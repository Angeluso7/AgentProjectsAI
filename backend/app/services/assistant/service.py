import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc

from app.db.models.assistant import AssistantInteraction
from app.schemas.assistant import (
    AssistantExecutionRequest,
    AssistantExecutionResponse,
    AssistantFeedbackRequest,
    AssistantInteractionRead,
    AssistantTaskCatalogItem
)
from app.schemas.knowledge_base import KnowledgeSearchQuery, KnowledgeSearchResultItem
from app.services.knowledge.service import KnowledgeBaseService
from app.services.assistant.router import AiEngineRouter

class AssistantService:
    """
    Servicio integral del Asistente Técnico Operacional.
    Coordina la recuperación contextual RAG gobernada, el routing por tiers de IA
    y la persistencia/trazabilidad de cada interacción con soporte para feedback HITL.
    """

    def __init__(self, db: Session):
        self.db = db
        self.kb_service = KnowledgeBaseService(db)
        self.router = AiEngineRouter()

    def get_task_catalog(self) -> List[AssistantTaskCatalogItem]:
        """Retorna el catálogo público de tareas asistidas y sus políticas de routing."""
        return self.router.get_task_catalog()

    def execute_task(
        self,
        organization_id: str,
        payload: AssistantExecutionRequest,
        user_id: str = "system"
    ) -> AssistantExecutionResponse:
        """
        Ejecuta una tarea asistida con RAG activo gobernado y routing de motores IA.
        Garantiza exclusión de conocimiento no aprobado y registra la interacción.
        """
        task_type_val = payload.task_type.value if hasattr(payload.task_type, "value") else str(payload.task_type)

        # ---------------------------------------------------------------------
        # 1. RECUPERACIÓN CONTEXTUAL RAG (GOBERNADA)
        # ---------------------------------------------------------------------
        search_query = KnowledgeSearchQuery(
            query=payload.prompt,
            project_id=payload.project_id,
            discipline=payload.discipline,
            stage=payload.stage,
            active_only=True, # REGLA ESTRICTA: Solo items approved_for_reuse / validated
            top_k=5
        )
        rag_search_resp = self.kb_service.search_knowledge(organization_id, search_query)
        rag_sources: List[KnowledgeSearchResultItem] = rag_search_resp.results

        # Extraer IDs y Fragmentos para Trazabilidad
        retrieved_ids = [src.item_id for src in rag_sources]
        retrieved_chunks = [
            {
                "item_id": src.item_id,
                "chunk_id": src.chunk_id,
                "title": src.title,
                "domain": src.domain,
                "snippet": src.snippet,
                "relevance_score": src.relevance_score
            }
            for src in rag_sources
        ]

        # Enriquecer context_data con perfil de madurez del proyecto si existe
        resolved_context = dict(payload.context_data or {})
        if payload.project_id:
            from app.db.models.maturity import ProjectMaturityProfile
            latest_mat = self.db.query(ProjectMaturityProfile)\
                .filter(ProjectMaturityProfile.project_id == payload.project_id)\
                .order_by(desc(ProjectMaturityProfile.created_at))\
                .first()
            if latest_mat:
                resolved_context["maturity_score"] = latest_mat.overall_score
                resolved_context["maturity_level"] = latest_mat.maturity_level
                resolved_context["critical_gaps_count"] = len(latest_mat.critical_gaps or [])
                resolved_context["critical_gaps"] = latest_mat.critical_gaps[:3]
                resolved_context["acquisition_routes"] = latest_mat.acquisition_routes[:3]

        # ---------------------------------------------------------------------
        # 2. ROUTING DE MOTORES IA Y EVALUACIÓN DE ESCALAMIENTO
        # ---------------------------------------------------------------------
        initial_tier, executed_tier, engine_id, was_escalated, escalation_reason = self.router.evaluate_routing(
            task_type=task_type_val,
            prompt=payload.prompt,
            rag_sources=rag_sources,
            context_data=resolved_context,
            force_tier=payload.force_tier,
            allow_escalation=payload.allow_escalation
        )

        # ---------------------------------------------------------------------
        # 3. EJECUCIÓN DE INFERENCIA
        # ---------------------------------------------------------------------
        response_md, structured_output, confidence_score, cost_usd = self.router.execute_inference(
            task_type=task_type_val,
            prompt=payload.prompt,
            rag_sources=rag_sources,
            context_data=resolved_context,
            executed_tier=executed_tier,
            engine_id=engine_id
        )

        # ---------------------------------------------------------------------
        # 4. REGISTRO Y PERSISTENCIA DE INTERACCIÓN TRAZABLE
        # ---------------------------------------------------------------------
        interaction = AssistantInteraction(
            id=str(uuid.uuid4()),
            organization_id=organization_id,
            project_id=payload.project_id,
            task_type=task_type_val,
            user_prompt=payload.prompt,
            resolved_prompt=f"Task: {task_type_val} | Project: {payload.project_id} | Context: {payload.context_data}",
            stage=payload.stage,
            discipline=payload.discipline,
            retrieved_knowledge_ids=retrieved_ids,
            retrieved_chunks=retrieved_chunks,
            initial_tier=initial_tier,
            executed_tier=executed_tier,
            engine_model_used=engine_id,
            was_escalated=was_escalated,
            escalation_reason=escalation_reason,
            generated_response=response_md,
            structured_output=structured_output,
            confidence_score=confidence_score,
            cost_estimate_usd=cost_usd,
            feedback_status="pending",
            feedback_payload={},
            user_id=user_id
        )
        self.db.add(interaction)
        self.db.commit()
        self.db.refresh(interaction)

        return AssistantExecutionResponse(
            interaction_id=interaction.id,
            task_type=task_type_val,
            generated_response=response_md,
            structured_output=structured_output,
            confidence_score=confidence_score,
            tier_used=executed_tier,
            engine_model_used=engine_id,
            was_escalated=was_escalated,
            escalation_reason=escalation_reason,
            cost_estimate_usd=cost_usd,
            retrieved_sources=rag_sources
        )

    def submit_feedback(
        self,
        interaction_id: str,
        organization_id: str,
        payload: AssistantFeedbackRequest,
        user_id: str = "system"
    ) -> Optional[AssistantInteraction]:
        """Registra el feedback del usuario (aceptada, editada o rechazada) sobre una sugerencia."""
        interaction = self.db.query(AssistantInteraction).filter(
            AssistantInteraction.id == interaction_id,
            AssistantInteraction.organization_id == organization_id
        ).first()

        if not interaction:
            return None

        interaction.feedback_status = payload.status
        interaction.feedback_payload = {
            "notes": payload.feedback_notes,
            "edited_payload": payload.edited_payload,
            "submitted_by": user_id,
            "submitted_at": datetime.utcnow().isoformat()
        }
        interaction.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(interaction)
        return interaction

    def list_interactions(
        self,
        organization_id: str,
        project_id: Optional[str] = None,
        task_type: Optional[str] = None,
        feedback_status: Optional[str] = None,
        limit: int = 50
    ) -> List[AssistantInteraction]:
        """Lista el historial de interacciones asistidas para auditoría y trazabilidad."""
        q = self.db.query(AssistantInteraction).filter(
            AssistantInteraction.organization_id == organization_id
        )
        if project_id:
            q = q.filter(AssistantInteraction.project_id == project_id)
        if task_type:
            q = q.filter(AssistantInteraction.task_type == task_type)
        if feedback_status:
            q = q.filter(AssistantInteraction.feedback_status == feedback_status)

        return q.order_by(desc(AssistantInteraction.created_at)).limit(limit).all()
