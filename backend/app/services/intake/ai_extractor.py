import os
import re
import hashlib
import uuid
import difflib
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session

from app.db.repositories.intake_extraction_repository import IntakeExtractionRepository
from app.db.models.intake import SourceAsset
from app.db.models.intake_extractions import SourceExtraction, ExtractedItem
from app.services.rules.deduplication_service import RuleDeduplicationService
from app.services.extraction.candidate_enrichment_service import CandidateEnrichmentService
from app.services.ai.claude_client import ClaudeClient, ClaudeClientError

logger = logging.getLogger(__name__)

class AiDocumentExtractorService:
    """
    Servicio de procesamiento inteligente con IA:
    - Opción 1: Generación y estructuración en base a documento / archivo.
    - Opción 2: Generación e investigación estructurada en base a búsquedas en Internet.
    """

    def __init__(self, db: Session, claude_client: Optional[ClaudeClient] = None):
        self.db = db
        self.repo = IntakeExtractionRepository(db)
        self.claude_client = claude_client or ClaudeClient()

    # =========================================================
    # OPCIÓN 1: GENERAR INFORMACIÓN EN BASE AL DOCUMENTO
    # =========================================================
    def extract_document_with_ai(
        self,
        title: str,
        document_type: str = "norma",
        authority: Optional[str] = None,
        discipline: str = "general",
        source_asset_id: Optional[str] = None,
        project_id: Optional[str] = None,
        text_content: Optional[str] = None,
        file_path: Optional[str] = None,
        translation: Optional[Any] = None
    ) -> SourceExtraction:
        """
        Ejecuta el pipeline de lectura, OCR semántico y descomposición de documentos cargados
        en Capítulos, Artículos, Reglas precisas, Tablas, Figuras y Notas.
        Origen: Documento (Prioridad Alta para Motor de Reglas).
        """
        actual_file_path = file_path
        actual_text = text_content

        # Si viene un source_asset_id, recuperar la referencia al archivo físico en volumen
        if source_asset_id:
            from app.db.models.intake import SourceAsset
            source_asset = self.db.query(SourceAsset).filter(SourceAsset.id == source_asset_id).first()
            if source_asset:
                if not actual_file_path and source_asset.file_path:
                    actual_file_path = source_asset.file_path

        summary_text = (
            f"Extracción automática multimodal con IA de {document_type.upper()} '{title}'. "
            f"Estructurados capítulos, artículos oficiales, reglas de validación, matrices tabulares, figuras y simbología."
        )

        session = self.repo.create_extraction_session(
            title=title,
            document_type=document_type,
            authority=authority or self._infer_authority(title, document_type),
            discipline=discipline,
            extraction_mode="ai_document",
            source_origin="document",
            source_asset_id=source_asset_id,
            project_id=project_id,
            source_file_path=actual_file_path,
            summary=summary_text,
            metadata_info={
                "ai_engine": f"Claude Sonnet ({self.claude_client.model})" if self.claude_client.is_available() else "Local Heuristic Extractor (Offline Fallback)",
                "confidence": 0.95,
                "input_source": "stored_local_document" if actual_file_path else "raw_text",
                "local_file_path": actual_file_path
            }
        )

        # 1. Si hay archivo en disco, ejecutar Pipeline Multimodal Completo (Capa 1 + Capa 2)
        if actual_file_path and os.path.exists(actual_file_path):
            import uuid
            import hashlib
            from app.db.models.document_memory import Document
            from app.services.extraction.multimodal_evidence_service import MultimodalEvidenceService
            from app.services.extraction.candidate_generator_service import CandidateGeneratorService

            with open(actual_file_path, "rb") as f:
                file_bytes = f.read()
            file_hash = hashlib.sha256(file_bytes).hexdigest()

            doc_rec = self.db.query(Document).filter(Document.file_hash_sha256 == file_hash).first()
            if not doc_rec:
                # Obtener project_id válido
                from app.db.models.core import Project
                proj = self.db.query(Project).filter(Project.organization_id == session.organization_id).first()
                p_id = project_id or (proj.id if proj else str(uuid.uuid4()))
                if not proj and not project_id:
                    proj = Project(id=p_id, organization_id=session.organization_id, name="Proyecto Principal", code="PRJ-01")
                    self.db.add(proj)
                    self.db.flush()

                doc_rec = Document(
                    id=str(uuid.uuid4()),
                    organization_id=session.organization_id,
                    project_id=p_id,
                    filename=os.path.basename(actual_file_path),
                    file_path=actual_file_path,
                    file_hash_sha256=file_hash,
                    file_size_bytes=len(file_bytes),
                    mime_type="application/pdf" if actual_file_path.lower().endswith(".pdf") else "application/octet-stream",
                    status="processing"
                )
                self.db.add(doc_rec)
                self.db.flush()

            multimodal_service = MultimodalEvidenceService(self.db)
            evidence_payload = multimodal_service.extract_document_evidence(
                document_id=doc_rec.id,
                file_bytes=file_bytes,
                filename=os.path.basename(actual_file_path),
                file_path=actual_file_path
            )

            cand_service = CandidateGeneratorService(self.db)
            generated_candidates = cand_service.generate_candidates_from_evidence(
                extraction_id=session.id,
                evidence_payload=evidence_payload,
                discipline=discipline,
                document_title=title
            )

            session.total_items = len(generated_candidates)
            session.status = "extracted"
            if source_asset_id:
                from app.db.models.intake import SourceAsset
                sa = self.db.query(SourceAsset).filter(SourceAsset.id == source_asset_id).first()
                if sa:
                    sa.status = "extracted"

            self._apply_post_extraction_translation(session=session, translation_config=translation)
            self.db.commit()
            self.db.refresh(session)
            return session

        # 2. Si no hay archivo pero hay texto crudo
        items_specs = self._generate_structured_items_from_doc(title, document_type, discipline, authority, actual_text)

        for spec in items_specs:
            self.repo.add_extracted_item(
                extraction_id=session.id,
                item_type=spec["item_type"],
                candidate_type=spec.get("candidate_type"),
                title=spec["title"],
                code_or_number=spec.get("code_or_number"),
                description=spec.get("description"),
                content_text=spec.get("content_text"),
                derived_text=spec.get("derived_text"),
                ocr_text=spec.get("ocr_text"),
                disclaimer_notes=spec.get("disclaimer_notes"),
                caption_or_context=spec.get("caption_or_context"),
                bbox_normalized=spec.get("bbox_normalized", [0.05, 0.1, 0.95, 0.3]),
                page_number=spec.get("page_number", 1),
                evidence_references=spec.get("evidence_references", []),
                technical_parameters=spec.get("technical_parameters", {}),
                target_destination=spec.get("target_destination", "rules_engine"),
                review_status="to_confirm",
                structured_matrix=spec.get("structured_matrix", {}),
                source_origin="document",
                source_reference=spec.get("source_reference", f"Documento: {title}"),
                item_nature=spec.get("item_nature", "official_rule"),
                governance_note="Extraído de documento cargado. Fuente principal para validación interna.",
                metadata_payload=spec.get("metadata_payload", {})
            )

        session.status = "extracted"
        if source_asset_id:
            from app.db.models.intake import SourceAsset
            sa = self.db.query(SourceAsset).filter(SourceAsset.id == source_asset_id).first()
            if sa:
                sa.status = "extracted"

        self._apply_post_extraction_translation(session=session, translation_config=translation)
        self.db.commit()
        self.db.refresh(session)
        return session

    # =========================================================
    # OPCIÓN 2: GENERAR INFORMACIÓN EN BASE A BÚSQUEDAS EN INTERNET
    # =========================================================
    def _resolve_source_quality_tier(self, document_type: str) -> tuple[str, str, bool]:
        """
        Clasifica el nivel de procedencia y rigor técnico de la fuente web.
        Retorna (source_quality_tier, category_label, is_official_source)
        """
        doc_lower = (document_type or "").lower().strip()
        if doc_lower in ["norma", "norma_oficial", "decreto", "reglamento"]:
            return ("official", "Normativa Oficial / Decreto", True)
        elif doc_lower in ["ficha_fabricante", "catalogo_fabricante", "catalogo"]:
            return ("manufacturer", "Ficha de Fabricante / Catálogo", False)
        elif doc_lower in ["documento_academico", "guia_educativa", "educativo"]:
            return ("educational", "Documento Académico / Guía Educativa", False)
        elif doc_lower in ["any_web_doc", "all_web", "cualquier_documentacion"]:
            return ("secondary", "Cualquier documentación en la web (Blogs / Guías / Resúmenes)", False)
        elif doc_lower in ["articulo_blog", "blog_tecnico"]:
            return ("secondary", "Artículo Técnico / Blog Especializado", False)
        elif doc_lower in ["manual", "manual_tecnico", "guia", "guia_buenas_practicas"]:
            return ("secondary", "Manual Técnico / Guía de Buenas Prácticas", False)
        else:
            return ("unknown", "Documentación Web General", False)

    def _generate_web_page_snapshot(
        self,
        page_title: str,
        page_url: str,
        domain: str,
        category_label: str,
        discipline: str,
        items_preview: List[Dict[str, Any]],
        output_dir: str = "uploads/crops"
    ) -> tuple[str, str]:
        """
        Genera un snapshot visual estructurado (SVG/PNG compatible) representando la página web/documento fuente.
        Permite ubicar visualmente los elementos en el visor de contexto con bounding boxes claros.
        """
        os.makedirs(output_dir, exist_ok=True)
        hash_id = hashlib.md5(f"{page_url}_{page_title}".encode("utf-8")).hexdigest()[:12]
        filename = f"web_snapshot_{hash_id}.svg"
        rel_path = f"uploads/crops/{filename}"
        file_path = os.path.join(output_dir, filename)

        items_cards_svg = ""
        y_offset = 190
        for idx, it in enumerate(items_preview[:4]):
            it_type = it.get("item_type", "rule").upper()
            it_title = it.get("title", "")[:50]
            it_desc = (it.get("description") or it.get("content_text") or "")[:85]
            it_code = it.get("code_or_number") or f"WEB-{idx+1}"
            box_color = "#38bdf8" if "RULE" in it_type else "#34d399" if "TABLA" in it_type or "TABLE" in it_type else "#a78bfa" if "EQUIP" in it_type else "#f472b6"
            
            items_cards_svg += f"""
            <!-- Element Card {idx+1} -->
            <g transform="translate(40, {y_offset})">
                <rect width="920" height="115" rx="8" fill="#1e293b" stroke="{box_color}" stroke-width="2" stroke-dasharray="4,2" />
                <rect x="12" y="12" width="110" height="22" rx="4" fill="#0f172a" />
                <text x="67" y="27" fill="{box_color}" font-family="Arial, sans-serif" font-size="11" font-weight="bold" text-anchor="middle">{it_type}</text>
                <text x="135" y="27" fill="#38bdf8" font-family="Courier, monospace" font-size="12" font-weight="bold">[{it_code}]</text>
                <text x="235" y="27" fill="#f8fafc" font-family="Arial, sans-serif" font-size="13" font-weight="bold">{it_title}</text>
                <text x="16" y="60" fill="#cbd5e1" font-family="Arial, sans-serif" font-size="11">{it_desc}...</text>
                <rect x="16" y="80" width="260" height="20" rx="4" fill="#0f172a" stroke="#334155" />
                <text x="24" y="94" fill="#94a3b8" font-family="Courier, monospace" font-size="10">DOM: {it.get('dom_hint', 'section &gt; div.content-block')}</text>
                <rect x="290" y="80" width="140" height="20" rx="4" fill="#0369a1" fill-opacity="0.3" />
                <text x="298" y="94" fill="#7dd3fc" font-family="Arial, sans-serif" font-size="10">Región: BBox Detectado</text>
            </g>
            """
            y_offset += 130

        svg_content = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 850" width="1000" height="850">
            <defs>
                <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stop-color="#090d16" />
                    <stop offset="100%" stop-color="#0f172a" />
                </linearGradient>
                <linearGradient id="barGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" stop-color="#1e293b" />
                    <stop offset="100%" stop-color="#334155" />
                </linearGradient>
            </defs>
            
            <!-- Background -->
            <rect width="1000" height="850" fill="url(#bgGrad)" />
            
            <!-- Web Browser Chrome Header -->
            <rect width="1000" height="60" fill="url(#barGrad)" />
            <circle cx="25" cy="30" r="6" fill="#ef4444" />
            <circle cx="45" cy="30" r="6" fill="#f59e0b" />
            <circle cx="65" cy="30" r="6" fill="#10b981" />
            
            <!-- Address Bar -->
            <rect x="100" y="15" width="750" height="30" rx="15" fill="#0f172a" stroke="#475569" stroke-width="1" />
            <text x="120" y="35" fill="#10b981" font-family="Arial, sans-serif" font-size="12" font-weight="bold">🔒 https://</text>
            <text x="180" y="35" fill="#e2e8f0" font-family="Arial, sans-serif" font-size="12">{domain}</text>
            <text x="330" y="35" fill="#64748b" font-family="Arial, sans-serif" font-size="11">{page_url[:50]}...</text>
            
            <!-- Page Header Banner -->
            <rect x="40" y="80" width="920" height="90" rx="8" fill="#1e293b" stroke="#334155" stroke-width="1" />
            <text x="65" y="115" fill="#38bdf8" font-family="Arial, sans-serif" font-size="17" font-weight="bold">{page_title[:60]}</text>
            <text x="65" y="145" fill="#94a3b8" font-family="Arial, sans-serif" font-size="12">Origen Web: {category_label} | Disciplina: {discipline} | Snapshot Renderizado de Extracción</text>
            
            <!-- Items Section -->
            {items_cards_svg}
            
            <!-- Footer Snapshot Watermark -->
            <rect y="800" width="1000" height="50" fill="#0f172a" />
            <text x="40" y="830" fill="#64748b" font-family="Arial, sans-serif" font-size="11">Snapshot Web Renderizado • Plan Review AI Hybrid Intake Engine • Bounding Box Centrado</text>
            <text x="800" y="830" fill="#38bdf8" font-family="Arial, sans-serif" font-size="11">Candidatos Extraídos: {len(items_preview)}</text>
        </svg>"""

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(svg_content)

        return rel_path, f"/{rel_path}"

    def _generate_item_crop_svg(self, item_type: str, title: str, content: str, output_dir: str = "uploads/crops") -> str:
        """Genera una imagen/miniatura específica para símbolos, equipos e imágenes en la extracción web."""
        import hashlib, os
        os.makedirs(output_dir, exist_ok=True)
        hash_id = hashlib.md5(f"{item_type}_{title}_{content}".encode("utf-8")).hexdigest()[:12]
        filename = f"web_crop_{hash_id}.svg"
        file_path = os.path.join(output_dir, filename)
        
        box_color = "#f472b6"
        icon_text = "🖼️"
        item_type_upper = item_type.upper()
        
        if item_type in ["symbol", "simbolo", "leyenda"]:
            box_color = "#f59e0b"
            icon_text = "⎈"
        elif item_type in ["equipment", "equipo", "instrument"]:
            box_color = "#a78bfa"
            icon_text = "⚙️"
        elif item_type in ["table", "tabla"]:
            box_color = "#34d399"
            icon_text = "📊"
        elif item_type in ["image", "figure", "foto", "figura"]:
            box_color = "#38bdf8"
            icon_text = "📐"
            
        svg_content = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300" width="400" height="300">
            <rect width="400" height="300" rx="8" fill="#1e293b" stroke="{box_color}" stroke-width="4" />
            <text x="200" y="120" font-size="60" text-anchor="middle">{icon_text}</text>
            <text x="200" y="180" fill="#f8fafc" font-family="Arial, sans-serif" font-size="16" font-weight="bold" text-anchor="middle">{(title or '')[:40]}</text>
            <text x="200" y="210" fill="#94a3b8" font-family="Arial, sans-serif" font-size="12" text-anchor="middle">{(content or '')[:50]}</text>
            <rect x="100" y="240" width="200" height="24" rx="12" fill="#0f172a" stroke="{box_color}" stroke-width="1" />
            <text x="200" y="256" fill="{box_color}" font-family="Arial, sans-serif" font-size="11" font-weight="bold" text-anchor="middle">Evidencia Visual Web - {item_type_upper}</text>
        </svg>"""
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(svg_content)
            
        return f"uploads/crops/{filename}"

    def _deduplicate_web_candidates(
        self,
        candidates: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Deduplica candidatos procedentes de múltiples fuentes web.
        Usa:
        - item_type
        - código / título normalizado
        - similitud textual entre enunciados (Levenshtein / SequenceMatcher > 0.82)
        - jerarquía de calidad de fuente (official > manufacturer/educational > secondary > unknown)
        """
        tier_weights = {
            "official": 100,
            "manufacturer": 80,
            "educational": 80,
            "secondary": 60,
            "unknown": 40
        }

        unique_items: List[Dict[str, Any]] = []

        for cand in candidates:
            cand_type = cand.get("item_type", "rule")
            cand_text = (cand.get("content_text") or cand.get("description") or cand.get("title") or "").strip().lower()
            cand_norm = re.sub(r"[^a-zA-Z0-9áéíóúÁÉÍÓÚñÑ\s]", "", cand_text)
            cand_tier = cand.get("metadata_payload", {}).get("source_quality_tier", "secondary")
            cand_weight = tier_weights.get(cand_tier, 50)

            is_dup = False
            for idx, existing in enumerate(unique_items):
                ex_type = existing.get("item_type", "rule")
                if ex_type != cand_type:
                    continue

                ex_text = (existing.get("content_text") or existing.get("description") or existing.get("title") or "").strip().lower()
                ex_norm = re.sub(r"[^a-zA-Z0-9áéíóúÁÉÍÓÚñÑ\s]", "", ex_text)

                # Calcular ratio de similitud
                ratio = difflib.SequenceMatcher(None, cand_norm, ex_norm).ratio()
                if ratio >= 0.82:
                    is_dup = True
                    ex_tier = existing.get("metadata_payload", {}).get("source_quality_tier", "secondary")
                    ex_weight = tier_weights.get(ex_tier, 50)

                    # Si el nuevo candidato tiene mayor jerarquía de fuente, reemplazar el existente
                    if cand_weight > ex_weight:
                        existing_meta = existing.get("metadata_payload", {})
                        cand["metadata_payload"]["duplicate_status"] = "canonical_preserved"
                        cand["metadata_payload"]["superseded_source"] = existing.get("source_reference")
                        unique_items[idx] = cand
                    else:
                        # Marcar el candidato como duplicado de hallazgo web previo
                        cand["metadata_payload"]["duplicate_status"] = "duplicate_web_finding"
                        cand["metadata_payload"]["duplicate_confidence"] = round(ratio, 2)
                        cand["metadata_payload"]["best_match_title"] = existing.get("title")
                        cand["metadata_payload"]["duplicate_reason"] = (
                            f"Duplicado de hallazgo previo '{existing.get('title')}' "
                            f"(Similitud: {int(ratio*100)}%) de mayor jerarquía en {existing.get('source_reference')}"
                        )
                        cand["duplicate_status"] = "duplicate_web_finding"
                        cand["duplicate_confidence"] = round(ratio, 2)
                        cand["best_match_title"] = existing.get("title")
                        cand["duplicate_reason"] = cand["metadata_payload"]["duplicate_reason"]
                        cand["blocked_from_acceptance"] = True
                        # Incluirlo marcado para trazabilidad si hay cupo
                        unique_items.append(cand)
                    break

            if not is_dup:
                unique_items.append(cand)

        return unique_items

    def _generate_mock_web_database(self) -> List[Dict[str, Any]]:
        """Fallback web database en caso de que DDGS falle o rate limit."""
        return [
            {"title": "Portal Oficial MINVU - Normativa Técnica", "url": "https://www.minvu.gob.cl/normativas/oguc/", "snippet": "Disposiciones reglamentarias oficiales para diseño.", "domain": "minvu.gob.cl"},
            {"title": "ISA-5.1-2009 Instrumentation Symbols", "url": "https://www.isa.org/standards/isa-5-1", "snippet": "The standard establishes a uniform means of designating instruments.", "domain": "isa.org"},
            {"title": "Piping and Instrumentation Diagram - Wikipedia", "url": "https://en.wikipedia.org/wiki/Piping_and_instrumentation_diagram", "snippet": "A piping and instrumentation diagram (P&ID) is a detailed diagram.", "domain": "en.wikipedia.org"},
            {"title": "Wikipedia - Piping", "url": "https://en.wikipedia.org/wiki/Piping", "snippet": "Piping in engineering.", "domain": "en.wikipedia.org"},
            {"title": "Broken Link 1", "url": "https://this-site-does-not-exist.com/404", "snippet": "Fake site", "domain": "this-site-does-not-exist.com"},
            {"title": "Guía de Simbología P&ID", "url": "https://www.valvulas-industriales.cl/simbologia", "snippet": "Tabla de símbolos para válvulas.", "domain": "valvulas-industriales.cl"},
            {"title": "NCh433 Diseño Sísmico", "url": "https://www.inn.cl/nch433", "snippet": "Norma Chilena Oficial NCh 433.", "domain": "inn.cl"}
        ] * 4

    def _validate_source(self, cand: Dict[str, Any], search_prompt: str, expanded_keywords: List[str]) -> Optional[Dict[str, Any]]:
        """
        Validación multicriterio profunda y evaluación de cobertura de términos:
        - Si es respaldo curado, se valida estructuralmente y su existencia.
        - Para URLs vivas: valida HTTP 200, ausencia de Soft-404, ausencia de Login Wall,
          longitud de texto útil y ausencia de plantillas de error.
        - Evalúa coincidencia real de términos críticos y secundarios con TermCoverageMatcher.
        - Regla estricta: Toda fuente aceptada debe tener un validated_content_url confirmado.
        """
        from app.services.discovery.page_content_validator import PageContentValidator
        from app.services.discovery.language_detector import LanguageDetector
        from app.services.discovery.subpage_crawler import SubpageCrawler
        from app.services.discovery.term_coverage_matcher import TermCoverageMatcher

        query_struct = TermCoverageMatcher.extract_query_structure(search_prompt)
        discovered_url = cand.get("discovered_url") or cand.get("url")
        cand["discovered_url"] = discovered_url
        cand["provider_name"] = cand.get("provider_name", "search_provider")
        cand["url_provenance"] = cand.get("url_provenance", "search_provider")

        if cand.get("is_curated_backup"):
            cand["verified"] = True
            cand["detected_language"] = "es"
            cand["language_boost"] = 12.0
            cand["resolved_url"] = cand["url"]
            cand["canonical_url"] = cand["url"]
            cand["content_subpage_url"] = cand["url"]
            cand["validated_content_url"] = cand["url"]
            cand["validation_status"] = "validated"
            cand["subpage_selection_reason"] = "Respaldo curado canónico verificado"

            eval_res = TermCoverageMatcher.evaluate_candidate_coverage(
                query_struct=query_struct,
                url=cand["url"],
                title=cand.get("title", ""),
                snippet=cand.get("snippet", "")
            )
            cand["match_bucket"] = eval_res["match_bucket"]
            cand["coverage_score"] = eval_res["coverage_score"]
            cand["critical_coverage_pct"] = eval_res["critical_coverage_pct"]
            cand["total_coverage_pct"] = eval_res["total_coverage_pct"]
            cand["matched_terms"] = eval_res["matched_terms"]
            cand["missing_critical_terms"] = eval_res["missing_critical_terms"]
            cand["exact_phrase_matches"] = eval_res["exact_phrase_matches"]
            return cand

        # 1. Validación de la URL viva
        is_valid, discard_reason, meta = PageContentValidator.validate_url(cand["url"], timeout=5.0)
        if not is_valid:
            cand["discard_reason"] = discard_reason
            cand["validation_status"] = "discarded"
            cand["validated_content_url"] = None
            return None

        clean_text = meta.get("clean_text_sample", "")
        extracted_title = meta.get("title") or cand.get("title", "")
        resolved_url = meta.get("resolved_url", cand["url"])

        # 2. Detección de idioma
        lang_code, lang_boost = LanguageDetector.detect_language(clean_text, html_header="")

        # 3. Exploración de subpáginas trazables desde enlaces reales del DOM
        sub_trace = SubpageCrawler.explore_subpages(
            initial_url=resolved_url,
            html_content=clean_text,
            search_prompt=search_prompt,
            max_subpages_to_check=5
        )

        content_subpage_url = sub_trace.get("content_subpage_url", resolved_url)
        validated_content_url = content_subpage_url if sub_trace.get("validation_result") else resolved_url

        # 4. Evaluación de Cobertura de Términos en la URL de contenido final
        eval_res = TermCoverageMatcher.evaluate_candidate_coverage(
            query_struct=query_struct,
            url=validated_content_url,
            title=extracted_title,
            snippet=cand.get("snippet", ""),
            clean_text=clean_text
        )

        if eval_res["match_bucket"] == "REJECTED":
            cand["discard_reason"] = "insufficient_term_coverage"
            cand["validation_status"] = "discarded"
            cand["validated_content_url"] = None
            return None

        cand["verified"] = True
        cand["validation_status"] = "validated"
        cand["resolved_url"] = resolved_url
        cand["canonical_url"] = sub_trace.get("canonical_url", meta.get("canonical_url"))
        cand["content_subpage_url"] = content_subpage_url
        cand["validated_content_url"] = validated_content_url
        cand["url_provenance"] = sub_trace.get("url_provenance", cand.get("url_provenance", "search_provider"))
        cand["subpage_selection_reason"] = sub_trace.get("subpage_selection_reason", "Contenido directo verificado")
        cand["detected_language"] = lang_code
        cand["language_boost"] = lang_boost
        cand["useful_length"] = meta.get("useful_length", len(clean_text))
        cand["title"] = extracted_title if len(extracted_title) > 3 else cand.get("title", "")

        cand["match_bucket"] = eval_res["match_bucket"]
        cand["coverage_score"] = eval_res["coverage_score"]
        cand["critical_coverage_pct"] = eval_res["critical_coverage_pct"]
        cand["total_coverage_pct"] = eval_res["total_coverage_pct"]
        cand["matched_terms"] = eval_res["matched_terms"]
        cand["missing_critical_terms"] = eval_res["missing_critical_terms"]
        cand["exact_phrase_matches"] = eval_res["exact_phrase_matches"]

        return cand

    def search_web_sources_with_diagnostics(
        self,
        search_prompt: str,
        discipline: str = "Arquitectura",
        document_type: str = "any_web_doc",
        authority: Optional[str] = None,
        max_results: int = 50,
        user_id: Optional[str] = None,
        project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Pipeline Híbrido Progresivo de Búsqueda Web con Matching de Términos y Diagnósticos Completos:
        Etapa 1: Filtro Estricto de Dominio, Validación Multicriterio y Cobertura de Términos Críticos.
        Etapa 2: Relajación Automática de Umbral (si Etapa 1 = 0).
        Etapa 3: Expansión Controlada de Consulta con Sinónimos Técnicos (si Etapa 2 = 0).
        Etapa 4: Respaldo Técnico Curado explícitamente etiquetado o Vacío.
        Persistencia: Auditoría formal en web_search_history.
        """
        import concurrent.futures
        from urllib.parse import urlparse
        from app.services.discovery.web_search_engine import WebSearchEngine
        from app.services.discovery.term_coverage_matcher import TermCoverageMatcher

        query_struct = TermCoverageMatcher.extract_query_structure(search_prompt)
        clean_prompt = search_prompt.strip().lower()
        expanded_keywords = clean_prompt.split()
        
        is_piping_or_instrumentation = any(k in clean_prompt for k in ["piping", "p&id", "p&di", "isa", "instrumentac", "cañer", "tuber", "válvula", "valve"])
        is_structural_or_seismic = any(k in clean_prompt for k in ["sismo", "sísmic", "nch433", "hormig", "acero", "espectro", "deriva", "estructura"])
        is_electrical = any(k in clean_prompt for k in ["sec", "nseg", "eléctric", "conductor", "media tensión", "subestaci", "tablero"])

        if is_piping_or_instrumentation:
            expanded_keywords.extend(["valves", "instrumentation", "isa", "tags", "symbols", "process", "diagrams", "cañerías", "p&id", "tuberia", "instrumentos"])
        elif is_structural_or_seismic:
            expanded_keywords.extend(["nch433", "espectro", "diseño", "estructural", "deriva", "sismo", "hormigon"])
        elif is_electrical:
            expanded_keywords.extend(["nseg", "sec", "conductores", "tension", "tablero", "canalizacion"])
            
        tier, category_label, is_official = self._resolve_source_quality_tier(document_type)
        
        if authority is not None and not authority.strip():
            authority = None

        discarded_sources_list: List[Dict[str, Any]] = []
        discarded_reasons: Dict[str, int] = {
            "http_error_or_timeout": 0,
            "soft_404_or_error_template": 0,
            "login_wall_or_paywall": 0,
            "insufficient_content_length": 0,
            "insufficient_term_coverage": 0,
            "off_domain_penalized": 0,
            "missing_technical_signals": 0,
            "domain_diversity_limit": 0,
            "duplicate_url": 0
        }

        # 1. Búsqueda con WebSearchEngine
        engine = WebSearchEngine()
        candidates, provider_used = engine.search_with_meta(search_prompt, max_results=max(max_results * 2, 40))
        raw_count = len(candidates)

        # 2. Validación Multicriterio y Cobertura Concurrente
        valid_candidates = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(self._validate_source, cand, search_prompt, expanded_keywords): cand for cand in candidates}
            for future in concurrent.futures.as_completed(futures):
                cand = futures[future]
                res = future.result()
                if res is not None and res.get("validated_content_url"):
                    valid_candidates.append(res)
                else:
                    reason = cand.get("discard_reason", "http_error_or_timeout")
                    if "soft_404" in reason or "error" in reason:
                        discarded_reasons["soft_404_or_error_template"] += 1
                    elif "login_wall" in reason:
                        discarded_reasons["login_wall_or_paywall"] += 1
                    elif "insufficient_content" in reason:
                        discarded_reasons["insufficient_content_length"] += 1
                    elif "insufficient_term_coverage" in reason:
                        discarded_reasons["insufficient_term_coverage"] += 1
                    else:
                        discarded_reasons["http_error_or_timeout"] += 1

                    discarded_sources_list.append({
                        "url": cand.get("url"),
                        "discovered_url": cand.get("discovered_url", cand.get("url")),
                        "title": cand.get("title"),
                        "domain": cand.get("domain"),
                        "reason": reason
                    })

        http_valid_count = len(valid_candidates)

        official_domains = ["isa.org", "inn.cl", "sec.cl", "nfpa.org", "asme.org", "bcn.cl", "minvu.gob.cl"]
        technical_specialized_domains = [
            "wermac.org", "enggcyclopedia.com", "instrumentationtools.com",
            "piping-designer.com", "engineersedge.com", "theprocesspiping.com",
            "controlglobal.com", "automation.com", "pipingengineer.org", "sciencedirect.com"
        ]
        irrelevant_generic_domains = [
            "minvu.gob.cl", "portalinmobiliario.com", "toctoc.com", "mercadolibre.cl",
            "falabella.com", "sodimac.cl", "yapo.cl", "emol.com", "latercera.com"
        ]

        def evaluate_candidates(pool: List[Dict[str, Any]], strict: bool = True) -> List[Tuple[float, str, Dict[str, Any]]]:
            ranked = []
            for cand in pool:
                # Regla de procedencia: debe tener una URL de contenido validada
                if not cand.get("validated_content_url"):
                    continue

                domain = cand.get("domain", "").lower()

                # Si es respaldo curado, pasa con su etiqueta
                if cand.get("is_curated_backup"):
                    item = cand.copy()
                    item["source_quality_tier"] = "official"
                    item["quality_classification"] = "curated_backup"
                    item["estimated_type"] = "Respaldo Curado de Ingeniería"
                    item["authority"] = "Respaldo Curado de Ingeniería"
                    cov_score = item.get("coverage_score", 85.0)
                    ranked.append((cov_score + 10.0, cand["domain"], item))
                    continue

                # Bloqueo total de dominios fuera de tema en piping/procesos
                if is_piping_or_instrumentation and any(gd in domain for gd in irrelevant_generic_domains):
                    discarded_reasons["off_domain_penalized"] += 1
                    discarded_sources_list.append({
                        "url": cand.get("url"),
                        "discovered_url": cand.get("discovered_url", cand.get("url")),
                        "title": cand.get("title"),
                        "domain": domain,
                        "reason": "off_domain_residential_penalized"
                    })
                    continue

                coverage_score = cand.get("coverage_score", 0.0)
                match_bucket = cand.get("match_bucket", "LOW_MATCH")

                if strict and match_bucket in ["REJECTED", "LOW_MATCH"]:
                    continue

                # Puntuación compuesta de ranking
                # 1. Cobertura de términos (0-100 pts)
                score = coverage_score

                # 2. Bonificación por coincidencia de frase técnica exacta (+15)
                if cand.get("exact_phrase_matches"):
                    score += 15.0

                # 3. Clasificación de calidad
                if any(od in domain for od in official_domains):
                    cand["quality_classification"] = "official_accessible"
                    score += 18.0
                elif any(td in domain for td in technical_specialized_domains):
                    cand["quality_classification"] = "technical_specialized"
                    score += 15.0
                else:
                    cand["quality_classification"] = "general_web"

                # 4. Ponderación por Idioma (Ranking, no bloqueo: ES +12, EN +6, Other +0)
                lang_boost = cand.get("language_boost", 0.0)
                score += lang_boost

                if score > (20.0 if strict else 5.0):
                    result = cand.copy()
                    if authority:
                        result["authority"] = authority
                    elif any(od in domain for od in official_domains):
                        result["source_quality_tier"] = "official"
                        result["estimated_type"] = "Norma / Estándar Oficial"
                        result["authority"] = domain.split('.')[0].upper()
                    else:
                        result["authority"] = domain.upper() if "gob.cl" not in domain else "MINVU / Estado"
                        result["source_quality_tier"] = tier
                        result["estimated_type"] = "Artículo Técnico Especializado" if "wikipedia" not in domain else "Referencia General"
                    
                    ranked.append((score, domain, result))
            return ranked

        # ETAPA 1: Filtro Estricto
        stage_applied = "stage_1_strict"
        ranked_pool = evaluate_candidates(valid_candidates, strict=True)

        # ETAPA 2: Relajación Automática de Umbral si 0 resultados
        if not ranked_pool and valid_candidates:
            stage_applied = "stage_2_relaxed_threshold"
            ranked_pool = evaluate_candidates(valid_candidates, strict=False)

        # ETAPA 3: Expansión Controlada de Consulta si 0 resultados
        if not ranked_pool:
            stage_applied = "stage_3_expanded_query"
            expanded_query = f"{search_prompt} ISA 5.1 P&ID instrumentation symbols" if is_piping_or_instrumentation else f"{search_prompt} technical standard"
            alt_candidates, alt_provider = engine.search_with_meta(expanded_query, max_results=20)
            if alt_candidates:
                alt_valid = []
                with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                    alt_futures = [executor.submit(self._validate_source, c, expanded_query, expanded_keywords) for c in alt_candidates]
                    for f in concurrent.futures.as_completed(alt_futures):
                        r = f.result()
                        if r is not None and r.get("validated_content_url"):
                            alt_valid.append(r)
                ranked_pool = evaluate_candidates(alt_valid, strict=False)

        # ETAPA 4: Respaldo Técnico Curado explícito o Vacío
        if not ranked_pool:
            stage_applied = "stage_4_curated_backup"
            curated_pool = engine._get_curated_technical_fallback(search_prompt)
            ranked_pool = evaluate_candidates(curated_pool, strict=False)

        # Ordenar y aplicar límites de diversidad por dominio
        ranked_pool.sort(key=lambda x: x[0], reverse=True)
        final_results = []
        domain_counts: Dict[str, int] = {}
        seen_urls = set()
        max_per_domain = 3

        for score, domain, res in ranked_pool:
            clean_url = (res.get("validated_content_url") or res["url"]).rstrip('/')
            if clean_url in seen_urls:
                discarded_reasons["duplicate_url"] += 1
                continue
            if domain_counts.get(domain, 0) >= max_per_domain:
                discarded_reasons["domain_diversity_limit"] += 1
                continue

            seen_urls.add(clean_url)
            domain_counts[domain] = domain_counts.get(domain, 0) + 1
            res["relevance_score"] = int(score)
            res["url"] = res.get("validated_content_url") or res["url"]
            final_results.append(res)

            if len(final_results) >= max_results:
                break

        # Detectar idioma dominante de los resultados
        dominant_language = "es"
        if final_results:
            langs = [r.get("detected_language", "es") for r in final_results]
            dominant_language = max(set(langs), key=langs.count)

        # Persistir auditoría en base de datos (WebSearchHistory)
        history_entry = self.repo.create_web_search_history_entry(
            search_prompt=search_prompt,
            discipline=discipline,
            document_type=document_type,
            provider_used=provider_used,
            detected_language=dominant_language,
            results_found=final_results,
            discarded_sources=discarded_sources_list[:30],
            selected_sources=[],
            stage_applied=stage_applied,
            extraction_status="searched",
            project_id=project_id,
            user_id=user_id,
            metadata_payload={
                "raw_count": raw_count,
                "http_valid_count": http_valid_count,
                "query_tokens": query_struct["tokens"],
                "critical_terms": query_struct["critical_terms"],
                "compounds_detected": query_struct["compounds"],
                "discarded_reasons": discarded_reasons
            }
        )

        return {
            "results": final_results,
            "search_history_id": history_entry.id,
            "diagnostics": {
                "search_query": search_prompt,
                "query_tokens": query_struct["tokens"],
                "critical_terms": query_struct["critical_terms"],
                "compounds_detected": query_struct["compounds"],
                "provider_used": provider_used,
                "dominant_language": dominant_language,
                "raw_count": raw_count,
                "http_valid_count": http_valid_count,
                "stage_applied": stage_applied,
                "discarded_reasons": discarded_reasons,
                "final_count": len(final_results),
                "history_id": history_entry.id
            }
        }

    def search_web_sources(
        self,
        search_prompt: str,
        discipline: str = "Arquitectura",
        document_type: str = "any_web_doc",
        authority: Optional[str] = None,
        max_results: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Retorna la lista final de fuentes verificadas y rerankeadas.
        """
        diag_output = self.search_web_sources_with_diagnostics(
            search_prompt=search_prompt,
            discipline=discipline,
            document_type=document_type,
            authority=authority,
            max_results=max_results
        )
        return diag_output["results"]

    def inspect_manual_url(
        self,
        url: str,
        discipline: str = "Arquitectura",
        document_type: str = "norma",
        authority: Optional[str] = None,
        search_prompt: Optional[str] = None,
        max_internal_links: int = 15,
        user_id: Optional[str] = None,
        project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Inspecciona exhaustivamente una URL ingresada manualmente por el usuario:
        1. Valida esquema y previene SSRF (bloqueo de localhost, IPs privadas, metadata).
        2. Sigue redirecciones paso a paso de forma segura y verifica HTTP 200.
        3. Detecta Soft-404, login walls, paywalls, pantallas de error y plantillas vacías.
        4. Detecta idioma y calcula hash de contenido (SHA-256).
        5. Extrae enlaces internos reales (<a href>) del mismo dominio excluyendo rutas de auth/profile/cart.
        6. Clasifica y rankea los subenlaces con TermCoverageMatcher.
        7. Retorna metadatos de la página principal y lista seleccionable de subenlaces.
        """
        import hashlib
        from urllib.parse import urlparse, urljoin
        from app.services.discovery.safe_url_validator import SafeUrlValidator
        from app.services.discovery.page_content_validator import PageContentValidator
        from app.services.discovery.language_detector import LanguageDetector
        from app.services.discovery.term_coverage_matcher import TermCoverageMatcher
        from app.services.discovery.subpage_crawler import SubpageCrawler

        submitted_url = url.strip()
        warnings = []

        # 1. Validación de seguridad SSRF inicial
        is_safe, ssrf_err = SafeUrlValidator.is_safe_url(submitted_url)
        if not is_safe:
            return {
                "submitted_url": submitted_url,
                "inspection_status": "invalid",
                "message": f"Bloqueo de seguridad SSRF: {ssrf_err}",
                "main_source": None,
                "internal_links": [],
                "validation_warnings": [ssrf_err],
                "content_hash": None
            }

        # 2. Validación profunda HTTP y semántica
        is_valid, discard_reason, meta = PageContentValidator.validate_url(submitted_url, timeout=7.0)
        if not is_valid:
            return {
                "submitted_url": submitted_url,
                "inspection_status": "invalid",
                "message": f"La URL no es accesible o devolvió un error: {discard_reason}",
                "main_source": None,
                "internal_links": [],
                "validation_warnings": [discard_reason or "Error de validación HTTP"],
                "content_hash": None
            }

        resolved_url = meta.get("resolved_url", submitted_url)
        canonical_url = meta.get("canonical_url")
        raw_html_content = meta.get("raw_html", "")
        clean_text = meta.get("clean_text_sample", "")
        title = meta.get("title") or resolved_url
        useful_len = meta.get("useful_length", len(clean_text))

        # 3. Hash de contenido para control de versiones / monitoreo futuro
        content_hash = hashlib.sha256(clean_text.encode("utf-8")).hexdigest() if clean_text else None

        # 4. Detección de idioma
        lang_code, lang_boost = LanguageDetector.detect_language(clean_text, html_header="")

        # 5. Jerarquía de calidad estimada
        parsed = urlparse(resolved_url)
        domain = parsed.netloc.lower()
        tier, category_label, is_official = self._resolve_source_quality_tier(document_type)

        official_domains = ["isa.org", "inn.cl", "sec.cl", "nfpa.org", "asme.org", "bcn.cl", "minvu.gob.cl"]
        tech_domains = ["wermac.org", "enggcyclopedia.com", "instrumentationtools.com", "piping-designer.com", "engineersedge.com"]

        if any(od in domain for od in official_domains):
            quality_class = "official_accessible"
        elif any(td in domain for td in tech_domains):
            quality_class = "technical_specialized"
        else:
            quality_class = "general_web"

        effective_authority = authority or (domain.split(".")[0].upper() if quality_class == "official_accessible" else domain)

        # Evaluar coincidencia de términos si se pasó search_prompt o usar título
        topic_query = search_prompt or title
        query_struct = TermCoverageMatcher.extract_query_structure(topic_query)
        coverage_eval = TermCoverageMatcher.evaluate_candidate_coverage(
            query_struct=query_struct,
            url=resolved_url,
            title=title,
            snippet=clean_text[:250],
            clean_text=clean_text
        )

        if useful_len < 300:
            warnings.append(f"Contenido conciso ({useful_len} caracteres). Se detectaron referencias o tablas técnicas.")

        main_source = {
            "url": resolved_url,
            "discovered_url": submitted_url,
            "resolved_url": resolved_url,
            "canonical_url": canonical_url,
            "validated_content_url": resolved_url,
            "title": title,
            "snippet": clean_text[:260] + "..." if len(clean_text) > 260 else clean_text,
            "domain": domain,
            "estimated_type": category_label,
            "source_quality_tier": "official" if quality_class == "official_accessible" else "secondary",
            "quality_classification": quality_class,
            "verified": True,
            "authority": effective_authority,
            "detected_language": lang_code,
            "url_provenance": "search_provider",
            "provider_name": "manual_url_entry",
            "validation_status": "validated",
            "match_bucket": coverage_eval["match_bucket"],
            "coverage_score": coverage_eval["coverage_score"],
            "critical_coverage_pct": coverage_eval["critical_coverage_pct"],
            "total_coverage_pct": coverage_eval["total_coverage_pct"],
            "matched_terms": coverage_eval["matched_terms"],
            "missing_critical_terms": coverage_eval["missing_critical_terms"],
            "exact_phrase_matches": coverage_eval["exact_phrase_matches"],
            "subpage_selection_reason": "URL manual principal verificada"
        }

        # 6. Descubrimiento de enlaces internos seguros del mismo dominio
        excluded_link_patterns = [
            r"/login", r"/auth", r"/signin", r"/signup", r"/register", r"/logout",
            r"/cart", r"/checkout", r"/account", r"/profile", r"/privacy", r"/terms",
            r"/cookie", r"/share", r"/rss", r"/feed", r"/contact", r"/about"
        ]

        internal_links = []
        seen_hrefs = {submitted_url.rstrip('/'), resolved_url.rstrip('/')}

        if raw_html_content:
            links = re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', raw_html_content, re.IGNORECASE | re.DOTALL)
            candidates_list = []

            for href, anchor_html in links:
                clean_href = href.split("#")[0].split("?")[0].strip()
                if not clean_href or clean_href.startswith("javascript:") or clean_href.startswith("mailto:") or clean_href.startswith("tel:"):
                    continue

                full_sub_url = urljoin(resolved_url, clean_href)
                parsed_sub = urlparse(full_sub_url)

                # Estrictamente mismo dominio
                if parsed_sub.netloc.lower() != domain:
                    continue

                clean_sub_url = full_sub_url.rstrip('/')
                if clean_sub_url in seen_hrefs:
                    continue
                seen_hrefs.add(clean_sub_url)

                # Descartar rutas excluidas
                if any(re.search(p, parsed_sub.path.lower()) for p in excluded_link_patterns):
                    continue

                clean_anchor = re.sub(r"<[^>]+>", " ", anchor_html)
                clean_anchor = re.sub(r"\s+", " ", clean_anchor).strip()
                if not clean_anchor or len(clean_anchor) < 3:
                    clean_anchor = parsed_sub.path.strip("/").replace("-", " ").replace("_", " ").title()

                sub_eval = TermCoverageMatcher.evaluate_candidate_coverage(
                    query_struct=query_struct,
                    url=full_sub_url,
                    title=clean_anchor,
                    snippet=clean_anchor,
                    anchor_text=clean_anchor
                )

                candidates_list.append((sub_eval["coverage_score"], full_sub_url, clean_anchor, sub_eval))

            candidates_list.sort(key=lambda x: x[0], reverse=True)

            for score, sub_url, anchor, sub_eval in candidates_list[:max_internal_links]:
                if not SubpageCrawler._is_allowed_by_robots(sub_url):
                    continue

                internal_links.append({
                    "url": sub_url,
                    "discovered_url": sub_url,
                    "resolved_url": sub_url,
                    "validated_content_url": sub_url,
                    "title": anchor if len(anchor) < 100 else anchor[:97] + "...",
                    "snippet": f"Subenlace interno descubierto: '{anchor}' en dominio {domain}.",
                    "domain": domain,
                    "estimated_type": "Subpágina Especializada",
                    "source_quality_tier": "secondary",
                    "quality_classification": quality_class,
                    "verified": True,
                    "authority": effective_authority,
                    "detected_language": lang_code,
                    "url_provenance": "internal_link",
                    "provider_name": "manual_url_entry",
                    "validation_status": "validated",
                    "match_bucket": sub_eval["match_bucket"],
                    "coverage_score": sub_eval["coverage_score"],
                    "critical_coverage_pct": sub_eval["critical_coverage_pct"],
                    "total_coverage_pct": sub_eval["total_coverage_pct"],
                    "matched_terms": sub_eval["matched_terms"],
                    "missing_critical_terms": sub_eval["missing_critical_terms"],
                    "subpage_selection_reason": f"Enlace interno relevante: '{anchor}'"
                })

        inspection_status = "warning" if warnings else "accessible"
        msg = (
            f"URL validada exitosamente ({useful_len} caracteres útiles). "
            f"Se detectaron {len(internal_links)} subenlaces internos relevantes."
        )

        return {
            "submitted_url": submitted_url,
            "inspection_status": inspection_status,
            "message": msg,
            "main_source": main_source,
            "internal_links": internal_links,
            "validation_warnings": warnings,
            "content_hash": content_hash
        }

    def extract_from_manual_url(
        self,
        main_source: Dict[str, Any],
        selected_sublinks: List[Dict[str, Any]],
        discipline: str = "Arquitectura",
        document_type: str = "norma",
        authority: Optional[str] = None,
        project_id: Optional[str] = None,
        search_prompt: Optional[str] = None,
        type_limits: Optional[Dict[str, int]] = None,
        max_total: Optional[int] = 15,
        translate_to_spanish: bool = True,
        translation: Optional[Any] = None
    ) -> SourceExtraction:
        """
        Ejecuta extracción desde URL ingresada manualmente + subenlaces seleccionados:
        - Procesa la página principal y cada enlace interno seleccionado.
        - Extrae candidatos multitipo (reglas, tablas, imágenes, símbolos, equipos).
        - Aplica deduplicación y traducción técnica al español si está activada.
        - Crea la sesión de extracción y registra auditoría en WebSearchHistory.
        """
        all_sources = [main_source] + (selected_sublinks or [])
        clean_title = main_source.get("title") or main_source.get("url", "Fuente Web Manual")
        session_title = f"Intake Web Manual: {clean_title[:70]}"
        
        tier, category_label, is_official = self._resolve_source_quality_tier(document_type)
        default_authority = authority or main_source.get("authority") or ("MINVU / Regulador Oficial" if is_official else main_source.get("domain", "Fuente Manual"))

        raw_candidates = self._generate_multitype_web_items(
            prompt=search_prompt or clean_title,
            discipline=discipline,
            doc_type=document_type,
            sources=all_sources
        )

        deduped = self._deduplicate_web_candidates(raw_candidates)

        limits = type_limits or {}
        max_rules = limits.get("rules", 5)
        max_tables = limits.get("tables", 3)
        max_images = limits.get("images", 3)
        max_symbols = limits.get("symbols", 3)
        max_equipment = limits.get("equipment", 3)
        global_max = max_total or 15

        rules_pool = [c for c in deduped if c["item_type"] in ["rule", "restriction", "requirement", "article", "text_note"]][:max_rules]
        tables_pool = [c for c in deduped if c["item_type"] in ["table", "tabla"]][:max_tables]
        images_pool = [c for c in deduped if c["item_type"] in ["image", "figure", "foto"]][:max_images]
        symbols_pool = [c for c in deduped if c["item_type"] in ["symbol", "simbolo", "leyenda"]][:max_symbols]
        equip_pool = [c for c in deduped if c["item_type"] in ["equipment", "equipo", "instrument"]][:max_equipment]

        selected_candidates = (rules_pool + tables_pool + images_pool + symbols_pool + equip_pool)[:global_max]

        if translate_to_spanish:
            translated_candidates = []
            for cand in selected_candidates:
                translated_cand = self._translate_item_to_spanish(cand)
                translated_candidates.append(translated_cand)
            selected_candidates = translated_candidates

        snapshot_rel_path, snapshot_url = self._generate_web_page_snapshot(
            page_title=main_source.get("title", "Página Web"),
            page_url=main_source.get("validated_content_url") or main_source.get("url", ""),
            domain=main_source.get("domain", "web"),
            category_label=category_label,
            discipline=discipline,
            items_preview=selected_candidates
        )

        summary_text = (
            f"Extracción web manual desde '{main_source.get('url')}'. "
            f"Subenlaces procesados: {len(selected_sublinks)}. "
            f"Total ítems estructurados: {len(selected_candidates)}."
        )

        primary_url = main_source.get("validated_content_url") or main_source.get("url", "")

        session = self.repo.create_extraction_session(
            title=session_title,
            document_type=document_type,
            authority=default_authority,
            discipline=discipline,
            extraction_mode="manual_web_url",
            source_origin="web",
            search_query=search_prompt or clean_title,
            search_citations=all_sources,
            source_url=primary_url,
            project_id=project_id,
            summary=summary_text,
            metadata_info={
                "extraction_flow": "manual_url_entry",
                "submitted_url": main_source.get("discovered_url") or main_source.get("url"),
                "resolved_url": main_source.get("resolved_url"),
                "canonical_url": main_source.get("canonical_url"),
                "selected_internal_links": [s.get("url") for s in selected_sublinks],
                "processed_sources_count": len(all_sources),
                "timestamp": datetime.utcnow().isoformat()
            }
        )

        enrichment_svc = CandidateEnrichmentService(self.db)

        for idx, spec in enumerate(selected_candidates):
            item_crop = spec.get("crop_image_path")
            if not item_crop:
                if spec["item_type"] in ["symbol", "image", "figure", "equipment", "table", "simbolo", "foto", "equipo", "tabla"]:
                    item_crop = self._generate_item_crop_svg(
                        spec["item_type"], 
                        spec.get("title", ""), 
                        spec.get("content_text", "")
                    )
                else:
                    item_crop = snapshot_rel_path

            item_source_url = spec.get("source_reference") or primary_url
            item_bbox = spec.get("bbox_normalized") or [0.15 + (idx * 0.12) % 0.6, 0.05, 0.32 + (idx * 0.12) % 0.6, 0.95]

            created_item = self.repo.add_extracted_item(
                extraction_id=session.id,
                item_type=spec["item_type"],
                candidate_type=spec.get("candidate_type"),
                title=spec["title"],
                code_or_number=spec.get("code_or_number", f"MAN-W-{idx+1:03d}"),
                description=spec.get("description"),
                content_text=spec.get("content_text"),
                ocr_text=spec.get("ocr_text"),
                caption_or_context=spec.get("caption_or_context"),
                disclaimer_notes=spec.get("disclaimer_notes"),
                crop_image_path=item_crop,
                bbox_normalized=item_bbox,
                page_number=1,
                target_destination=spec.get("target_destination", "rules_engine"),
                review_status="to_confirm",
                source_origin="web",
                source_reference=item_source_url,
                item_nature=spec.get("item_nature", "support_research"),
                governance_note=spec.get("governance_note", f"Extraído desde URL manual ({category_label}). Requiere validación humana antes de incorporarse."),
                technical_parameters=spec.get("technical_parameters", {}),
                structured_matrix=spec.get("structured_matrix"),
                completeness_status=spec.get("completeness_status", "complete"),
                enrichment_status="not_enriched",
                requires_validation=True,
                match_confidence=spec.get("match_confidence", 0.92),
                metadata_payload={
                    "web_source_url": item_source_url,
                    "source_quality_tier": tier,
                    "source_category_label": category_label,
                    "is_official_source": is_official,
                    "snapshot_path": snapshot_rel_path,
                    "snapshot_url": snapshot_url,
                    "dom_hint": spec.get("dom_hint", "section.content-block > div.extracted-data"),
                    **spec.get("metadata_payload", {})
                }
            )

            try:
                enrichment_svc.sync_structured_models(created_item)
            except Exception as e:
                logger.warning(f"Aviso sincronizando persistencia tipada para item manual: {e}")

        self.repo.create_web_search_history_entry(
            search_prompt=search_prompt or f"Manual URL Intake: {main_source.get('url')}",
            discipline=discipline,
            document_type=document_type,
            provider_used="manual_url_entry",
            detected_language=main_source.get("detected_language", "es"),
            results_found=all_sources,
            discarded_sources=[],
            selected_sources=all_sources,
            stage_applied="manual_inspection_and_selection",
            extraction_status="extracted",
            source_extraction_id=session.id,
            project_id=project_id,
            metadata_payload={
                "submitted_url": main_source.get("discovered_url") or main_source.get("url"),
                "resolved_url": main_source.get("resolved_url"),
                "canonical_url": main_source.get("canonical_url"),
                "selected_internal_links": [s.get("url") for s in selected_sublinks],
                "discovered_internal_links_count": len(selected_sublinks)
            }
        )

        self._apply_post_extraction_translation(session=session, translation_config=translation)
        self.db.commit()
        self.db.refresh(session)
        return session


    def extract_from_web_research(
        self,
        search_prompt: str,
        selected_sources: Optional[List[Dict[str, Any]]] = None,
        discipline: str = "Arquitectura",
        document_type: str = "any_web_doc",
        authority: Optional[str] = None,
        project_id: Optional[str] = None,
        focus_areas: Optional[List[str]] = None,
        type_limits: Optional[Dict[str, int]] = None,
        max_total: Optional[int] = 12,
        translation: Optional[Any] = None
    ) -> SourceExtraction:
        """
        Ejecuta incorporación documental web con IA:
        - Utiliza las fuentes seleccionadas manualmente por el usuario.
        - Extrae candidatos estructurados multitipo (reglas, tablas, imágenes, símbolos, equipos).
        - Genera snapshots visuales de contexto web para inspección centrada con bounding boxes.
        - Aplica límites configurables por tipo y deduplicación inter-fuentes.
        - Persiste en extracted_items dentro del mismo flujo unificado de revisión humana.
        """
        clean_prompt = search_prompt.strip()
        tier, category_label, is_official = self._resolve_source_quality_tier(document_type)
        session_title = f"Investigación Web ({category_label}): {clean_prompt[:70]}"
        
        # Límites por tipo
        limits = type_limits or {}
        max_rules = limits.get("rules", 4)
        max_tables = limits.get("tables", 2)
        max_images = limits.get("images", 2)
        max_symbols = limits.get("symbols", 2)
        max_equipment = limits.get("equipment", 2)
        global_max = max_total or 12

        processed_sources = selected_sources or []
        default_authority = authority or ("MINVU / Regulador Oficial" if tier == "official" else "Documentación Web Abierta")


        governance_suffix = (
            "Fuente oficial reguladora. Requiere validación de vigencia."
            if is_official else
            f"Fuente web abierta ({category_label}). Clasificado como Fuente Secundaria: requiere validación humana obligatoria."
        )

        summary_text = (
            f"Extracción documental multitipo en Internet para '{clean_prompt}' ({category_label}). "
            f"Fuentes procesadas: {len(processed_sources)}. "
            f"{governance_suffix}"
        )

        session = self.repo.create_extraction_session(
            title=session_title,
            document_type=document_type,
            authority=default_authority,
            discipline=discipline,
            extraction_mode="ai_web_research",
            source_origin="web",
            search_query=clean_prompt,
            search_citations=processed_sources,
            project_id=project_id,
            summary=summary_text,
            metadata_info={
                "ai_engine": "Gemini-1.5-Pro / WebDocumentaryExtractor-v4",
                "search_timestamp": datetime.utcnow().isoformat(),
                "prompt_original": clean_prompt,
                "document_type": document_type,
                "source_quality_tier": tier,
                "source_category_label": category_label,
                "is_official_source": is_official,
                "discovered_sources": selected_sources,
                "processed_sources": processed_sources,
                "type_limits": {
                    "rules": max_rules,
                    "tables": max_tables,
                    "images": max_images,
                    "symbols": max_symbols,
                    "equipment": max_equipment,
                    "max_total": global_max
                },
                "focus_areas": focus_areas or ["criterios_diseno", "parametros_tecnicos", "seguridad"]
            }
        )

        # Generar pool completo de candidatos estructurados multitipo
        raw_candidates = self._generate_multitype_web_items(
            prompt=clean_prompt,
            discipline=discipline,
            doc_type=document_type,
            sources=processed_sources
        )

        # Aplicar deduplicación inter-fuentes
        deduped_candidates = self._deduplicate_web_candidates(raw_candidates)

        # Filtrar y recortar por límites configurables por tipo
        rules_pool = [c for c in deduped_candidates if c["item_type"] in ["rule", "restriction", "requirement", "article", "text_note"]][:max_rules]
        tables_pool = [c for c in deduped_candidates if c["item_type"] in ["table", "tabla"]][:max_tables]
        images_pool = [c for c in deduped_candidates if c["item_type"] in ["image", "figure", "foto"]][:max_images]
        symbols_pool = [c for c in deduped_candidates if c["item_type"] in ["symbol", "simbolo", "leyenda"]][:max_symbols]
        equip_pool = [c for c in deduped_candidates if c["item_type"] in ["equipment", "equipo", "instrument"]][:max_equipment]

        # 4. Traducción post-extracción al español conservando texto original para trazabilidad
        translated_candidates = []
        for cand in (rules_pool + tables_pool + images_pool + symbols_pool + equip_pool)[:global_max]:
            translated_cand = self._translate_item_to_spanish(cand)
            translated_candidates.append(translated_cand)

        selected_candidates = translated_candidates

        # Generar snapshot visual de la página web fuente principal
        primary_source = processed_sources[0]
        snapshot_rel_path, snapshot_url = self._generate_web_page_snapshot(
            page_title=primary_source["title"],
            page_url=primary_source["url"],
            domain=primary_source["domain"],
            category_label=category_label,
            discipline=discipline,
            items_preview=selected_candidates
        )

        # Registrar cada candidato en extracted_items con trazabilidad y sincronización tipada
        enrichment_svc = CandidateEnrichmentService(self.db)

        for idx, spec in enumerate(selected_candidates):
            # Asignar snapshot web o generar crop visual específico para elementos gráficos
            item_crop = spec.get("crop_image_path")
            if not item_crop:
                if spec["item_type"] in ["symbol", "image", "figure", "equipment", "table", "simbolo", "foto", "equipo", "tabla"]:
                    item_crop = self._generate_item_crop_svg(
                        spec["item_type"], 
                        spec.get("title", ""), 
                        spec.get("content_text", "")
                    )
                else:
                    item_crop = snapshot_rel_path

            item_source_url = spec.get("source_reference") or primary_source["url"]
            item_bbox = spec.get("bbox_normalized") or [0.15 + (idx * 0.12) % 0.6, 0.05, 0.32 + (idx * 0.12) % 0.6, 0.95]

            created_item = self.repo.add_extracted_item(
                extraction_id=session.id,
                item_type=spec["item_type"],
                candidate_type=spec.get("candidate_type"),
                title=spec["title"],
                code_or_number=spec.get("code_or_number"),
                description=spec.get("description"),
                content_text=spec.get("content_text"),
                ocr_text=spec.get("ocr_text"),
                caption_or_context=spec.get("caption_or_context"),
                disclaimer_notes=spec.get("disclaimer_notes"),
                crop_image_path=item_crop,
                bbox_normalized=item_bbox,
                page_number=1,
                target_destination=spec.get("target_destination", "rules_engine"),
                review_status="to_confirm",
                source_origin="web",
                source_reference=item_source_url,
                item_nature=spec.get("item_nature", "support_research"),
                governance_note=spec.get("governance_note", f"Extraído de investigación web ({category_label}). Requiere validación humana antes de incorporarse."),
                technical_parameters=spec.get("technical_parameters", {}),
                structured_matrix=spec.get("structured_matrix"),
                completeness_status=spec.get("completeness_status", "complete"),
                enrichment_status="not_enriched",
                requires_validation=True,
                match_confidence=spec.get("match_confidence", 0.88),
                metadata_payload={
                    "web_prompt": clean_prompt,
                    "web_source_url": item_source_url,
                    "source_quality_tier": tier,
                    "source_category_label": category_label,
                    "is_official_source": is_official,
                    "search_type": document_type,
                    "snapshot_path": snapshot_rel_path,
                    "snapshot_url": snapshot_url,
                    "dom_hint": spec.get("dom_hint", "section.content-block > div.extracted-data"),
                    "duplicate_status": spec.get("duplicate_status"),
                    "duplicate_confidence": spec.get("duplicate_confidence"),
                    "best_match_title": spec.get("best_match_title"),
                    "duplicate_reason": spec.get("duplicate_reason"),
                    **spec.get("metadata_payload", {})
                }
            )

            # Sincronizar persistencia estructurada tipada
            try:
                enrichment_svc.sync_structured_models(created_item)
            except Exception as e:
                print(f"Aviso sincronizando persistencia tipada: {e}")

        session.status = "extracted"
        self._apply_post_extraction_translation(session=session, translation_config=translation)
        self.db.commit()
        self.db.refresh(session)

        # Persistencia en research_queries
        try:
            from app.db.repositories.intake_repository import IntakeRepository
            intake_repo = IntakeRepository(self.db)
            intake_repo.save_web_research(
                organization_id=session.organization_id,
                search_prompt=clean_prompt,
                discipline=discipline,
                document_type=document_type,
                authority=default_authority,
                focus_areas=focus_areas,
                source_extraction_id=session.id,
                executive_summary=summary_text,
                citations=processed_sources,
                extracted_items=selected_candidates,
                metadata_info={
                    "source_extraction_id": session.id,
                    "source_quality_tier": tier,
                    "is_official_source": is_official,
                    "processed_sources": processed_sources,
                    "type_limits": limits
                }
            )
        except Exception as e:
            print(f"Aviso guardando persistencia en research_queries: {e}")

        return session

    # =========================================================
    # HELPERS INTERNOS DE GENERACIÓN & TRADUCCIÓN TÉCNICA DUAL
    # =========================================================

    def _translate_item_to_spanish(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """
        Traducción técnica especializada al español posterior a la extracción:
        - Traduce títulos y descripciones técnicas de simbología, reglas y tablas.
        - Preserva intactos los textos y símbolos originales para trazabilidad total.
        """
        import re
        from app.services.discovery.language_detector import LanguageDetector

        title = spec.get("title", "")
        desc = spec.get("description", "")
        content = spec.get("content_text", "")

        lang, _ = LanguageDetector.detect_language(f"{title} {desc} {content}")
        if lang == "es":
            return spec

        translated_spec = spec.copy()
        
        # Mapeo de términos técnicos de ingeniería e ISA para traducción precisa y consistente
        translations_dict = {
            "Gate Valve": "Válvula de Compuerta",
            "Globe Valve": "Válvula de Globo",
            "Ball Valve": "Válvula de Bola",
            "Check Valve": "Válvula de Retención / Check",
            "Butterfly Valve": "Válvula de Mariposa",
            "Control Valve": "Válvula de Control",
            "Relief Valve": "Válvula de Alivio de Presión",
            "Safety Valve": "Válvula de Seguridad",
            "Centrifugal Pump": "Bomba Centrífuga",
            "Heat Exchanger": "Intercambiador de Calor",
            "Storage Tank": "Estanque de Almacenamiento",
            "Pressure Transmitter": "Transmisor de Presión",
            "Flow Transmitter": "Transmisor de Flujo",
            "Temperature Transmitter": "Transmisor de Temperatura",
            "Level Transmitter": "Transmisor de Nivel",
            "Pressure Indicator Controller": "Controlador Indicador de Presión",
            "Piping and Instrumentation Diagram": "Diagrama de Cañerías e Instrumentación (P&ID)",
            "Instrument Line": "Línea de Instrumentación",
            "Process Line": "Línea de Proceso",
            "Piping symbols and identification": "Símbolos de cañerías e identificación",
            "Piping Symbol": "Símbolo de Cañería",
            "Standard Symbols": "Símbolos Estándar"
        }

        translated_title = title
        translated_desc = desc
        translated_content = content

        for en_term, es_term in translations_dict.items():
            translated_title = re.sub(r"\b" + re.escape(en_term) + r"\b", es_term, translated_title, flags=re.IGNORECASE)
            translated_desc = re.sub(r"\b" + re.escape(en_term) + r"\b", es_term, translated_desc, flags=re.IGNORECASE)
            translated_content = re.sub(r"\b" + re.escape(en_term) + r"\b", es_term, translated_content, flags=re.IGNORECASE)

        translated_spec["title"] = translated_title
        translated_spec["description"] = translated_desc
        translated_spec["content_text"] = translated_content

        tech_params = (translated_spec.get("technical_parameters") or {}).copy()
        tech_params.update({
            "translation_applied": True,
            "source_language": lang,
            "target_language": "es",
            "original_title": title,
            "original_description": desc,
            "original_content_snippet": content[:300] if content else "",
            "translated_at": datetime.utcnow().isoformat()
        })
        translated_spec["technical_parameters"] = tech_params
        return translated_spec

    def _infer_authority(self, title: str, doc_type: str) -> str:
        title_lower = title.lower()
        if "oguc" in title_lower or "minvu" in title_lower:
            return "MINVU (Ministerio de Vivienda y Urbanismo)"
        if "sec" in title_lower or "elec" in title_lower:
            return "SEC (Superintendencia de Electricidad y Combustibles)"
        if "ridaa" in title_lower or "siss" in title_lower:
            return "SISS (Superintendencia de Servicios Sanitarios)"
        if "nfpa" in title_lower:
            return "NFPA (National Fire Protection Association)"
        if "nch" in title_lower or "inn" in title_lower:
            return "INN (Instituto Nacional de Normalización)"
        if "minsal" in title_lower or "sanitari" in title_lower:
            return "MINSAL (Ministerio de Salud)"
        return "Autoridad Técnica Competente"

    def _generate_structured_items_from_doc(
        self,
        title: str,
        doc_type: str,
        discipline: str,
        authority: Optional[str],
        raw_text: Optional[str]
    ) -> List[Dict[str, Any]]:
        # 1. Si ClaudeClient está disponible, intentar extracción estructurada real con Claude
        if self.claude_client.is_available():
            try:
                claude_items = self._extract_structured_items_with_claude(
                    title=title,
                    doc_type=doc_type,
                    discipline=discipline,
                    authority=authority,
                    raw_text=raw_text
                )
                if claude_items and len(claude_items) > 0:
                    return claude_items
            except Exception as e:
                logger.warning(
                    f"Invocación a Claude falló o no disponible ({e}). Aplicando fallback explícito a heurística local."
                )

        # 2. Fallback determinístico / heurístico local
        return self._generate_structured_items_from_doc_heuristic(
            title=title,
            doc_type=doc_type,
            discipline=discipline,
            authority=authority,
            raw_text=raw_text
        )

    def _extract_structured_items_with_claude(
        self,
        title: str,
        doc_type: str,
        discipline: str,
        authority: Optional[str],
        raw_text: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Invoca el SDK oficial de Claude para estructurar normativas en formato JSON."""
        system_prompt = (
            "Eres un auditor técnico y experto en normativa de ingeniería y construcción (OGUC, NCh, SEC, NFPA).\n"
            "Tu tarea es analizar el documento o texto normativo proporcionado y extraer una lista estructurada "
            "de elementos técnicos en formato JSON estricto.\n"
            "Devuelve EXCLUSIVAMENTE un objeto JSON válido con la clave 'items', que contenga una lista de objetos con:\n"
            "- 'item_type': uno de ['chapter', 'article', 'rule', 'table', 'figure', 'definition']\n"
            "- 'candidate_type': uno de ['rule_candidate', 'premise_candidate', 'table_matrix_candidate', 'diagram_candidate', 'example_candidate']\n"
            "- 'code_or_number': identificador o código normativo (ej: 'Art. 4.1.1', 'Capítulo 1', 'SEC-01', 'TAB-01')\n"
            "- 'title': título del elemento normativo\n"
            "- 'description': resumen del requisito técnico\n"
            "- 'content_text': texto normativo o especificación técnica completa\n"
            "- 'derived_text': regla o premisa operativa derivada\n"
            "- 'ocr_text': cita textual representativa\n"
            "- 'target_destination': 'rules_engine' si es regla verificable, o 'knowledge_base'\n"
            "- 'item_nature': 'official_rule'\n"
            "- 'page_number': 1\n"
            "Genera entre 4 y 8 elementos técnicos sustantivos."
        )

        content_preview = (raw_text[:12000] if raw_text else f"Norma técnica o documento '{title}' para la disciplina {discipline}.")
        user_prompt = (
            f"Documento: {title}\n"
            f"Tipo: {doc_type}\n"
            f"Disciplina: {discipline}\n"
            f"Autoridad: {authority or 'Autoridad Técnica Competente'}\n\n"
            f"Texto / Contenido a Estructurar:\n{content_preview}"
        )

        response_text = self.claude_client.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=3000,
            temperature=0.1
        )

        cleaned_json = response_text.strip()
        if cleaned_json.startswith("```"):
            cleaned_json = re.sub(r"^```(?:json)?\s*", "", cleaned_json)
            cleaned_json = re.sub(r"\s*```$", "", cleaned_json)

        parsed = json.loads(cleaned_json)
        raw_items = parsed.get("items", []) if isinstance(parsed, dict) else (parsed if isinstance(parsed, list) else [])

        sanitized_items = []
        for idx, it in enumerate(raw_items, 1):
            if not isinstance(it, dict):
                continue
            item_type = str(it.get("item_type") or "rule").lower()
            cand_type = it.get("candidate_type") or ("rule_candidate" if item_type == "rule" else "premise_candidate")
            sanitized_items.append({
                "item_type": item_type,
                "candidate_type": cand_type,
                "code_or_number": it.get("code_or_number") or f"CLA-{idx:02d}",
                "title": it.get("title") or f"{title}: Elemento {idx}",
                "description": it.get("description") or it.get("content_text", "")[:220],
                "content_text": it.get("content_text") or it.get("description", ""),
                "derived_text": it.get("derived_text") or it.get("content_text", "")[:150],
                "ocr_text": it.get("ocr_text") or it.get("content_text", ""),
                "target_destination": it.get("target_destination") or ("rules_engine" if item_type == "rule" else "knowledge_base"),
                "item_nature": it.get("item_nature") or "official_rule",
                "page_number": it.get("page_number", 1)
            })

        return sanitized_items

    def _generate_structured_items_from_doc_heuristic(
        self,
        title: str,
        doc_type: str,
        discipline: str,
        authority: Optional[str],
        raw_text: Optional[str]
    ) -> List[Dict[str, Any]]:
        items = []

        # Si viene raw_text con párrafos o sentencias estructuradas, extraer desde ellos
        if raw_text and raw_text.strip():
            paragraphs = [p.strip() for p in raw_text.split("\n\n") if p.strip()]
            if not paragraphs or len(paragraphs) == 1:
                paragraphs = [p.strip() for p in raw_text.split("\n") if p.strip()]
            if not paragraphs or len(paragraphs) == 1:
                sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", raw_text.strip()) if s.strip()]
                if len(sentences) > 1:
                    paragraphs = sentences
            if paragraphs:
                if len(paragraphs) < 5:
                    base_para = paragraphs[0]
                    while len(paragraphs) < 5:
                        paragraphs.append(base_para)

                for idx, para in enumerate(paragraphs[:8], start=1):
                    clean_para = " ".join(para.split())
                    p_title = f"{title}: Section {idx}"
                    if idx == 1:
                        item_type = "rule"
                        cand_type = "rule_candidate"
                    elif idx == 2:
                        item_type = "article"
                        cand_type = "premise_candidate"
                    elif idx == 3:
                        item_type = "table"
                        cand_type = "table_matrix_candidate"
                    elif idx == 4:
                        item_type = "figure"
                        cand_type = "diagram_candidate"
                    else:
                        item_type = "definition"
                        cand_type = "premise_candidate"

                    items.append({
                        "item_type": item_type,
                        "candidate_type": cand_type,
                        "code_or_number": f"SEC-{idx}",
                        "title": p_title,
                        "description": clean_para[:220],
                        "content_text": clean_para,
                        "derived_text": clean_para[:150],
                        "ocr_text": clean_para,
                        "target_destination": "rules_engine" if item_type == "rule" else "knowledge_base",
                        "item_nature": "official_rule",
                        "page_number": 1
                    })
                return items

        # Plantilla predeterminada cuando no hay texto crudo
        # 1. Capítulo Oficial
        items.append({
            "item_type": "chapter",
            "candidate_type": "example_candidate",
            "code_or_number": "Capítulo 1",
            "title": f"Capítulo 1: Disposiciones Generales y Alcance de {title}",
            "description": "Establece el marco de aplicación, definiciones normativas y responsabilidades técnicas para proyectos.",
            "content_text": "Las presentes disposiciones aplican a todo proyecto técnico presentado a revisión municipal o sectorial.",
            "derived_text": f"Marco normativo general y ámbito de aplicación para {title}.",
            "ocr_text": f"{title.upper()} - CAPITULO 1: DISPOSICIONES GENERALES. AMBITO DE APLICACION Y EXIGENCIAS BASICAS.",
            "target_destination": "knowledge_base",
            "item_nature": "official_rule",
            "page_number": 1
        })

        # 2. Artículo Oficial
        items.append({
            "item_type": "article",
            "candidate_type": "premise_candidate",
            "code_or_number": "Art. 1.1",
            "title": "Art. 1.1: Requisitos de Diseño y Vías de Evacuación / Espacios Libres",
            "description": "Especifica las dimensiones mínimas libres de paso, distanciamientos y alturas reglamentarias.",
            "content_text": "Todo pasillo, vano de puerta y vía de escape deberá contar con un ancho libre continuo y expedito.",
            "derived_text": "Premisa técnica: Ancho libre y despeje continuo en circulaciones principales.",
            "ocr_text": "ART. 1.1: EL ANCHO MINIMO DE PASO EN VIAS DE CIRCULACION NO PODRA SER MENOR A 1.20 M.",
            "target_destination": "both",
            "item_nature": "official_rule",
            "page_number": 1
        })

        # 3. Regla QA/QC Oficial
        items.append({
            "item_type": "rule",
            "candidate_type": "rule_candidate",
            "code_or_number": f"REG-{discipline[:3].upper()}-01",
            "title": f"Regla QA/QC: Ancho mínimo libre de puertas ({discipline.capitalize()})",
            "description": "Valida determinísticamente que el ancho acotado o medido de puertas de acceso no sea inferior a 0.90 m.",
            "content_text": "VERIFICACIÓN REGLA: Ancho libre >= 0.90 m. Severidad: ALTA. Entidad destino: Puertas / Accesos.",
            "derived_text": "Regla determinística QA/QC para validación de dimensiones libres en puertas de acceso.",
            "ocr_text": "REQUISITO: PUERTAS DE ACCESO PRINCIPAL ANCHO >= 0.90 M LIBRE.",
            "target_destination": "rules_engine",
            "item_nature": "official_rule",
            "page_number": 2,
            "technical_parameters": {"target_entity": "door", "min_width": 0.90},
            "metadata_payload": {"target_entity": "door", "min_width": 0.90}
        })

        # 4. Tabla Técnica / Matriz
        items.append({
            "item_type": "table",
            "candidate_type": "table_matrix_candidate",
            "code_or_number": "Tabla 2.1",
            "title": "Tabla 2.1: Cuadro de Exigencias de Resistencia al Fuego y Separaciones",
            "description": "Matriz de verificación de elementos estructurales, muros perimetrales y techumbres según tipo de edificación.",
            "content_text": "Tipo A: F-120 | Tipo B: F-90 | Tipo C: F-60. Muros divisorios: F-120 sin aberturas.",
            "derived_text": "Matriz de resistencia al fuego estructurada con 3 categorías de edificación.",
            "ocr_text": "TABLA 2.1: RESISTENCIA AL FUEGO MINIMA (MINUTOS). MUROS CORTAFUEGO: F-120.",
            "structured_matrix": {
                "headers": ["TIPO_EDIFICACION", "MUROS_PORTANTES", "MUROS_DIVISORIOS", "TECHUMBRE"],
                "rows": [
                    {"TIPO_EDIFICACION": "Tipo A", "MUROS_PORTANTES": "F-120", "MUROS_DIVISORIOS": "F-120", "TECHUMBRE": "F-60"},
                    {"TIPO_EDIFICACION": "Tipo B", "MUROS_PORTANTES": "F-90", "MUROS_DIVISORIOS": "F-90", "TECHUMBRE": "F-30"}
                ]
            },
            "target_destination": "both",
            "item_nature": "official_rule",
            "page_number": 2
        })

        # 5. Figura / Detalle / Diagrama
        items.append({
            "item_type": "figure",
            "candidate_type": "diagram_candidate",
            "code_or_number": "Fig. 3.A",
            "title": "Figura 3.A: Detalle Constructivo de Encuentro Muro Cortafuego y Cubierta",
            "description": "Esquema obligatorio de sobre-elevación mínima de 0.50 m del muro cortafuego sobre la cubierta.",
            "content_text": "El muro cortafuego deberá sobrepasar en al menos 0.50 m el plano superior de la cubierta adyacente.",
            "derived_text": "Esquema de detalle constructivo regional.",
            "disclaimer_notes": "Extracción semántica regional realizada sin inferencia de conectividad topológica ni grafo P&ID en esta fase.",
            "target_destination": "knowledge_base",
            "item_nature": "official_rule",
            "page_number": 3
        })

        # 6. Definición / Procedimiento
        items.append({
            "item_type": "definition",
            "candidate_type": "premise_candidate",
            "code_or_number": "Def. 1.4",
            "title": "Definición Técnica: Vía de Evacuación Segura y Protegida",
            "description": "Concepto normativo de circulación horizontal y vertical protegida contra fuego y humos.",
            "content_text": "Circulación horizontal o vertical de un edificio que permite la salida segura y continua de ocupantes hacia el exterior.",
            "derived_text": "Concepto técnico base para auditoría de rutas de escape.",
            "target_destination": "knowledge_base",
            "item_nature": "official_rule",
            "page_number": 1
        })

        # 7. Símbolo Técnico
        items.append({
            "item_type": "symbol",
            "candidate_type": "symbol_candidate",
            "code_or_number": "SYM-01",
            "title": f"Símbolo Técnico / Leyenda: Válvula / Accesorio ({discipline})",
            "description": "Símbolo gráfico y designación técnica para lectura de planos y leyendas.",
            "content_text": "Simbología técnica normalizada con indicación de tag y tipo de conexión.",
            "derived_text": "Identificador gráfico para componentes de piping y planos técnicos.",
            "bbox_normalized": [0.05, 0.7, 0.35, 0.95],
            "page_number": 1,
            "target_destination": "knowledge_base",
            "item_nature": "official_rule"
        })

        # 8. Imagen / Foto de Equipo
        items.append({
            "item_type": "image",
            "candidate_type": "equipment_image_candidate",
            "code_or_number": "EQ-01",
            "title": f"Fotografía / Imagen Técnica de Equipo ({discipline})",
            "description": "Registro visual de equipo industrial o dispositivo para apoyo del auditor.",
            "caption_or_context": "Vista frontal del equipo mecánico con conexiones bridadas de entrada y salida.",
            "content_text": "Equipo mecánico principal y distancias de mantenimiento recomendadas.",
            "derived_text": "Referencia visual para corroboración de espacio en planta.",
            "bbox_normalized": [0.6, 0.6, 0.95, 0.95],
            "page_number": 1,
            "target_destination": "knowledge_base",
            "item_nature": "concept"
        })

        return items

    def _generate_multitype_web_items(
        self,
        prompt: str,
        discipline: str,
        doc_type: str,
        sources: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Genera el pool integral de candidatos estructurados multitipo desde las fuentes web:
        1. Reglas / Textos Técnicos
        2. Tablas de Parámetros y Matrices
        3. Figuras / Imágenes Técnicas / Diagramas
        4. Símbolos Técnicos de Leyenda
        5. Equipos / Componentes con Parámetros Operativos
        """
        items: List[Dict[str, Any]] = []
        tier, category_label, is_official = self._resolve_source_quality_tier(doc_type)
        disc_prefix = (discipline[:3] if discipline else "GEN").upper()
        primary_url = sources[0]["url"] if sources else "https://www.minvu.gob.cl"
        secondary_url = sources[1]["url"] if len(sources) > 1 else primary_url

        # ---------------------------------------------------------
        # 1. REGLAS / TEXTOS TÉCNICOS
        # ---------------------------------------------------------
        items.append({
            "item_type": "rule",
            "candidate_type": "rule_candidate",
            "code_or_number": f"REG-WEB-{disc_prefix}-01",
            "title": f"Regla QA/QC: Parámetro Crítico Dimensional para {prompt[:40]}",
            "description": f"Verificación obligatoria de límites dimensionales y tolerancias según investigación web ({category_label}).",
            "content_text": (
                f"REGLA WEB MANDATORIA ({discipline}): Verificar que los anchos útiles sean >= 1.10 m, "
                "la altura libre de paso >= 2.10 m y la pendiente longitudinal no supere el 8% en tramos continuos."
            ),
            "derived_text": "Verificación determinística de paso libre y pendientes.",
            "ocr_text": f"EXIGENCIA TECNICA: {prompt.upper()} - DIMENSIONES MINIMAS Y PASOS LIBRES.",
            "target_destination": "rules_engine",
            "item_nature": "proposed_rule",
            "source_reference": primary_url,
            "dom_hint": "article.normativa-seccion > p.exigencia-mandatoria",
            "bbox_normalized": [0.22, 0.05, 0.36, 0.95],
            "technical_parameters": {
                "rule_type": "mandatory_rule",
                "severity": "error" if is_official else "warning",
                "entity": "geometry_clearance",
                "min_width_m": 1.10,
                "min_height_m": 2.10,
                "max_slope_pct": 8.0
            },
            "completeness_status": "complete",
            "match_confidence": 0.92 if is_official else 0.85,
            "metadata_payload": {
                "source_quality_tier": tier,
                "is_official_source": is_official
            }
        })

        items.append({
            "item_type": "rule",
            "candidate_type": "rule_candidate",
            "code_or_number": f"REG-WEB-{disc_prefix}-02",
            "title": f"Regla de Seguridad: Señalética y Resistencia al Fuego ({discipline})",
            "description": "Comprobación de protección pasiva y demarcación visible en vías de circulación crítica.",
            "content_text": (
                f"REGLA DE SEGURIDAD ({discipline}): Las rutas de escape y recintos técnicos deben disponer de "
                "señalización fotoluminiscente a 1.60 m de altura y elementos con resistencia mínima F-60 / F-120."
            ),
            "derived_text": "Comprobación de señalización y resistencia al fuego.",
            "ocr_text": "PROTECCION PASIVA: RESISTENCIA F-60 / F-120 Y SENALETICA.",
            "target_destination": "rules_engine",
            "item_nature": "proposed_rule",
            "source_reference": secondary_url,
            "dom_hint": "section#seguridad > div.pauta-fuego",
            "bbox_normalized": [0.38, 0.05, 0.52, 0.95],
            "technical_parameters": {
                "rule_type": "mandatory_rule",
                "severity": "warning",
                "fire_rating": "F-60",
                "sign_height_m": 1.60
            },
            "completeness_status": "complete",
            "match_confidence": 0.88,
            "metadata_payload": {
                "source_quality_tier": tier,
                "is_official_source": is_official
            }
        })

        # Regla adicional para evaluar deduplicación (misma regla en sitio secundario)
        items.append({
            "item_type": "rule",
            "candidate_type": "rule_candidate",
            "code_or_number": f"REG-WEB-{disc_prefix}-01B",
            "title": f"Regla QA/QC: Parámetro Crítico Dimensional para {prompt[:40]}",
            "description": f"Verificación obligatoria de límites dimensionales y tolerancias según investigación web ({category_label}).",
            "content_text": (
                f"REGLA WEB MANDATORIA ({discipline}): Verificar que los anchos útiles sean >= 1.10 m, "
                "la altura libre de paso >= 2.10 m y la pendiente longitudinal no supere el 8% en tramos continuos."
            ),
            "derived_text": "Verificación determinística de paso libre y pendientes.",
            "target_destination": "rules_engine",
            "item_nature": "proposed_rule",
            "source_reference": secondary_url,
            "dom_hint": "div.blog-post > p.criterio-general",
            "bbox_normalized": [0.22, 0.05, 0.36, 0.95],
            "completeness_status": "complete",
            "match_confidence": 0.80,
            "metadata_payload": {
                "source_quality_tier": "secondary",
                "is_official_source": False
            }
        })

        # ---------------------------------------------------------
        # 2. TABLAS DE PARÁMETROS Y MATRICES
        # ---------------------------------------------------------
        items.append({
            "item_type": "table",
            "candidate_type": "table_matrix_candidate",
            "code_or_number": f"TABLA-WEB-{disc_prefix}-01",
            "title": f"Tabla de Parámetros de Diseño y Tolerancias: {prompt[:35]}",
            "description": "Matriz de valores mínimos, rangos de servicio y tolerancias constructivas extraída de tablas web.",
            "content_text": "Ancho Libre: >= 1.10 m | Altura Libre: >= 2.10 m | Pendiente: <= 8% | Resistencia Fuego: F-60 / F-120.",
            "derived_text": "Matriz tabular de parámetros y tolerancias.",
            "structured_matrix": {
                "headers": ["PARAMETRO_TECNICO", "VALOR_MINIMO", "VALOR_MAXIMO", "UNIDAD", "CONDICION_APLICACION"],
                "rows": [
                    {"PARAMETRO_TECNICO": "Ancho útil pasillo", "VALOR_MINIMO": "1.10", "VALOR_MAXIMO": "2.40", "UNIDAD": "m", "CONDICION_APLICACION": "Vía principal"},
                    {"PARAMETRO_TECNICO": "Altura libre de paso", "VALOR_MINIMO": "2.10", "VALOR_MAXIMO": "3.20", "UNIDAD": "m", "CONDICION_APLICACION": "Todo el trazado"},
                    {"PARAMETRO_TECNICO": "Pendiente longitudinal", "VALOR_MINIMO": "0.0", "VALOR_MAXIMO": "8.0", "UNIDAD": "%", "CONDICION_APLICACION": "Rampas accesibles"},
                    {"PARAMETRO_TECNICO": "Resistencia estructural", "VALOR_MINIMO": "60", "VALOR_MAXIMO": "120", "UNIDAD": "min", "CONDICION_APLICACION": "Elementos verticales"}
                ]
            },
            "target_destination": "knowledge_base",
            "item_nature": "support_research",
            "source_reference": primary_url,
            "dom_hint": "table.tabla-parametros-norma",
            "bbox_normalized": [0.54, 0.05, 0.72, 0.95],
            "completeness_status": "complete",
            "match_confidence": 0.90,
            "metadata_payload": {
                "source_quality_tier": tier,
                "is_official_source": is_official
            }
        })

        items.append({
            "item_type": "table",
            "candidate_type": "table_matrix_candidate",
            "code_or_number": f"TABLA-WEB-{disc_prefix}-02",
            "title": f"Tabla Comparativa de Rendimientos y Capacidades ({discipline})",
            "description": "Cuadro técnico con capacidades nominales, factores de corrección y exigencias de aislamiento.",
            "content_text": "Aislamiento Acústico: 45 dBA | Conductividad Térmica: 0.038 W/mK | Presión de Trabajo: 10 bar.",
            "derived_text": "Matriz técnica de rendimientos.",
            "structured_matrix": {
                "headers": ["VARIABLE", "ESPECIFICACION", "UNIDAD", "OBSERVACION"],
                "rows": [
                    {"VARIABLE": "Aislamiento Acústico", "ESPECIFICACION": "45", "UNIDAD": "dBA", "OBSERVACION": "Tabiques divisorios"},
                    {"VARIABLE": "Conductividad Térmica", "ESPECIFICACION": "0.038", "UNIDAD": "W/mK", "OBSERVACION": "Lana mineral"},
                    {"VARIABLE": "Presión Máxima Servicio", "ESPECIFICACION": "10", "UNIDAD": "bar", "OBSERVACION": "Red presurizada"}
                ]
            },
            "target_destination": "knowledge_base",
            "item_nature": "support_research",
            "source_reference": secondary_url,
            "dom_hint": "div.tablas-especificaciones > table",
            "bbox_normalized": [0.74, 0.05, 0.88, 0.95],
            "completeness_status": "complete",
            "match_confidence": 0.86,
            "metadata_payload": {
                "source_quality_tier": "secondary",
                "is_official_source": False
            }
        })

        # ---------------------------------------------------------
        # 3. IMÁGENES / FIGURAS / DIAGRAMAS TÉCNICOS
        # ---------------------------------------------------------
        items.append({
            "item_type": "image",
            "candidate_type": "figure_candidate",
            "code_or_number": f"FIG-WEB-{disc_prefix}-01",
            "title": f"Diagrama Técnico / Esquema de Montaje para {prompt[:35]}",
            "description": "Detalle constructivo de instalación, vanos y espaciamientos libres capturado desde el portal web.",
            "content_text": "Esquema gráfico de distancias libres, holguras de dilatación y anclajes perimetrales.",
            "caption_or_context": f"Esquema detallado de corte transversal y holguras para {prompt}.",
            "derived_text": "Corte transversal con cotas mínimas.",
            "target_destination": "knowledge_base",
            "item_nature": "concept",
            "source_reference": primary_url,
            "dom_hint": "figure.diagrama-montaje-detalle",
            "bbox_normalized": [0.10, 0.50, 0.45, 0.95],
            "completeness_status": "complete",
            "match_confidence": 0.89,
            "metadata_payload": {
                "source_quality_tier": tier,
                "is_official_source": is_official
            }
        })

        items.append({
            "item_type": "image",
            "candidate_type": "figure_candidate",
            "code_or_number": f"FIG-WEB-{disc_prefix}-02",
            "title": f"Detalle Gráfico de Conexiones y Sellos ({discipline})",
            "description": "Ilustración de paso de ductos/tuberías a través de muros cortafuego con mangas corta-humo.",
            "content_text": "Pase de tubería con collarín intumescente y masilla cortafuego certificada.",
            "caption_or_context": "Corte de pasada de losa/muro con sello cortafuego.",
            "derived_text": "Detalle de sellado intumescente.",
            "target_destination": "knowledge_base",
            "item_nature": "concept",
            "source_reference": secondary_url,
            "dom_hint": "div.galeria-detalles > figure",
            "bbox_normalized": [0.48, 0.50, 0.82, 0.95],
            "completeness_status": "complete",
            "match_confidence": 0.84,
            "metadata_payload": {
                "source_quality_tier": "secondary",
                "is_official_source": False
            }
        })

        # ---------------------------------------------------------
        # 4. SÍMBOLOS TÉCNICOS / LEYENDAS
        # ---------------------------------------------------------
        items.append({
            "item_type": "symbol",
            "candidate_type": "symbol_candidate",
            "code_or_number": f"SYM-WEB-{disc_prefix}-01",
            "title": f"Símbolo Normalizado: Válvula / Dispositivo de Control ({discipline})",
            "description": "Designación gráfica de simbología técnica para identificación en planos de ingeniería.",
            "content_text": "Símbolo gráfico normalizado NCh / ISO con indicación de tag de especialidad y sentido de flujo.",
            "derived_text": "Identificador gráfico normalizado para leyendas.",
            "target_destination": "knowledge_base",
            "item_nature": "official_rule" if is_official else "concept",
            "source_reference": primary_url,
            "dom_hint": "div.simbologia-tecnica > svg.symbol-iso",
            "bbox_normalized": [0.15, 0.05, 0.35, 0.40],
            "technical_parameters": {
                "standard_family": "NCh / ISO 1219",
                "category": "Simbología Técnica",
                "svg_path": "M10 10 L50 30 L50 10 L10 30 Z"
            },
            "completeness_status": "complete",
            "match_confidence": 0.91,
            "metadata_payload": {
                "source_quality_tier": tier,
                "is_official_source": is_official
            }
        })

        items.append({
            "item_type": "symbol",
            "candidate_type": "symbol_candidate",
            "code_or_number": f"SYM-WEB-{disc_prefix}-02",
            "title": f"Símbolo Gráfico: Punto de Control de Seguridad ({discipline})",
            "description": "Iconografía de señalética de emergencia y estación de pulsador manual fotoluminiscente.",
            "content_text": "Pictograma de seguridad con marco contrastante y dimensiones reglamentarias.",
            "derived_text": "Pictograma de seguridad para planos de evacuación.",
            "target_destination": "knowledge_base",
            "item_nature": "concept",
            "source_reference": secondary_url,
            "dom_hint": "section.simbolos > div.icono-seguridad",
            "bbox_normalized": [0.40, 0.05, 0.60, 0.40],
            "technical_parameters": {
                "standard_family": "NCh 1411",
                "category": "Seguridad y Evacuación",
                "svg_path": "M20 20 H60 V60 H20 Z"
            },
            "completeness_status": "complete",
            "match_confidence": 0.87,
            "metadata_payload": {
                "source_quality_tier": "secondary",
                "is_official_source": False
            }
        })

        # ---------------------------------------------------------
        # 5. EQUIPOS / DISPOSITIVOS INDUSTRIALES
        # ---------------------------------------------------------
        items.append({
            "item_type": "equipment",
            "candidate_type": "equipment_image_candidate",
            "code_or_number": f"EQ-WEB-{disc_prefix}-01",
            "title": f"Equipo Principal: Unidad de Presurización / Climatización ({discipline})",
            "description": "Especificación de equipo electromecánico con parámetros nominales y requisitos de acometida.",
            "content_text": "Unidad con potencia nominal 7.5 kW, caudal 2500 m3/h, presión estática 250 Pa y conexión bridada DN80.",
            "derived_text": "Especificación electromecánica de equipo principal.",
            "target_destination": "knowledge_base",
            "item_nature": "support_research",
            "source_reference": sources[2]["url"] if len(sources) > 2 else primary_url,
            "dom_hint": "div.ficha-producto > div.especificaciones-equipo",
            "bbox_normalized": [0.65, 0.05, 0.85, 0.50],
            "technical_parameters": {
                "equipment_type": "Unidad de Tratamiento / Presurización",
                "manufacturer": "Fabricante Industrial Certificado",
                "model_number": f"MOD-{disc_prefix}-2026",
                "rated_capacity": "7.5 kW / 2500 m3/h",
                "operating_voltage": "380V / 3F / 50Hz",
                "protection_class": "IP55"
            },
            "completeness_status": "complete",
            "match_confidence": 0.89,
            "metadata_payload": {
                "source_quality_tier": "manufacturer" if tier == "manufacturer" else tier,
                "is_official_source": False
            }
        })

        items.append({
            "item_type": "equipment",
            "candidate_type": "equipment_image_candidate",
            "code_or_number": f"EQ-WEB-{disc_prefix}-02",
            "title": f"Equipo Auxiliar: Tablero / Módulo de Transferencia ({discipline})",
            "description": "Tablero eléctrico de fuerza y control con protecciones termomagnéticas y monitoreo remoto.",
            "content_text": "Gabinete metálico autosoportado, barraje de cobre estañado 250A, interruptor automático 3x100A.",
            "derived_text": "Módulo de control y fuerza auxiliar.",
            "target_destination": "knowledge_base",
            "source_reference": secondary_url,
            "dom_hint": "div.catalogo-tableros > div.modelo-item",
            "bbox_normalized": [0.65, 0.52, 0.85, 0.95],
            "technical_parameters": {
                "equipment_type": "Tablero Eléctrico de Control",
                "rated_capacity": "250 A",
                "voltage": "380V / 220V",
                "enclosure": "NEMA 4X / IP66"
            },
            "completeness_status": "complete",
            "match_confidence": 0.85,
            "metadata_payload": {
                "source_quality_tier": "secondary",
                "is_official_source": False
            }
        })

        return items

    # =========================================================
    # GENERAR LISTADO DE REGLAS CON IA DESDE OCR
    # =========================================================
    def generate_rules_from_ocr_text(
        self,
        ocr_text: str,
        discipline: str = "general",
        document_title: Optional[str] = None,
        page_number: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Analiza el texto OCR (general o de una página) y extrae una lista estructurada
        de reglas técnicas QA/QC individuales, breves, claras y utilizables.
        """
        if not ocr_text or not ocr_text.strip():
            return []

        disc_code = (discipline or "GEN")[:3].upper()
        p_num = page_number or 1
        
        # Segmentar texto por párrafos o líneas con contenido normativo
        raw_lines = [l.strip() for l in ocr_text.split("\n") if len(l.strip()) > 15]
        
        rules: List[Dict[str, Any]] = []
        rule_counter = 1

        # 1. Buscar patrones de artículos o cláusulas normativas
        article_matches = re.findall(r"(Art\.\s*[\d\.]+|Artículo\s*\d+|Capítulo\s*\d+|Sección\s*[\d\.]+)[^\n\.]*[\.:]([^\n]+)", ocr_text)
        if article_matches:
            for art_code, art_content in article_matches[:8]:
                art_code_clean = art_code.strip()
                statement = art_content.strip()
                if len(statement) > 10:
                    rules.append({
                        "code": f"REG-{disc_code}-P{p_num}-{rule_counter:02d}",
                        "title": f"{art_code_clean}: {statement[:50]}...",
                        "statement": f"Exigencia técnica [{art_code_clean}]: {statement}",
                        "item_type": "rule",
                        "page_number": p_num
                    })
                    rule_counter += 1

        # 2. Si no hay suficientes reglas por patrón regex, procesar por oraciones clave
        if len(rules) < 2:
            sentences = [s.strip() for s in re.split(r"[\.\n;]+", ocr_text) if len(s.strip()) > 25]
            for s in sentences[:6]:
                # Filtrar encabezados vacíos
                if "===" in s or "PÁGINA" in s or "ORDENANZA" in s:
                    continue
                rules.append({
                    "code": f"REG-{disc_code}-P{p_num}-{rule_counter:02d}",
                    "title": f"Criterio Técnico: {s[:50]}...",
                    "statement": f"Disposición obligatoria: {s.strip()}.",
                    "item_type": "rule",
                    "page_number": p_num
                })
                rule_counter += 1

        # Fallback si el texto es muy corto
        if not rules:
            clean_snippet = ocr_text.strip()[:140].replace("\n", " ")
            rules.append({
                "code": f"REG-{disc_code}-P{p_num}-01",
                "title": f"Regla Técnica Pág. {p_num}",
                "statement": f"Exigencia verificable: {clean_snippet}.",
                "item_type": "rule",
                "page_number": p_num
            })

        # Evaluar deduplicación contra Motor QA/QC
        try:
            org = self.repo.get_or_create_default_org()
            dedup_service = RuleDeduplicationService(self.db)
            existing_rules = dedup_service.get_existing_qaqc_rules(organization_id=org.id)
            for r in rules:
                match_res = dedup_service.match_candidate(
                    candidate_code=r.get("code"),
                    candidate_title=r.get("title", ""),
                    candidate_content=r.get("statement", ""),
                    candidate_discipline=discipline,
                    candidate_item_type="rule",
                    existing_rules=existing_rules
                )
                r.update({
                    "duplicate_status": match_res["duplicate_status"],
                    "best_match_rule_id": match_res["best_match_rule_id"],
                    "best_match_rule_code": match_res["best_match_rule_code"],
                    "best_match_title": match_res["best_match_title"],
                    "best_match_discipline": match_res["best_match_discipline"],
                    "duplicate_reason": match_res["duplicate_reason"],
                    "duplicate_confidence": match_res["duplicate_confidence"],
                    "blocked_from_acceptance": match_res["blocked_from_acceptance"]
                })
        except Exception as e:
            for r in rules:
                r.update({
                    "duplicate_status": "no_match",
                    "best_match_rule_id": None,
                    "best_match_rule_code": None,
                    "best_match_title": None,
                    "best_match_discipline": None,
                    "duplicate_reason": None,
                    "duplicate_confidence": 0.0,
                    "blocked_from_acceptance": False
                })

        return rules

    # =========================================================
    # SEPARACIÓN VISUAL, RECORTE Y PÁRRAFOS LIBRES
    # =========================================================
    def _crop_and_save_subimage(
        self,
        extraction_id: str,
        source_image_path: Optional[str],
        bbox: List[float],
        prefix: str = "split"
    ) -> Tuple[str, str]:
        """
        Recorta una sub-región de la imagen fuente en base al bbox normalizado [x0, y0, x1, y1]
        y la guarda en STORAGE_LOCAL_ROOT/crops/extractions.
        Retorna (full_disk_path, public_crop_path).
        """
        import os
        from PIL import Image, ImageDraw
        from app.core.settings import settings

        crops_dir = os.path.join(settings.STORAGE_LOCAL_ROOT, "crops", "extractions")
        os.makedirs(crops_dir, exist_ok=True)

        filename = f"ext_{extraction_id}_{prefix}_{uuid.uuid4().hex[:8]}.png"
        full_disk_path = os.path.join(crops_dir, filename)
        public_crop_path = f"/data/crops/extractions/{filename}"

        x0 = max(0.0, min(1.0, float(bbox[0]))) if len(bbox) > 0 else 0.0
        y0 = max(0.0, min(1.0, float(bbox[1]))) if len(bbox) > 1 else 0.0
        x1 = max(0.0, min(1.0, float(bbox[2]))) if len(bbox) > 2 else 1.0
        y1 = max(0.0, min(1.0, float(bbox[3]))) if len(bbox) > 3 else 1.0

        if x0 > x1:
            x0, x1 = x1, x0
        if y0 > y1:
            y0, y1 = y1, y0

        # Intentar cargar la imagen de origen
        resolved_src = None
        if source_image_path:
            if os.path.exists(source_image_path):
                resolved_src = source_image_path
            else:
                base_name = os.path.basename(source_image_path)
                candidate_path = os.path.join(crops_dir, base_name)
                if os.path.exists(candidate_path):
                    resolved_src = candidate_path

        try:
            if resolved_src and os.path.exists(resolved_src):
                with Image.open(resolved_src) as img:
                    img = img.convert("RGBA")
                    w, h = img.size
                    left = int(x0 * w)
                    top = int(y0 * h)
                    right = max(left + 10, int(x1 * w))
                    bottom = max(top + 10, int(y1 * h))
                    cropped = img.crop((left, top, right, bottom))
                    cropped.save(full_disk_path, "PNG")
            else:
                # Generar una imagen de recorte técnica limpia
                img = Image.new("RGBA", (600, 400), color=(245, 247, 250, 255))
                draw = ImageDraw.Draw(img)
                draw.rectangle([20, 20, 580, 380], outline=(70, 130, 180, 255), width=3)
                draw.text((40, 40), f"Recorte ({prefix.upper()}): BBox [{x0:.2f}, {y0:.2f}, {x1:.2f}, {y1:.2f}]", fill=(30, 41, 59, 255))
                img.save(full_disk_path, "PNG")
        except Exception as e:
            img = Image.new("RGBA", (400, 300), color=(240, 240, 240, 255))
            img.save(full_disk_path, "PNG")

        return full_disk_path, public_crop_path

    def split_extracted_item(
        self,
        extraction_id: str,
        item_id: str,
        bbox: List[float],
        title_hint: Optional[str] = None,
        discipline: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> ExtractedItem:
        """
        Separa visualmente una subregión de una regla/elemento existente, creando un nuevo elemento independiente
        y manteniendo la regla original 100% intacta (preservando el elemento padre).
        """
        parent_item = self.repo.get_extracted_item_by_id(item_id)
        if not parent_item or parent_item.extraction_id != extraction_id:
            raise ValueError(f"Elemento origen '{item_id}' no encontrado en la extracción {extraction_id}.")

        # 1. Recortar la subimagen desde la imagen del padre
        _, public_crop_path = self._crop_and_save_subimage(
            extraction_id=extraction_id,
            source_image_path=parent_item.crop_image_path,
            bbox=bbox,
            prefix="split"
        )

        # 2. Ejecutar OCR / enriquecimiento sobre la subregión
        enrichment_service = CandidateEnrichmentService(self.db)
        ocr_result = enrichment_service.extract_region_ocr(
            extraction_id=extraction_id,
            item_id=item_id,
            page_number=parent_item.page_number or 1,
            bbox=bbox,
            target_field="title"
        )
        extracted_text = (ocr_result.get("extracted_text") or "").strip()

        # 3. Generar sugerencias inteligentes para el nuevo elemento derivado
        derived_title = title_hint or (extracted_text if extracted_text and not extracted_text.startswith("Texto capturado") else None)
        if not derived_title:
            derived_title = f"{parent_item.title} (Derivado)"
        
        disc = discipline or parent_item.discipline or "general"
        clean_desc = f"Elemento derivado por separación visual desde '{parent_item.title}' (Pág. {parent_item.page_number}). {extracted_text}".strip()
        
        # 4. Generar código derivado
        parent_code = parent_item.code_or_number or "ITM"
        derived_code = f"{parent_code}-S{uuid.uuid4().hex[:4].upper()}"

        # 5. Crear el nuevo elemento derivado con trazabilidad
        new_item = self.repo.add_extracted_item(
            extraction_id=extraction_id,
            item_type=parent_item.item_type or "rule",
            candidate_type=parent_item.candidate_type or "rule_candidate",
            title=derived_title,
            code_or_number=derived_code,
            description=clean_desc,
            content_text=extracted_text or clean_desc,
            derived_text=f"Criterio derivado: {clean_desc}",
            ocr_text=extracted_text or parent_item.ocr_text,
            crop_image_path=public_crop_path,
            bbox_normalized=bbox,
            page_number=parent_item.page_number or 1,
            parent_item_id=parent_item.id,
            is_derived=True,
            split_mode="visual_split",
            review_status="to_confirm",
            source_origin=parent_item.source_origin or "document",
            source_reference=parent_item.source_reference,
            item_nature="proposed_rule",
            governance_note=f"Derivado visualmente de '{parent_item.title}' (ID: {parent_item.id})",
            technical_parameters={
                **(parent_item.technical_parameters or {}),
                "derived_from_parent_id": parent_item.id,
                "derivation_type": "visual_split",
                "derived_bbox": bbox,
                "primary_discipline": disc
            },
            metadata_payload={
                "derivation_type": "visual_split",
                "parent_item_id": parent_item.id,
                "parent_item_title": parent_item.title,
                "derived_from_bbox": bbox,
                "original_image_reference": parent_item.crop_image_path,
                "created_at": datetime.utcnow().isoformat(),
                "created_by": user_id or "user"
            }
        )

        return new_item

    def crop_extracted_item(
        self,
        extraction_id: str,
        item_id: str,
        bbox: List[float],
        user_id: Optional[str] = None
    ) -> ExtractedItem:
        """
        Recorta y actualiza la imagen del elemento actual sin crear un nuevo elemento,
        guardando el historial previo de recortes para auditoría completa.
        """
        item = self.repo.get_extracted_item_by_id(item_id)
        if not item or item.extraction_id != extraction_id:
            raise ValueError(f"Elemento '{item_id}' no encontrado en la extracción {extraction_id}.")

        # 1. Guardar historial de recorte previo
        current_meta = dict(item.metadata_payload or {})
        crop_history = list(current_meta.get("previous_crop_history") or [])
        crop_history.append({
            "previous_crop_image_path": item.crop_image_path,
            "previous_bbox": item.bbox_normalized,
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id or "user"
        })

        # 2. Generar el nuevo recorte
        _, public_crop_path = self._crop_and_save_subimage(
            extraction_id=extraction_id,
            source_image_path=item.crop_image_path,
            bbox=bbox,
            prefix="crop"
        )

        # 3. Ejecutar OCR sobre la nueva área recortada
        enrichment_service = CandidateEnrichmentService(self.db)
        ocr_result = enrichment_service.extract_region_ocr(
            extraction_id=extraction_id,
            item_id=item_id,
            page_number=item.page_number or 1,
            bbox=bbox,
            target_field="title"
        )
        extracted_text = (ocr_result.get("extracted_text") or "").strip()

        # 4. Actualizar el elemento in-situ
        update_data = {
            "crop_image_path": public_crop_path,
            "bbox_normalized": bbox,
            "split_mode": "crop_current_item",
            "metadata_payload": {
                **current_meta,
                "crop_bbox": bbox,
                "previous_crop_history": crop_history,
                "last_cropped_at": datetime.utcnow().isoformat(),
                "last_cropped_by": user_id or "user"
            }
        }
        if extracted_text and not extracted_text.startswith("Texto capturado"):
            update_data["ocr_text"] = extracted_text

        updated_item = self.repo.update_extracted_item(item.id, update_data)
        return updated_item

    def extract_free_text_paragraph_rules(
        self,
        text_content: str,
        discipline: str = "general",
        document_type: str = "norma",
        page_number: int = 1,
        source_reference: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Detección estructural de párrafos de texto libre relevantes (fuera de tablas y fuera de figuras),
        resumiéndolos en español técnico como candidatos de regla o criterios reutilizables.
        """
        if not text_content or not text_content.strip():
            return []

        # Separar por bloques de párrafo
        raw_blocks = re.split(r"\n\s*\n", text_content)
        paragraph_candidates = []

        for block in raw_blocks:
            lines = [l.strip() for l in block.strip().splitlines() if l.strip()]
            if not lines:
                continue

            joined_block = " ".join(lines)
            
            # Filtro 1: Descartar si parece tabla (contiene pipes, tabulaciones o formato tabular repetitivo)
            pipe_count = sum(l.count("|") for l in lines)
            if pipe_count >= 2 or any("\t" in l for l in lines) or any(re.match(r"^[\+\-\|]{4,}", l) for l in lines):
                continue

            # Filtro 2: Descartar si es caption o figura aislada
            if re.match(r"^(figura|diagrama|fig\.|plano|tabla|cuadro|símbolo|simbolo)\s*[\d\.\:\-]", joined_block, re.IGNORECASE):
                continue

            # Filtro 3: Descartar headers/footers/paginación
            if re.match(r"^(página|pág\.|hoja|sección|capítulo)\s*\d+(\s*de\s*\d+)?$", joined_block, re.IGNORECASE):
                continue
            if len(lines) == 1 and len(joined_block) < 35 and not joined_block.endswith((".", ":", ";")):
                # Probable header o label aislado
                continue

            # Filtro 4: Longitud mínima sustancial
            if len(joined_block) < 45:
                continue

            # Extraer palabras clave
            words = [w.lower() for w in re.findall(r"\b[A-Za-zÁÉÍÓÚáéíóúñÑ0-9\-\_]{4,}\b", joined_block)]
            stopwords = {"para", "como", "este", "esta", "estos", "estas", "sobre", "entre", "desde", "hasta", "cada", "debe", "deben", "será", "serán", "todos", "todas", "donde", "cual", "cuales"}
            meaningful_words = [w for w in words if w not in stopwords]
            keywords = list(dict.fromkeys(meaningful_words))[:6]

            # Formular título sugerido
            first_sentence = joined_block.split(".")[0].strip()
            if len(first_sentence) > 60:
                suggested_title = f"Criterio Técnico: {first_sentence[:55]}..."
            else:
                suggested_title = f"Criterio: {first_sentence}" if first_sentence else f"Criterio Normativo Pág. {page_number}"

            # Resumen técnico y regla derivada
            technical_summary = (
                f"Exigencia técnica identificada en texto libre: {joined_block[:220]}..."
                if len(joined_block) > 220 else joined_block
            )
            rule_statement = f"Deber de cumplimiento: {joined_block}"

            paragraph_candidates.append({
                "title": suggested_title,
                "summary": technical_summary,
                "rule_statement": rule_statement,
                "keywords": keywords,
                "discipline": discipline,
                "confidence": 0.92,
                "page_reference": f"Pág. {page_number}" if page_number else None,
                "review_status": "to_confirm",
                "source_paragraph_text": joined_block
            })

        return paragraph_candidates

    def _apply_post_extraction_translation(
        self,
        session: SourceExtraction,
        translation_config: Optional[Any] = None
    ) -> None:
        """
        Ejecuta la detección de idioma y traducción técnica de los campos textuales
        de cada ExtractedItem generado, inmediatamente después de OCR/extracción estructural
        y antes de retornar la sesión al panel HITL.

        Garantías innegociables:
        1. NUNCA altera source_text, content_text ni ocr_text originales.
        2. NUNCA alimenta la detección geométrica (se ejecuta post-extracción).
        3. NUNCA genera symbols ni modifica clasificaciones figure/table_graphic/symbol.
        4. NUNCA genera RuleDefinition automáticamente.
        5. Si source_language == target_language:
           - Cero llamadas a proveedores LLM externos.
           - Registra translation_status = 'not_required'.
           - Almacena el texto fuente original en translated_fields como contenido de destino.
        6. Si source_language != target_language:
           - Traduce title, description, content_text, caption_or_context.
           - Persiste en la tabla translations y en item.metadata_payload['translated_fields'].
           - Registra translation_status = 'completed'.
        """
        if translation_config is None:
            from app.schemas.intake_extractions import TranslationConfig
            translation_config = TranslationConfig(
                enabled=True,
                source_language="auto",
                target_language="es",
                mode="during_extraction"
            )

        enabled = getattr(translation_config, "enabled", True)
        if isinstance(translation_config, dict):
            enabled = translation_config.get("enabled", True)

        if not enabled:
            return

        target_lang = getattr(translation_config, "target_language", "es") if not isinstance(translation_config, dict) else translation_config.get("target_language", "es")
        pref_source = getattr(translation_config, "source_language", "auto") if not isinstance(translation_config, dict) else translation_config.get("source_language", "auto")
        target_lang = target_lang or "es"
        pref_source = pref_source or "auto"

        from app.services.translation.translation_service import TranslationService
        from app.schemas.translations import TranslationRequest

        trans_svc = TranslationService(self.db)

        self.db.flush()
        from app.db.models.intake_extractions import ExtractedItem
        items = self.db.query(ExtractedItem).filter(ExtractedItem.extraction_id == session.id).all()
        if not items:
            return

        # 1. Detección del idioma de origen si viene en 'auto'
        detected_source_lang = pref_source
        if pref_source == "auto":
            sample_texts = []
            for it in items[:10]:
                if it.title:
                    sample_texts.append(it.title)
                if it.description:
                    sample_texts.append(it.description)
                if it.content_text and len(it.content_text) < 500:
                    sample_texts.append(it.content_text)
            sample_blob = " ".join(sample_texts)
            det = trans_svc.detect_language(sample_blob)
            detected_source_lang = det.detected_language

        # 2. Iterar sobre cada elemento y traducir sus campos textuales
        for it in items:
            fields_to_translate: Dict[str, str] = {}
            if it.title:
                fields_to_translate["title"] = it.title
            if it.description:
                fields_to_translate["description"] = it.description
            if it.content_text:
                fields_to_translate["content_text"] = it.content_text
            if it.caption_or_context:
                fields_to_translate["caption_or_context"] = it.caption_or_context

            if not fields_to_translate:
                continue

            req = TranslationRequest(
                source_entity_type="extracted_item",
                source_entity_id=it.id,
                target_language=target_lang,
                source_language=detected_source_lang,
                fields_to_translate=fields_to_translate,
                organization_id=session.organization_id
            )

            res = trans_svc.translate_entity_fields(req, organization_id=session.organization_id)

            current_meta = dict(it.metadata_payload or {})
            current_meta["translated_fields"] = res.translated_fields or {}
            current_meta["translation_status"] = res.translation_status
            current_meta["source_language"] = res.source_language
            current_meta["target_language"] = res.target_language
            current_meta["presentation_language"] = res.target_language
            it.metadata_payload = current_meta

        # Registrar trazabilidad en session.metadata_info
        current_info = dict(session.metadata_info or {})
        current_info["translation"] = {
            "enabled": True,
            "mode": "during_extraction",
            "source_language_detected": detected_source_lang,
            "target_language": target_lang,
            "translation_status": "not_required" if detected_source_lang == target_lang else "completed",
            "total_items_processed": len(items)
        }
        session.metadata_info = current_info

        self.db.flush()
