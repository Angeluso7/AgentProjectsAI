import json
import logging
import os
from typing import Optional, Dict, Any, Union
from sqlalchemy.orm import Session

from app.db.models.symbol_catalog import SymbolUnknownResearchCase, SymbolReviewDecision
from app.db.models.document_memory import DetectedSymbol, DocumentSheet
from app.services.ai.claude_client import ClaudeClient, ClaudeClientDisabledError, ClaudeClientError
from app.services.symbols.canonical_catalog_service import CanonicalPipingCatalogService

logger = logging.getLogger(__name__)


class SymbolResearchService:
    """
    Servicio de investigación técnica y aprendizaje guiado por IA (Claude Vision + HITL)
    para símbolos desconocidos detectados en planos de ingeniería.
    """

    def __init__(self, db: Optional[Session] = None):
        self.db = db

    @staticmethod
    def format_sheet_label(sheet: Optional[DocumentSheet]) -> str:
        """Formatea la etiqueta legible de una lámina técnica."""
        if not sheet:
            return "Lámina no especificada"
        s_code = getattr(sheet, "sheet_code", None)
        s_num = getattr(sheet, "sheet_number", None)
        s_title = getattr(sheet, "title", None) or getattr(sheet, "sheet_name", None)
        if s_code and str(s_code).strip():
            return f"Lámina {str(s_code).strip()}"
        elif s_num is not None:
            return f"Lámina {s_num:02d}" if isinstance(s_num, int) else f"Lámina {s_num}"
        elif s_title and str(s_title).strip():
            return str(s_title).strip()
        return f"Lámina {str(sheet.id)[:6]}"

    @staticmethod
    def _parse_llm_json(raw_text: str) -> Optional[Dict[str, Any]]:
        """Extrae y parsea de forma robusta la respuesta JSON emitida por el modelo."""
        clean = (raw_text or "").strip()
        if "```json" in clean:
            clean = clean.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in clean:
            clean = clean.split("```", 1)[1].split("```", 1)[0].strip()

        try:
            parsed = json.loads(clean)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

        start = clean.find("{")
        end = clean.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                parsed = json.loads(clean[start : end + 1])
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass
        return None

    @classmethod
    def run_ai_research(
        cls,
        db: Session,
        research_case_id: str,
        claude_client: Optional[ClaudeClient] = None,
    ) -> SymbolUnknownResearchCase:
        """
        Ejecuta investigación guiada por IA multimodal sobre un caso de símbolo desconocido.
        No relanza excepciones por falta de API key ni por fallos de parseo, asegurando
        que el ciclo de vida progrese con trazabilidad.
        """
        case = db.query(SymbolUnknownResearchCase).filter(
            SymbolUnknownResearchCase.id == research_case_id
        ).first()
        if not case:
            raise ValueError(f"Caso de investigación '{research_case_id}' no encontrado.")

        occ: Optional[DetectedSymbol] = case.occurrence
        if not occ:
            occ = db.query(DetectedSymbol).filter(
                DetectedSymbol.id == case.symbol_occurrence_id
            ).first()

        doc_filename = "Desconocido"
        sheet_label = "Lámina no especificada"
        discipline = "piping"
        tag_code = None

        if occ:
            discipline = occ.discipline or "piping"
            tag_code = occ.detected_tag_or_code
            if occ.document:
                doc_filename = occ.document.filename or str(occ.document_id)
            elif occ.document_id:
                doc_filename = str(occ.document_id)

            if occ.sheet:
                sheet_label = cls.format_sheet_label(occ.sheet)

        crop_path = occ.crop_image_path if occ else None
        if not crop_path or not os.path.exists(crop_path):
            case.status = "research_exhausted"
            case.research_notes = f"Recorte de imagen no disponible o no existe en disco ({crop_path})."
            db.commit()
            return case

        client = claude_client or ClaudeClient()

        system_prompt = (
            "Eres un ingeniero senior experto en simbología técnica de diagramas de tuberías "
            "e instrumentación (P&ID) y piping bajo normativas ISA-5.1 y PIP PNC00001. "
            "Debes analizar el recorte visual del símbolo técnico adjunto y determinar su "
            "identidad técnica más probable.\n"
            "Debes responder ÚNICAMENTE con un objeto JSON estricto con los siguientes campos obligatorios:\n"
            "{\n"
            '  "proposed_name": "Nombre técnico del símbolo (ej. Gate Valve, Ball Valve, Control Valve)",\n'
            '  "proposed_standard_reference": "Norma técnica aplicable (ej. ISA-5.1, PIP PNC00001, ASME B31.3)",\n'
            '  "confidence": 0.95,\n'
            '  "reasoning": "Explicación técnica detallada de los rasgos geométricos y contexto observados"\n'
            "}\n"
            "No incluyas explicaciones de texto fuera del bloque JSON."
        )

        user_prompt = (
            f"Analiza este recorte de símbolo detectado en un plano de ingeniería.\n\n"
            f"Contexto disponible:\n"
            f"- Documento: {doc_filename}\n"
            f"- Lámina: {sheet_label}\n"
            f"- Disciplina: {discipline}\n"
            f"- Tag / Código asociado: {tag_code or 'Ninguno'}\n\n"
            f"Identifica el componente técnico, la norma de referencia, la confianza (0.0 a 1.0) "
            f"y el razonamiento geométrico."
        )

        try:
            raw_response = client.complete_vision(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                image_path=crop_path,
                max_tokens=1024,
                temperature=0.0,
            )
        except ClaudeClientDisabledError:
            case.status = "research_exhausted"
            case.research_notes = "IA no configurada (ANTHROPIC_API_KEY ausente)."
            db.commit()
            return case
        except Exception as e:
            err_msg = str(e)
            logger.warning(f"Error consultando Claude Vision para caso {case.id}: {err_msg}")
            case.status = "sources_found"
            case.research_notes = f"Error en consulta IA: {err_msg}"
            db.commit()
            return case

        parsed_data = cls._parse_llm_json(raw_response)
        required_keys = {"proposed_name", "proposed_standard_reference", "confidence", "reasoning"}

        if not parsed_data or not required_keys.issubset(parsed_data.keys()):
            case.status = "sources_found"
            case.research_notes = f"Respuesta IA no parseable: {raw_response[:800]}"
            db.commit()
            return case

        proposed_name = str(parsed_data["proposed_name"]).strip()
        proposed_std = str(parsed_data["proposed_standard_reference"]).strip()
        confidence = float(parsed_data.get("confidence", 0.0))
        reasoning = str(parsed_data.get("reasoning", "")).strip()

        case.status = "proposed_identity"
        case.proposed_name = proposed_name
        case.proposed_standard_reference = proposed_std
        case.research_notes = f"Confianza IA: {confidence:.2f}\n{reasoning}".strip()
        db.commit()
        return case

    @classmethod
    def validate_and_promote(
        cls,
        db: Session,
        research_case_id: str,
        reviewer_id: str,
        canonical_code: str,
        canonical_name: str,
        category: str = "valve",
        subcategory: str = "gate_valve",
        discipline: str = "piping",
        standard_reference: Optional[str] = None,
        evidence_kind: Optional[str] = "redacted_real",
        rationale: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Valida humanamente un caso de investigación y promueve su ocurrencia
        al catálogo canónico activo usando CanonicalPipingCatalogService.promote_candidate_to_canonical.
        """
        case = db.query(SymbolUnknownResearchCase).filter(
            SymbolUnknownResearchCase.id == research_case_id
        ).first()
        if not case:
            raise ValueError(f"Caso de investigación '{research_case_id}' no encontrado.")

        if not reviewer_id or not reviewer_id.strip():
            raise ValueError("Governance Violation: HITL Reviewer ID es obligatorio para validar y promover.")

        canonical_service = CanonicalPipingCatalogService(db)
        promo_res = canonical_service.promote_candidate_to_canonical(
            payload_or_candidate_id=case.symbol_occurrence_id,
            canonical_code=canonical_code,
            canonical_name=canonical_name,
            category=category,
            subcategory=subcategory,
            discipline=discipline,
            standard_reference=standard_reference or case.proposed_standard_reference,
            evidence_kind=evidence_kind or "redacted_real",
            reviewer_id=reviewer_id,
            rationale=rationale or f"Validado y promovido desde caso de investigación {case.id}",
            notes=notes or case.research_notes,
        )

        case.status = "human_validated"
        case.proposed_name = canonical_name
        case.proposed_standard_reference = standard_reference or case.proposed_standard_reference
        db.commit()

        return {
            "research_case": {
                "id": case.id,
                "symbol_occurrence_id": case.symbol_occurrence_id,
                "status": case.status,
                "search_query": case.search_query,
                "proposed_name": case.proposed_name,
                "proposed_standard_reference": case.proposed_standard_reference,
                "research_notes": case.research_notes,
                "created_at": case.created_at.isoformat() if case.created_at else None,
                "updated_at": case.updated_at.isoformat() if case.updated_at else None,
            },
            "template_id": promo_res.template_id,
            "template_version_id": promo_res.version_id,
            "canonical_code": promo_res.canonical_code,
            "version_number": promo_res.version_number,
            "status": promo_res.status,
            "message": promo_res.message,
        }

    @classmethod
    def dismiss_case(
        cls,
        db: Session,
        research_case_id: str,
        reviewer_id: str,
        rationale: str,
    ) -> SymbolUnknownResearchCase:
        """
        Descarta formalmente un caso de investigación dejándolo como 'unresolved'
        y registrando la decisión de auditoría HITL en SymbolReviewDecision.
        """
        case = db.query(SymbolUnknownResearchCase).filter(
            SymbolUnknownResearchCase.id == research_case_id
        ).first()
        if not case:
            raise ValueError(f"Caso de investigación '{research_case_id}' no encontrado.")

        if not reviewer_id or not reviewer_id.strip():
            raise ValueError("Governance Violation: Reviewer ID es obligatorio para descartar el caso.")

        case.status = "unresolved"
        dismiss_note = f"[Descartado por {reviewer_id}]: {rationale or 'Sin justificación'}"
        if case.research_notes:
            case.research_notes = f"{case.research_notes}\n{dismiss_note}".strip()
        else:
            case.research_notes = dismiss_note

        decision = SymbolReviewDecision(
            subject_type="research_case",
            subject_id=case.id,
            decision="dismiss",
            reviewer_id=reviewer_id,
            rationale=rationale,
            evidence_snapshot={"symbol_occurrence_id": case.symbol_occurrence_id},
            new_state={"status": "unresolved"},
        )
        db.add(decision)
        db.commit()

        return case
