import re
import unicodedata
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.db.models.intake_extractions import RuleDocument, RuleDocumentItem, ExtractedItem
from app.db.models.decision_memory import RuleDefinition
from app.db.models.normative_memory import NormativeDocument, NormativeClause, NormativeCriterion

class RuleDeduplicationService:
    """
    Servicio de Deduplicación y Matching Estricto de Reglas Candidatas contra el Motor QA/QC.
    
    Reglas de negocio:
    1. SQL es la autoridad de existencia real.
    2. Estados existentes elegibles para bloqueo: 'validated', 'approved', 'active', 'confirmado', 'promovido_baseline'.
    3. Estados NO elegibles: 'draft', 'to_confirm', 'rejected', 'archived', 'withdrawn', 'superseded', 'inactive'.
    4. Si duplicate_status == 'exact_match_existing_rule' -> blocked_from_acceptance = True.
    5. likely_duplicate_existing_rule y related_existing_rule NO bloquean la promoción.
    6. La regla candidata siempre permanece visible en el listado con la referencia a la regla existente.
    """

    ELIGIBLE_ACTIVE_STATUSES = {"active", "confirmado", "promovido_baseline", "validated", "approved"}
    RULE_ITEM_TYPES = {
        "rule", "restriction", "requirement", "article", "chapter", 
        "text_note", "definition", "procedure", "rule_candidate", "premise_candidate"
    }

    def __init__(self, db: Session):
        self.db = db

    # =========================================================
    # NORMALIZACIÓN CANÓNICA DE TEXTO Y CÓDIGOS
    # =========================================================

    @staticmethod
    def normalize_text(text: Optional[str]) -> str:
        """Normaliza cadenas eliminando tildes, puntuación, caracteres especiales y espacios redundantes."""
        if not text:
            return ""
        # Normalizar unicode (quitar acentos)
        nfkd = unicodedata.normalize("NFKD", text)
        cleaned = "".join([c for c in nfkd if not unicodedata.combining(c)]).lower()
        # Reemplazar puntuación por espacios
        cleaned = re.sub(r'[^a-z0-9\s]', ' ', cleaned)
        # Colapsar espacios múltiples
        return " ".join(cleaned.split())

    @staticmethod
    def normalize_code(code: Optional[str]) -> str:
        """Normaliza códigos identificadores para comparación canónica."""
        if not code:
            return ""
        nfkd = unicodedata.normalize("NFKD", code)
        cleaned = "".join([c for c in nfkd if not unicodedata.combining(c)]).upper()
        return re.sub(r'[^A-Z0-9]', '', cleaned)

    @classmethod
    def calculate_token_similarity(cls, text_a: str, text_b: str) -> float:
        """Calcula el coeficiente de similitud de tokens normalizados (Jaccard + Overlap)."""
        norm_a = cls.normalize_text(text_a)
        norm_b = cls.normalize_text(text_b)
        
        if not norm_a or not norm_b:
            return 0.0
        if norm_a == norm_b:
            return 1.0

        tokens_a = set(norm_a.split())
        tokens_b = set(norm_b.split())

        if not tokens_a or not tokens_b:
            return 0.0

        intersection = tokens_a.intersection(tokens_b)
        union = tokens_a.union(tokens_b)

        jaccard = len(intersection) / len(union) if union else 0.0
        overlap_min = len(intersection) / min(len(tokens_a), len(tokens_b))
        
        # Similitud combinada ponderada
        combined_sim = (jaccard * 0.6) + (overlap_min * 0.4)
        return min(1.0, combined_sim)

    # =========================================================
    # CONSULTA SQL DE REGLAS VIGENTES EN MOTOR QA/QC
    # =========================================================

    def get_existing_qaqc_rules(
        self,
        organization_id: str,
        project_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Recupera todas las reglas activas y elegibles del Motor QA/QC dentro del alcance de la organización y proyecto.
        SQL es la autoridad exclusiva de existencia.
        """
        active_rules = []

        # 1. Reglas en RuleDocument y RuleDocumentItem (Documentos y Reglas Incorporadas)
        doc_query = self.db.query(RuleDocumentItem, RuleDocument).join(
            RuleDocument, RuleDocumentItem.rule_document_id == RuleDocument.id
        ).filter(
            RuleDocument.organization_id == organization_id,
            RuleDocument.status.in_(self.ELIGIBLE_ACTIVE_STATUSES),
            RuleDocumentItem.status.in_(self.ELIGIBLE_ACTIVE_STATUSES)
        )

        for item, doc in doc_query.all():
            active_rules.append({
                "id": item.id,
                "document_id": doc.id,
                "code": item.code_or_number or f"DOC-{doc.discipline.upper()}-{item.id[:6]}",
                "title": item.title,
                "description": item.description or "",
                "content_text": item.content_text or item.description or item.title,
                "discipline": doc.discipline or "general",
                "authority": doc.authority or "Motor QA/QC",
                "source_type": "rule_document_item",
                "source_name": doc.title
            })

        # 2. Reglas determinísticas base en RuleDefinition
        def_query = self.db.query(RuleDefinition).filter(RuleDefinition.is_active == True)
        for rdef in def_query.all():
            active_rules.append({
                "id": rdef.id,
                "document_id": None,
                "code": rdef.code,
                "title": rdef.name,
                "description": rdef.description or "",
                "content_text": f"{rdef.name} - {rdef.description}",
                "discipline": rdef.discipline or "general",
                "authority": "Motor Determinístico QA/QC",
                "source_type": "rule_definition",
                "source_name": "Regla Determinística QA/QC"
            })

        # 3. Cláusulas y criterios normativos activos
        norm_query = self.db.query(NormativeClause, NormativeDocument).join(
            NormativeDocument, NormativeClause.document_id == NormativeDocument.id
        ).filter(
            NormativeDocument.is_active == True
        )
        for clause, ndoc in norm_query.all():
            active_rules.append({
                "id": clause.id,
                "document_id": ndoc.id,
                "code": clause.clause_number,
                "title": clause.title or f"{ndoc.code} - {clause.clause_number}",
                "description": clause.summary or clause.content_text[:200],
                "content_text": clause.content_text,
                "discipline": ndoc.discipline or "general",
                "authority": ndoc.authority or ndoc.code,
                "source_type": "normative_clause",
                "source_name": ndoc.title
            })

        return active_rules

    # =========================================================
    # EVALUACIÓN Y CLASIFICACIÓN DE CANDIDATOS
    # =========================================================

    def match_candidate(
        self,
        candidate_code: Optional[str],
        candidate_title: str,
        candidate_content: Optional[str],
        candidate_discipline: str,
        candidate_item_type: str,
        existing_rules: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Evalúa una regla candidata contra la colección de reglas existentes.
        Retorna la clasificación de coincidencia determinística y los metadatos de referencia.
        """
        # Si no es un tipo de regla o premisa normativa, no aplica deduplicación de reglas
        is_rule_like = candidate_item_type in self.RULE_ITEM_TYPES or "rule" in candidate_item_type or "premise" in candidate_item_type
        if not is_rule_like or not existing_rules:
            return {
                "duplicate_status": "no_match",
                "best_match_rule_id": None,
                "best_match_rule_code": None,
                "best_match_title": None,
                "best_match_discipline": None,
                "duplicate_reason": None,
                "duplicate_confidence": 0.0,
                "blocked_from_acceptance": False
            }

        norm_cand_code = self.normalize_code(candidate_code)
        norm_cand_title = self.normalize_text(candidate_title)
        cand_full_text = f"{candidate_title} {candidate_content or ''}"
        norm_cand_full = self.normalize_text(cand_full_text)

        best_match = None
        best_status = "no_match"
        best_confidence = 0.0
        best_reason = ""
        is_blocked = False

        # Lista de códigos genéricos que no deben provocar match exacto únicamente por código
        generic_codes = {"REG01", "REG02", "REG1", "REG2", "R01", "R1", "ART1", "ART01", "CAP1", "CAP01", "TBL01", "NOTE01"}

        for existing in existing_rules:
            ex_code = existing.get("code") or ""
            ex_title = existing.get("title") or ""
            ex_content = existing.get("content_text") or ""
            ex_disc = existing.get("discipline") or "general"

            norm_ex_code = self.normalize_code(ex_code)
            norm_ex_title = self.normalize_text(ex_title)
            norm_ex_full = self.normalize_text(f"{ex_title} {ex_content}")

            # Calcular similitudes
            title_sim = self.calculate_token_similarity(candidate_title, ex_title)
            content_sim = self.calculate_token_similarity(cand_full_text, f"{ex_title} {ex_content}")
            max_sim = max(title_sim, content_sim)

            # 1. MATCH EXACTO POR CÓDIGO (si el código es específico y no genérico)
            code_exact_match = (
                bool(norm_cand_code) and 
                bool(norm_ex_code) and 
                norm_cand_code == norm_ex_code and 
                norm_cand_code not in generic_codes and 
                len(norm_cand_code) >= 4 and
                (max_sim >= 0.65 or candidate_discipline == ex_disc or ex_disc == "general" or candidate_discipline == "general")
            )

            # 2. MATCH EXACTO POR TEXTO O TÍTULO CANÓNICO
            title_exact_match = (norm_cand_title == norm_ex_title and len(norm_cand_title) >= 15)
            content_exact_match = (norm_cand_full == norm_ex_full and len(norm_cand_full) >= 20)
            high_semantic_exact = (max_sim >= 0.93 and (candidate_discipline == ex_disc or ex_disc == "general" or candidate_discipline == "general"))

            if code_exact_match or title_exact_match or content_exact_match or high_semantic_exact:
                reason = f"Coincidencia exacta con la regla vigente '{ex_code}: {ex_title}' en el Motor QA/QC."
                if code_exact_match:
                    reason += f" (Código idéntico: {ex_code})"
                elif title_exact_match or content_exact_match:
                    reason += " (Texto o título canónico idéntico)"
                else:
                    reason += f" (Similitud textual: {round(max_sim * 100)}%)"

                return {
                    "duplicate_status": "exact_match_existing_rule",
                    "best_match_rule_id": existing.get("id"),
                    "best_match_rule_code": ex_code,
                    "best_match_title": ex_title,
                    "best_match_discipline": ex_disc,
                    "duplicate_reason": reason,
                    "duplicate_confidence": 1.0,
                    "blocked_from_acceptance": True
                }

            # 3. MATCH PROBABLE (likely_duplicate_existing_rule) -> NO BLOQUEA
            elif max_sim >= 0.78 and (candidate_discipline == ex_disc or ex_disc == "general" or candidate_discipline == "general"):
                if max_sim > best_confidence:
                    best_confidence = max_sim
                    best_status = "likely_duplicate_existing_rule"
                    best_match = existing
                    best_reason = f"Similitud textual alta ({round(max_sim * 100)}%) con la regla '{ex_code}: {ex_title}' en Motor QA/QC."

            # 4. REGLA RELACIONADA (related_existing_rule) -> NO BLOQUEA
            elif max_sim >= 0.58 and best_status not in ["likely_duplicate_existing_rule"]:
                if max_sim > best_confidence:
                    best_confidence = max_sim
                    best_status = "related_existing_rule"
                    best_match = existing
                    best_reason = f"Contenido temáticamente relacionado ({round(max_sim * 100)}%) con la regla '{ex_code}: {ex_title}'."

        if best_match and best_status != "no_match":
            return {
                "duplicate_status": best_status,
                "best_match_rule_id": best_match.get("id"),
                "best_match_rule_code": best_match.get("code"),
                "best_match_title": best_match.get("title"),
                "best_match_discipline": best_match.get("discipline"),
                "duplicate_reason": best_reason,
                "duplicate_confidence": round(best_confidence, 2),
                "blocked_from_acceptance": False
            }

        return {
            "duplicate_status": "no_match",
            "best_match_rule_id": None,
            "best_match_rule_code": None,
            "best_match_title": None,
            "best_match_discipline": None,
            "duplicate_reason": None,
            "duplicate_confidence": 0.0,
            "blocked_from_acceptance": False
        }

    # =========================================================
    # EVALUACIÓN EN LOTE DE ELEMENTOS EXTRAÍDOS
    # =========================================================

    def evaluate_and_tag_items(
        self,
        organization_id: str,
        project_id: Optional[str],
        items: List[ExtractedItem]
    ) -> List[ExtractedItem]:
        """
        Evalúa en lote una lista de ExtractedItem, etiquetando los campos de deduplicación
        y aplicando el bloqueo obligatorio a las coincidencias exactas.
        """
        existing_rules = self.get_existing_qaqc_rules(organization_id=organization_id, project_id=project_id)
        
        for it in items:
            match_res = self.match_candidate(
                candidate_code=it.code_or_number,
                candidate_title=it.title,
                candidate_content=it.content_text or it.description,
                candidate_discipline=it.technical_parameters.get("primary_discipline") if it.technical_parameters else "general",
                candidate_item_type=it.item_type,
                existing_rules=existing_rules
            )

            it.duplicate_status = match_res["duplicate_status"]
            it.best_match_rule_id = match_res["best_match_rule_id"]
            it.best_match_rule_code = match_res["best_match_rule_code"]
            it.best_match_title = match_res["best_match_title"]
            it.best_match_discipline = match_res["best_match_discipline"]
            it.duplicate_reason = match_res["duplicate_reason"]
            it.duplicate_confidence = match_res["duplicate_confidence"]
            it.blocked_from_acceptance = match_res["blocked_from_acceptance"]

            # Reflejar también en metadata_payload para trazabilidad
            meta = dict(it.metadata_payload or {})
            meta.update({
                "duplicate_status": it.duplicate_status,
                "best_match_rule_code": it.best_match_rule_code,
                "best_match_title": it.best_match_title,
                "blocked_from_acceptance": it.blocked_from_acceptance,
                "duplicate_reason": it.duplicate_reason
            })
            it.metadata_payload = meta

        return items
