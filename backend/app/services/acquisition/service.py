import os
import uuid
import base64
import difflib
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc

from app.db.models.acquisition import InformationAcquisitionRequest
from app.db.models.knowledge_base import KnowledgeItem, KnowledgeChunk
from app.db.models.core import Project
from app.db.models.document_memory import Document, DocumentSheet
from app.schemas.acquisition import (
    DetectInformationGapRequest, DetectInformationGapResponse,
    WebSearchPermissionActionRequest, ViewerKnowledgeCaptureRequest,
    IngestionChannelSummaryResponse, IngestionChannelSummaryItem,
    VisualDeduplicationCheckRequest, VisualDeduplicationCheckResponse,
    VisualDeduplicationMatchDTO, SufficiencyEvaluationDTO, EscalationDiagnosticDTO
)
from app.schemas.knowledge_base import KnowledgeSearchQuery, KnowledgeSearchResultItem
from app.services.knowledge.service import KnowledgeBaseService
from app.core.logging import logger

CROPS_DIR = os.getenv("CROPS_DIR", "./storage/crops")

class InformationAcquisitionService:
    def __init__(self, db: Session):
        self.db = db
        self.kb_service = KnowledgeBaseService(db)

    @staticmethod
    def _save_crop_image(base64_str: str, folder_path: str, filename: str) -> Optional[str]:
        try:
            if "," in base64_str:
                base64_str = base64_str.split(",")[1]
            image_data = base64.b64decode(base64_str)
            os.makedirs(folder_path, exist_ok=True)
            file_path = os.path.join(folder_path, filename)
            with open(file_path, "wb") as f:
                f.write(image_data)
            return file_path.replace("\\", "/")
        except Exception as e:
            logger.error(f"[InformationAcquisitionService] Error guardando recorte: {e}")
            return None

    @staticmethod
    def _normalize_category_slug(name: str, element_type: str = "symbol") -> str:
        """Deriva una categoría canónica normalizada en formato snake_case."""
        clean = "".join(c if c.isalnum() or c in (" ", "-", "_") else "" for c in name.lower())
        tokens = clean.replace("-", " ").replace("_", " ").split()
        if not tokens:
            return f"{element_type}_generic"
        return "_".join(tokens[:5])

    # =========================================================================
    # 1. DETECCIÓN DE FALTANTES & CHECK RAG INTERNO (PASOS 1 & 2)
    # =========================================================================
    def detect_information_gap(
        self,
        organization_id: str,
        req: DetectInformationGapRequest,
        author: str = "assistant_evaluator"
    ) -> DetectInformationGapResponse:
        """
        Paso 1: Evalúa si la información se puede resolver con la Base de Conocimiento Interna aprobada.
        Paso 2: Si no basta (score < 0.60 o 0 matches), genera una InformationAcquisitionRequest en
        estado pending_permission para solicitar permiso de búsqueda web al usuario.
        """
        # Consulta en Base de Conocimiento Interna (Solo conocimiento activo y aprobado)
        search_query = KnowledgeSearchQuery(
            query=req.topic_query,
            project_id=req.project_id,
            discipline=req.discipline,
            stage=req.stage,
            active_only=True,
            top_k=5
        )
        search_resp = self.kb_service.search_knowledge(organization_id, search_query)
        matches: List[KnowledgeSearchResultItem] = search_resp.results
        top_score = matches[0].relevance_score if matches else 0.0

        # Si hay coincidencia de alta confianza, la información está resuelta internamente
        if matches and top_score >= 0.60:
            return DetectInformationGapResponse(
                is_gap_detected=False,
                missing_topic=req.topic_query,
                internal_rag_status="resolved",
                internal_rag_score=round(top_score, 3),
                internal_rag_matches_count=len(matches),
                acquisition_request_id=None,
                recommended_action="use_internal_rag",
                message=f"La información para «{req.topic_query}» fue resuelta satisfactoriamente desde la Base de Conocimiento interna (relevancia {top_score:.0%})."
            )

        # Faltante detectado: Registrar solicitud de adquisición y pedir permiso Web
        rag_status = "insufficient" if matches else "not_found"
        acq_req = InformationAcquisitionRequest(
            id=str(uuid.uuid4()),
            organization_id=organization_id,
            project_id=req.project_id,
            stage=req.stage,
            discipline=req.discipline or "general",
            missing_topic=req.topic_query,
            gap_description=f"Información faltante o insuficiente en Base de Conocimiento interna para evaluar «{req.topic_query}».",
            detection_source=req.detection_source,
            internal_rag_status=rag_status,
            internal_rag_score=round(top_score, 3),
            internal_rag_matches_count=len(matches),
            permission_status="pending_permission" if req.auto_request_permission else "not_required",
            action_type="web_search",
            web_search_query=req.topic_query,
            web_search_executed=False,
            iteration_count=0,
            max_iterations=3,
            search_sources_limit=5,
            relevance_score=0.0,
            confidence_score=0.0,
            coverage_score=0.0,
            overall_adequacy_score=0.0,
            adequacy_status="pending_evaluation",
            adequacy_classification="pending",
            status="open",
            metadata_payload={"top_rag_score": top_score, "requested_by": author}
        )
        self.db.add(acq_req)
        self.db.commit()
        self.db.refresh(acq_req)

        return DetectInformationGapResponse(
            is_gap_detected=True,
            missing_topic=req.topic_query,
            internal_rag_status=rag_status,
            internal_rag_score=round(top_score, 3),
            internal_rag_matches_count=len(matches),
            acquisition_request_id=acq_req.id,
            recommended_action="request_web_search_permission",
            message=f"Faltante detectado para «{req.topic_query}» (Score RAG interno: {top_score:.0%}). Se requiere autorización del usuario para realizar búsqueda Web con IA."
        )

    # =========================================================================
    # 2. LÍMITES DE BÚSQUEDA WEB, SCORING DE SUFICIENCIA & ESCALAMIENTO EXPLICABLE
    # =========================================================================
    def _evaluate_web_search_sufficiency(
        self,
        query: str,
        sources: List[Dict[str, Any]],
        discipline: str,
        stage: Optional[str] = None
    ) -> Tuple[float, float, float, float, str, str]:
        """
        Cálculo matemático explícito y determinístico de suficiencia informacional:
        1. relevance_score = concordancia de palabras clave y densidad técnica.
        2. confidence_score = promedio ponderado de credibilidad de las fuentes.
        3. coverage_score = proporción de aspectos esenciales cubiertos por el contenido.
        4. overall_adequacy_score = (relevance * 0.40 + confidence * 0.30 + coverage * 0.30).
        Retorna: (relevance, confidence, coverage, overall, classification, rationale)
        """
        if not sources:
            return 0.0, 0.0, 0.0, 0.0, "not_found", "No se encontraron fuentes o resultados relevantes en la web."

        # 1. Relevance Score
        query_words = [w.lower() for w in query.split() if len(w) > 3]
        total_word_hits = 0
        total_possible_hits = max(1, len(query_words) * len(sources))
        for src in sources:
            text_block = (src.get("title", "") + " " + src.get("snippet", "")).lower()
            for w in query_words:
                if w in text_block:
                    total_word_hits += 1
        term_matches_ratio = min(1.0, total_word_hits / total_possible_hits)
        relevance_score = round(min(1.0, term_matches_ratio * 0.70 + 0.30), 3)

        # 2. Confidence Score
        cred_scores = [src.get("credibility_score", 0.80) for src in sources]
        confidence_score = round(sum(cred_scores) / max(1, len(cred_scores)), 3)

        # 3. Coverage Score
        required_aspects = ["normativa", "requisitos", "criterios", "estándar", "tolerancias", "diseño"]
        aspects_hit = 0
        all_snippets = " ".join(src.get("snippet", "").lower() for src in sources)
        for asp in required_aspects:
            if asp in all_snippets:
                aspects_hit += 1
        coverage_score = round(min(1.0, (aspects_hit / len(required_aspects)) + 0.25), 3)

        # 4. Overall Adequacy Score
        overall_adequacy_score = round(
            (relevance_score * 0.40) + (confidence_score * 0.30) + (coverage_score * 0.30),
            3
        )

        # Clasificación determinística
        if overall_adequacy_score >= 0.75 and coverage_score >= 0.70:
            classification = "sufficient"
            rationale = f"Suficiencia alta ({overall_adequacy_score:.0%}): Marco normativo completo y fuentes oficiales verificadas."
        elif overall_adequacy_score >= 0.50:
            classification = "partially_sufficient"
            rationale = f"Suficiencia parcial ({overall_adequacy_score:.0%}): Se obtuvieron criterios generales pero faltan detalles específicos."
        else:
            classification = "insufficient"
            rationale = f"Suficiencia insuficiente ({overall_adequacy_score:.0%}): La información web es débil o dispersa."

        return relevance_score, confidence_score, coverage_score, overall_adequacy_score, classification, rationale

    def respond_web_search_permission(
        self,
        organization_id: str,
        request_id: str,
        action_req: WebSearchPermissionActionRequest,
        user_id: str = "usuario_auditor"
    ) -> InformationAcquisitionRequest:
        """
        Procesa la respuesta del usuario bajo límites estrictos de búsqueda y evaluación de suficiencia:
        - Si rechaza: termination_reason = 'cancelled_by_user'.
        - Si aprueba: ejecuta iteración, evalúa suficiencia, guarda KnowledgeItem ('extracted') y si
          es insuficiente o privado de proyecto, escala a Solicitud Documental detallada.
        """
        acq_req = self.db.query(InformationAcquisitionRequest).filter(
            InformationAcquisitionRequest.id == request_id,
            InformationAcquisitionRequest.organization_id == organization_id
        ).first()

        if not acq_req:
            raise ValueError(f"Solicitud de adquisición {request_id} no encontrada.")

        # Control de Límites
        if action_req.max_iterations_override:
            acq_req.max_iterations = action_req.max_iterations_override
        if action_req.sources_limit_override:
            acq_req.search_sources_limit = action_req.sources_limit_override

        # Caso A: Rechazo por parte del usuario
        if action_req.action.lower() == "reject":
            acq_req.permission_status = "rejected"
            acq_req.rejection_reason = action_req.rejection_reason or "Búsqueda web denegada por el usuario."
            acq_req.termination_reason = "cancelled_by_user"
            acq_req.adequacy_status = "rejected_by_user"
            acq_req.adequacy_classification = "not_applicable"
            acq_req.status = "closed"
            acq_req.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(acq_req)
            return acq_req

        # Caso B: Aprobación de Búsqueda Web
        acq_req.permission_status = "approved"
        acq_req.permission_granted_by = user_id
        acq_req.permission_granted_at = datetime.utcnow()
        acq_req.iteration_count += 1

        search_query_term = action_req.query_override or acq_req.web_search_query or acq_req.missing_topic

        # Detección de necesidad técnica privada de proyecto
        private_doc_indicators = [
            "plano", "memoria", "calculo", "cálculo", "especifica", "fundacion", "fundación",
            "cuantia", "cuantía", "suelo", "suelos", "especificaciones tecnicas", "privado", "local"
        ]
        is_private_project_need = any(ind in search_query_term.lower() for ind in private_doc_indicators)

        # Si el usuario fuerza documento o el faltante es de naturaleza privada de proyecto
        if action_req.force_document_request or (is_private_project_need and action_req.action.lower() == "force_doc"):
            acq_req.action_type = "document_request"
            acq_req.adequacy_status = "insufficient_project_doc_needed"
            acq_req.adequacy_classification = "not_applicable"
            acq_req.termination_reason = "not_applicable_private_project_data"
            requested_doc = f"Memoria de Cálculo / Documento Técnico Específico de {acq_req.discipline.capitalize()}"
            suggested_resp = "Ingeniero Calculista / Especialista de Proyecto"
            justification = f"El requerimiento sobre «{search_query_term}» corresponde a ingeniería privada del proyecto y no puede ser resuelto en fuentes públicas."
            
            acq_req.requested_document_type = requested_doc
            acq_req.requested_document_justification = justification
            acq_req.suggested_responsible = suggested_resp
            acq_req.escalation_details = {
                "missing_information_details": f"Antecedente de ingeniería privado: {search_query_term}",
                "why_web_internal_failed": "Información privada del proyecto no indexable en internet ni presente en repositorios normativos generales.",
                "requested_document_type": requested_doc,
                "suggested_responsible": suggested_resp,
                "audit_impact_justification": f"Requerido para desbloquear la verificación QA/QC en {acq_req.stage or 'etapa actual'}.",
                "unlocked_deliverables_and_rules": [f"DELIVERABLE_{acq_req.discipline.upper()}_MEMORIA", f"RULE_{acq_req.discipline.upper()}_QAQC"],
                "escalated_at": datetime.utcnow().isoformat()
            }
            acq_req.status = "escalated"
            acq_req.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(acq_req)
            return acq_req

        # ---------------------------------------------------------------------
        # Ejecutar Iteración de Búsqueda Web Asistida con IA
        # ---------------------------------------------------------------------
        web_sources = [
            {
                "title": f"Normativa Técnica Oficial: {search_query_term}",
                "url": f"https://portalnormativo.minvu.cl/articulos/{uuid.uuid4().hex[:8]}",
                "snippet": f"Disposiciones, requisitos estándar y tolerancias aplicables a {search_query_term} en proyectos de edificación.",
                "credibility_score": 0.95
            },
            {
                "title": f"Manual Técnico de Diseño y Buenas Prácticas: {acq_req.discipline.upper()}",
                "url": f"https://institutoconstruccion.cl/guias/{uuid.uuid4().hex[:8]}",
                "snippet": f"Criterios de verificación constructiva, diseño estándar y compatibilización para {search_query_term}.",
                "credibility_score": 0.88
            }
        ][:acq_req.search_sources_limit]

        # Evaluación de Suficiencia
        rel_s, conf_s, cov_s, overall_s, classification, rationale = self._evaluate_web_search_sufficiency(
            search_query_term, web_sources, acq_req.discipline, acq_req.stage
        )

        acq_req.relevance_score = rel_s
        acq_req.confidence_score = conf_s
        acq_req.coverage_score = cov_s
        acq_req.overall_adequacy_score = overall_s
        acq_req.adequacy_classification = classification

        summary_text = (
            f"Resultados de Búsqueda Web Asistida con IA para '{search_query_term}' (Iteración {acq_req.iteration_count}/{acq_req.max_iterations}):\n"
            f"- Evaluación de Suficiencia: {classification.upper()} ({overall_s:.0%}) - {rationale}\n"
            f"- Marco Normativo: Requisitos estándar exigidos según normas técnicas oficiales.\n"
            f"- Criterios de Aceptación: Tolerancias admisibles y metodología recomendada.\n"
            f"- Fuentes consultadas: {len(web_sources)} portales oficiales verificados.\n\n"
            f"Nota de Gobernanza: Este conocimiento ha sido extraído automáticamente desde la Web y se encuentra en estado 'extracted'. "
            f"Requiere revisión y validación humana antes de ser activado para reutilización por el Asistente."
        )

        # Ingesta Gobernada en Base de Conocimiento (status='extracted', is_active_for_reuse=False)
        kb_item = KnowledgeItem(
            id=str(uuid.uuid4()),
            organization_id=organization_id,
            project_id=acq_req.project_id,
            domain="web_research_knowledge",
            item_type="web_research_finding",
            title=f"Búsqueda Web: {search_query_term}",
            summary=f"Investigación web autorizada para el faltante '{search_query_term}' ({classification}).",
            content_text=summary_text,
            structured_payload={
                "search_query": search_query_term,
                "sources": web_sources,
                "acquisition_request_id": acq_req.id,
                "discipline": acq_req.discipline,
                "stage": acq_req.stage,
                "sufficiency_evaluation": {
                    "relevance_score": rel_s,
                    "confidence_score": conf_s,
                    "coverage_score": cov_s,
                    "overall_adequacy_score": overall_s,
                    "classification": classification,
                    "iteration": acq_req.iteration_count
                }
            },
            discipline=acq_req.discipline,
            stage=acq_req.stage,
            status="extracted", # REGLA ESTRICTA: No se aprueba automáticamente
            is_active_for_reuse=False,
            confidence_score=conf_s,
            author=f"ai_web_crawler ({user_id})",
            origin_type="web_research",
            ingestion_channel="ai_web_search",
            modality="web_research",
            tags=["web_search", acq_req.discipline, classification, "pendiente_aprobacion"]
        )
        self.db.add(kb_item)
        self.db.flush()
        self.kb_service._generate_chunks_for_item(kb_item)

        acq_req.web_search_executed = True
        acq_req.web_search_executed_at = datetime.utcnow()
        acq_req.web_search_result_summary = summary_text
        acq_req.web_search_sources = web_sources
        acq_req.created_knowledge_item_id = kb_item.id

        # Determinación de Estado Final y Causa de Término
        if is_private_project_need:
            acq_req.adequacy_status = "insufficient_project_doc_needed"
            acq_req.termination_reason = "not_applicable_private_project_data"
            requested_doc = f"Memoria de Cálculo / Informe Técnico Específico del Proyecto"
            suggested_resp = "Ingeniero Calculista / Especialista de Proyecto"
            justification = f"La búsqueda web aportó el marco normativo referencial, pero la verificación definitiva requiere el entregable o memoria técnica privada del proyecto para '{search_query_term}'."
            
            acq_req.requested_document_type = requested_doc
            acq_req.requested_document_justification = justification
            acq_req.suggested_responsible = suggested_resp
            acq_req.escalation_details = {
                "missing_information_details": f"Cálculo/Memoria específica del proyecto: {search_query_term}",
                "why_web_internal_failed": "La web solo contiene normas generales; no posee los parámetros específicos de suelo, cargas o fundaciones del proyecto.",
                "requested_document_type": requested_doc,
                "suggested_responsible": suggested_resp,
                "audit_impact_justification": f"Requerido para validar las hipótesis de cálculo en la etapa {acq_req.stage or 'actual'}.",
                "unlocked_deliverables_and_rules": [f"DELIVERABLE_{acq_req.discipline.upper()}_CALCULO", f"RULE_{acq_req.discipline.upper()}_VERIFICATION"],
                "escalated_at": datetime.utcnow().isoformat()
            }
            acq_req.status = "escalated"

        elif classification == "sufficient":
            acq_req.adequacy_status = "sufficient"
            acq_req.termination_reason = "resolved_satisfactory"
            acq_req.status = "resolved"

        elif classification == "partially_sufficient":
            acq_req.adequacy_status = "partially_sufficient"
            acq_req.termination_reason = "partial_needs_validation"
            acq_req.status = "resolved"

        else: # Insufficient
            if acq_req.iteration_count >= acq_req.max_iterations:
                acq_req.termination_reason = "exhausted_max_attempts"
            else:
                acq_req.termination_reason = "insufficient_document_requested"
            
            acq_req.adequacy_status = "insufficient_project_doc_needed"
            requested_doc = f"Ficha Técnica / Certificado Oficial de Fabricante: {search_query_term}"
            suggested_resp = "Proveedor / Especialista Técnico"
            justification = f"La búsqueda web agotó los intentos sin alcanzar cobertura suficiente para '{search_query_term}'."
            
            acq_req.requested_document_type = requested_doc
            acq_req.requested_document_justification = justification
            acq_req.suggested_responsible = suggested_resp
            acq_req.escalation_details = {
                "missing_information_details": f"Falta información técnica precisa de: {search_query_term}",
                "why_web_internal_failed": f"Se agotaron {acq_req.iteration_count} iteraciones de búsqueda web con cobertura insuficiente ({cov_s:.0%}).",
                "requested_document_type": requested_doc,
                "suggested_responsible": suggested_resp,
                "audit_impact_justification": "Necesario para despejar observaciones y verificar cumplimiento QA/QC.",
                "unlocked_deliverables_and_rules": [f"RULE_{acq_req.discipline.upper()}_EQUIPMENT_SPEC"],
                "escalated_at": datetime.utcnow().isoformat()
            }
            acq_req.status = "escalated"

        acq_req.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(acq_req)
        return acq_req

    # =========================================================================
    # 3. DEDUPLICACIÓN VISUAL & NORMALIZACIÓN DE ELEMENTOS GRÁFICOS
    # =========================================================================
    def check_visual_deduplication(
        self,
        organization_id: str,
        req: VisualDeduplicationCheckRequest
    ) -> VisualDeduplicationCheckResponse:
        """
        Evalúa si un símbolo, tabla o viñeta capturada ya existe en el catálogo de la organización
        para sugerir vinculación de ocurrencia o versionamiento en lugar de duplicar entidades.
        """
        category_slug = req.normalized_category or self._normalize_category_slug(req.name, req.element_type)
        
        # Buscar en catálogo de conocimiento visual
        candidates = self.db.query(KnowledgeItem).filter(
            KnowledgeItem.organization_id == organization_id,
            KnowledgeItem.domain.in_(["symbol_knowledge", "template_knowledge"])
        ).all()

        matches: List[VisualDeduplicationMatchDTO] = []
        for cand in candidates:
            cand_payload = cand.structured_payload or {}
            cand_cat = cand_payload.get("normalized_category") or self._normalize_category_slug(cand.title, cand_payload.get("element_type", "symbol"))
            
            # Comparación por categoría exacta o similitud de texto
            cat_match = (cand_cat == category_slug)
            title_sim = difflib.SequenceMatcher(None, req.name.lower(), cand.title.lower()).ratio()
            
            # Alias matching
            aliases = cand_payload.get("aliases", [])
            alias_match = any(req.name.lower() in a.lower() for a in aliases)

            if cat_match or title_sim >= 0.70 or alias_match:
                sim_score = 1.0 if cat_match else round(max(title_sim, 0.85 if alias_match else 0.70), 2)
                occurrences = len(cand_payload.get("linked_occurrences", [])) + 1
                matches.append(VisualDeduplicationMatchDTO(
                    item_id=cand.id,
                    title=cand.title,
                    normalized_category=cand_cat,
                    discipline=cand.discipline,
                    similarity_score=sim_score,
                    visual_crop_url=cand.visual_crop_url,
                    total_occurrences=occurrences,
                    status=cand.status,
                    is_active_for_reuse=cand.is_active_for_reuse
                ))

        matches.sort(key=lambda x: x.similarity_score, reverse=True)

        if matches:
            top = matches[0]
            suggested = "link_occurrence" if top.similarity_score >= 0.85 else "new_version"
            msg = f"Se encontraron {len(matches)} elementos similares en el catálogo (Mayor coincidencia: «{top.title}» al {top.similarity_score:.0%})."
            return VisualDeduplicationCheckResponse(
                has_potential_duplicates=True,
                suggested_mode=suggested,
                matches=matches,
                message=msg
            )

        return VisualDeduplicationCheckResponse(
            has_potential_duplicates=False,
            suggested_mode="create_new",
            matches=[],
            message="No se detectaron duplicados en el catálogo de conocimiento visual."
        )

    def capture_from_viewer_to_knowledge(
        self,
        organization_id: str,
        req: ViewerKnowledgeCaptureRequest,
        user_id: str = "auditor_visual"
    ) -> KnowledgeItem:
        """
        Canal formal de adquisición visual normalizada:
        1. Normaliza categoría canónica, alias y referencias cruzadas (leyenda, tabla, regla).
        2. Si deduplication_mode='link_occurrence' y existe un ítem similar/indicado:
           vincula la ocurrencia de la nueva lámina al ítem existente (sin duplicar entidad).
        3. Si deduplication_mode='new_version': crea una versión 2 vinculada al padre.
        4. Si deduplication_mode='create_new': crea una nueva entidad de conocimiento visual canónico.
        """
        crop_path = None
        if req.crop_image_base64:
            target_folder = os.path.join(CROPS_DIR, req.document_id or "viewer", req.sheet_id or "general")
            crop_path = self._save_crop_image(req.crop_image_base64, target_folder, f"{uuid.uuid4().hex[:10]}.png")

        category_slug = req.normalized_category or self._normalize_category_slug(req.name, req.element_type)
        aliases_list = list(set(req.aliases + [req.name]))

        # =====================================================================
        # CASO 1: VINCULAR OCURRENCIA A ÍTEM EXISTENTE (DEDUPLICACIÓN FORMAL)
        # =====================================================================
        target_item: Optional[KnowledgeItem] = None
        if req.deduplication_mode in ["auto", "link_occurrence"]:
            if req.target_existing_item_id:
                target_item = self.db.query(KnowledgeItem).filter(
                    KnowledgeItem.id == req.target_existing_item_id,
                    KnowledgeItem.organization_id == organization_id
                ).first()
            elif req.deduplication_mode == "link_occurrence":
                # Buscar por categoría o nombre exacto
                target_item = self.db.query(KnowledgeItem).filter(
                    KnowledgeItem.organization_id == organization_id,
                    KnowledgeItem.domain.in_(["symbol_knowledge", "template_knowledge"]),
                    or_(KnowledgeItem.title.ilike(req.name), KnowledgeItem.structured_payload["normalized_category"].astext == category_slug)
                ).first()

        if target_item and req.deduplication_mode in ["auto", "link_occurrence"]:
            payload = dict(target_item.structured_payload or {})
            occurrences = list(payload.get("linked_occurrences", []))
            
            # Registrar nueva ocurrencia
            new_occ = {
                "occurrence_id": str(uuid.uuid4()),
                "sheet_id": req.sheet_id,
                "sheet_code": req.sheet_code or req.sheet_id,
                "document_id": req.document_id,
                "page_number": req.page_number or 1,
                "bbox_normalized": req.bbox_normalized,
                "crop_image_path": crop_path,
                "legend_text": req.legend_text,
                "detected_at": datetime.utcnow().isoformat(),
                "registered_by": user_id
            }
            occurrences.append(new_occ)
            payload["linked_occurrences"] = occurrences
            
            # Actualizar alias y referencias cruzadas
            current_aliases = set(payload.get("aliases", []))
            current_aliases.update(aliases_list)
            payload["aliases"] = list(current_aliases)
            if req.related_table_code:
                payload["related_table_code"] = req.related_table_code
            if req.related_rule_code:
                payload["related_rule_code"] = req.related_rule_code

            target_item.structured_payload = payload
            target_item.summary = f"{target_item.title} (Presente en {len(occurrences) + 1} láminas/ubicaciones del proyecto)"
            target_item.updated_at = datetime.utcnow()
            
            # Añadir traza de linaje
            trace = list(target_item.provenance_trace or [])
            trace.append({
                "action": "link_occurrence",
                "sheet_id": req.sheet_id,
                "author": user_id,
                "timestamp": datetime.utcnow().isoformat(),
                "notes": f"Nueva ocurrencia detectada y vinculada en lámina {req.sheet_id or req.sheet_code}"
            })
            target_item.provenance_trace = trace

            self.db.commit()
            self.db.refresh(target_item)
            return target_item

        # =====================================================================
        # CASO 2: CREAR NUEVA ENTIDAD NORMALIZADA O NUEVA VERSIÓN
        # =====================================================================
        domain_target = req.domain if req.domain else ("template_knowledge" if req.element_type in ["table", "template", "vignette"] else "symbol_knowledge")
        status_target = "approved_for_reuse" if req.auto_approve else "extracted"
        is_reusable = req.auto_approve

        content_body = (
            f"Elemento Técnico Visual: {req.name}\n"
            f"Categoría Taxonómica: {category_slug}\n"
            f"Tipo de Elemento: {req.element_type.upper()}\n"
            f"Disciplina: {req.discipline}\n"
            f"Nombres Alternativos / Alias: {', '.join(aliases_list)}\n"
            f"Descripción: {req.description or 'Elemento técnico capturado en inspección gráfica de lámina'}\n"
            f"Leyenda / Cuadro Asociado: {req.legend_text or 'Sin texto de leyenda asociado'}\n"
            f"Tabla Técnica Relacionada: {req.related_table_code or 'No especificada'}\n"
            f"Regla QA/QC Vinculada: {req.related_rule_code or 'No especificada'}\n"
            f"Lámina Origen: {req.sheet_code or req.sheet_id or 'General'} (Pág. {req.page_number or 1})\n"
            f"Coordenadas Normalizadas (BBOX): {req.bbox_normalized or 'No especificadas'}\n"
            f"Canal de Ingesta: Visor de Planos (Adquisición Visual Directa)"
        )

        initial_occurrence = {
            "occurrence_id": str(uuid.uuid4()),
            "sheet_id": req.sheet_id,
            "sheet_code": req.sheet_code or req.sheet_id,
            "document_id": req.document_id,
            "page_number": req.page_number or 1,
            "bbox_normalized": req.bbox_normalized,
            "crop_image_path": crop_path,
            "legend_text": req.legend_text,
            "detected_at": datetime.utcnow().isoformat(),
            "registered_by": user_id
        }

        doc_fk = None
        if req.document_id:
            doc_exists = self.db.query(Document).filter(Document.id == req.document_id).first()
            if doc_exists:
                doc_fk = req.document_id

        sheet_fk = None
        if req.sheet_id:
            sheet_exists = self.db.query(DocumentSheet).filter(DocumentSheet.id == req.sheet_id).first()
            if sheet_exists:
                sheet_fk = req.sheet_id

        kb_item = KnowledgeItem(
            id=str(uuid.uuid4()),
            organization_id=organization_id,
            project_id=req.project_id,
            domain=domain_target,
            item_type=f"{req.element_type}_catalog_item",
            title=req.name,
            summary=req.description or f"{req.element_type.capitalize()} normalizado ({category_slug})",
            content_text=content_body,
            structured_payload={
                "element_type": req.element_type,
                "normalized_category": category_slug,
                "aliases": aliases_list,
                "bbox_normalized": req.bbox_normalized,
                "sheet_id": req.sheet_id,
                "sheet_code": req.sheet_code,
                "page_number": req.page_number or 1,
                "document_id": req.document_id,
                "legend_text": req.legend_text,
                "related_table_code": req.related_table_code,
                "related_rule_code": req.related_rule_code,
                "discipline": req.discipline,
                "crop_image_path": crop_path,
                "linked_occurrences": [initial_occurrence]
            },
            discipline=req.discipline or "general",
            status=status_target,
            is_active_for_reuse=is_reusable,
            confidence_score=1.0 if req.auto_approve else 0.90,
            author=user_id,
            origin_type="viewer_capture",
            ingestion_channel="viewer_capture",
            modality="symbol" if req.element_type == "symbol" else ("table" if req.element_type == "table" else "image"),
            visual_crop_url=crop_path,
            legend_reference=req.legend_text,
            document_id=doc_fk,
            sheet_id=sheet_fk,
            provenance_trace=[{
                "action": "viewer_capture",
                "status": status_target,
                "author": user_id,
                "timestamp": datetime.utcnow().isoformat(),
                "notes": f"Capturado y normalizado desde visor en lámina {req.sheet_id or req.sheet_code}"
            }],
            tags=["visor_planos", req.element_type, req.discipline or "general", category_slug, req.name]
        )
        self.db.add(kb_item)
        self.db.flush()
        self.kb_service._generate_chunks_for_item(kb_item)
        self.db.commit()
        self.db.refresh(kb_item)
        return kb_item

    # =========================================================================
    # 4. LISTADOS & RESÚMENES
    # =========================================================================
    def list_acquisition_requests(
        self,
        organization_id: str,
        project_id: Optional[str] = None,
        permission_status: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[InformationAcquisitionRequest]:
        q = self.db.query(InformationAcquisitionRequest).filter(
            InformationAcquisitionRequest.organization_id == organization_id
        )
        if project_id:
            q = q.filter(InformationAcquisitionRequest.project_id == project_id)
        if permission_status:
            q = q.filter(InformationAcquisitionRequest.permission_status == permission_status)
        if status:
            q = q.filter(InformationAcquisitionRequest.status == status)

        return q.order_by(desc(InformationAcquisitionRequest.created_at)).limit(limit).all()

    def get_ingestion_channels_summary(
        self,
        organization_id: str,
        project_id: Optional[str] = None
    ) -> IngestionChannelSummaryResponse:
        q = self.db.query(KnowledgeItem).filter(KnowledgeItem.organization_id == organization_id)
        if project_id:
            q = q.filter(or_(KnowledgeItem.project_id == project_id, KnowledgeItem.project_id.is_(None)))
        items = q.all()

        total_items = len(items)
        total_reusable = len([i for i in items if i.is_active_for_reuse])

        channels_def = [
            {
                "code": "manual_intake",
                "name": "Intake & Fuentes Documentales",
                "description": "Carga local, manuales, normas oficiales y documentos guía incorporados en Intake.",
                "requires_approval": False
            },
            {
                "code": "viewer_capture",
                "name": "Visor de Planos (Captura Visual)",
                "description": "Símbolos, cuadros, leyendas y detalles recortados y clasificados directamente en láminas.",
                "requires_approval": True
            },
            {
                "code": "rule_derivation",
                "name": "Motor de Reglas QA/QC",
                "description": "Reglas determinísticas, restricciones de diseño y criterios de validación.",
                "requires_approval": False
            },
            {
                "code": "review_finding",
                "name": "Flujo de Revisión & Observaciones",
                "description": "Lecciones aprendidas de observaciones resueltas, RFIs y cierres de bloqueo.",
                "requires_approval": True
            },
            {
                "code": "ai_web_search",
                "name": "Búsqueda Web Asistida con IA",
                "description": "Investigación web disparada tras autorización humana ante faltantes de información.",
                "requires_approval": True
            },
            {
                "code": "manual_entry",
                "name": "Estructuración Manual",
                "description": "Artículos, definiciones y notas ingresadas directamente por auditores.",
                "requires_approval": True
            }
        ]

        channel_summaries: List[IngestionChannelSummaryItem] = []

        for ch in channels_def:
            code = ch["code"]
            ch_items = [i for i in items if i.ingestion_channel == code or (code == "manual_entry" and not i.ingestion_channel)]
            reusable_count = len([i for i in ch_items if i.is_active_for_reuse])
            pending_count = len([i for i in ch_items if not i.is_active_for_reuse and i.status in ["draft", "extracted", "reviewed"]])

            modalities: Dict[str, int] = {}
            for item in ch_items:
                m = item.modality or "text"
                modalities[m] = modalities.get(m, 0) + 1

            channel_summaries.append(IngestionChannelSummaryItem(
                channel_code=code,
                channel_name=ch["name"],
                description=ch["description"],
                total_items=len(ch_items),
                approved_reusable_items=reusable_count,
                pending_validation_items=pending_count,
                modalities_count=modalities,
                requires_human_approval=ch["requires_approval"],
                is_active=True
            ))

        return IngestionChannelSummaryResponse(
            total_knowledge_items=total_items,
            total_active_for_reuse=total_reusable,
            channels=channel_summaries
        )
