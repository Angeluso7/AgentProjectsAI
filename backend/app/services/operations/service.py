from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from app.db.models.operations import (
    ProcessingJob, JobEvent, ConfidencePolicy, ReviewTask, ReviewDecision, DecisionTrace
)
from app.db.repositories.operations_repository import OperationsRepository
from app.services.operations.dispatcher import JobDispatcher
from app.core.logging import logger

class OperationsService:
    """Servicio orquestador de operaciones, jobs asíncronos, políticas de confianza y revisión humana."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = OperationsRepository(db)
        self.dispatcher = JobDispatcher(db)

    # ==========================================
    # 1. Gestión de Jobs
    # ==========================================

    def submit_job(
        self,
        job_type: str,
        target_type: str,
        target_id: str,
        project_id: Optional[str] = None,
        parent_job_id: Optional[str] = None,
        pipeline_name: str = "standard_pipeline",
        requested_by: str = "system",
        priority: int = 5,
        input_payload: Optional[Dict[str, Any]] = None,
        async_mode: bool = True
    ) -> ProcessingJob:
        """Crea y encola un nuevo job de procesamiento con respuesta inmediata HTTP 202."""
        job = self.repo.create_job(
            job_type=job_type,
            target_type=target_type,
            target_id=target_id,
            project_id=project_id,
            parent_job_id=parent_job_id,
            pipeline_name=pipeline_name,
            requested_by=requested_by,
            priority=priority,
            input_payload=input_payload or {}
        )

        logger.info(f"Job encolado: ID={job.id}, Tipo={job_type}, Target={target_type}:{target_id}")
        self.dispatcher.dispatch(job.id, async_mode=async_mode)
        if not async_mode:
            self.db.refresh(job)
        return job

    def get_job(self, job_id: str) -> Optional[ProcessingJob]:
        return self.repo.get_job(job_id)

    def list_jobs(
        self,
        status: Optional[str] = None,
        job_type: Optional[str] = None,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        project_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[ProcessingJob]:
        return self.repo.list_jobs(
            status=status,
            job_type=job_type,
            target_type=target_type,
            target_id=target_id,
            project_id=project_id,
            limit=limit,
            offset=offset
        )

    def retry_job(self, job_id: str, async_mode: bool = True) -> ProcessingJob:
        """Reintenta manualmente un job fallido o cancelado."""
        job = self.repo.get_job(job_id)
        if not job:
            raise ValueError(f"Job '{job_id}' no encontrado.")

        if job.status == "completed":
            raise ValueError("No se puede reintentar un job que ya completó exitosamente.")

        job.status = "queued"
        job.current_stage = "queued"
        job.progress_percent = 0
        job.error_code = None
        job.error_message = None
        job.failed_at = None
        self.db.commit()

        self.repo.record_event(
            job_id=job.id,
            event_type="retry_scheduled",
            status_before=job.status,
            status_after="queued",
            stage="manual_retry",
            message="Reintento manual solicitado por usuario/sistema.",
            actor_type="user"
        )

        self.dispatcher.dispatch(job.id, async_mode=async_mode)
        return job

    def cancel_job(self, job_id: str) -> ProcessingJob:
        """Cancela un job si aún se encuentra en cola o en ejecución."""
        job = self.repo.get_job(job_id)
        if not job:
            raise ValueError(f"Job '{job_id}' no encontrado.")

        if job.status in ["completed", "failed", "cancelled"]:
            return job # Idempotente

        self.repo.update_job_status(
            job_id=job.id,
            status="cancelled",
            stage="cancelled_by_user",
            actor_type="user"
        )
        return job

    def list_job_events(self, job_id: str) -> List[JobEvent]:
        return self.repo.list_events_by_job(job_id)

    # ==========================================
    # 2. Políticas de Confianza
    # ==========================================

    def seed_default_policies(self) -> None:
        """Siembra de políticas de confianza baseline (conservadoras y provisionales)."""
        defaults = [
            ConfidencePolicy(
                name="ocr_text_general_v1",
                applies_to="ocr_text",
                risk_level="medium",
                auto_accept_threshold=0.88,
                review_threshold=0.65,
                action_below_review_threshold="flag_only",
                version="1.0",
                description="Umbral conservador inicial para bloques de texto OCR general."
            ),
            ConfidencePolicy(
                name="title_block_match_general_v1",
                applies_to="title_block_match",
                risk_level="high",
                auto_accept_threshold=0.85,
                review_threshold=0.60,
                action_below_review_threshold="exception_required",
                version="1.0",
                description="Umbral para matching de viñetas contra plantillas de template_memory."
            ),
            ConfidencePolicy(
                name="title_block_scale_v1",
                applies_to="title_block_field",
                field_name="scale_text",
                risk_level="critical",
                auto_accept_threshold=0.90,
                review_threshold=0.70,
                action_below_review_threshold="exception_required",
                version="1.0",
                description="Extracción crítica de escala de plano arquitectónico/estructural."
            ),
            ConfidencePolicy(
                name="web_normative_intake_policy_v1",
                applies_to="normative_source",
                risk_level="critical",
                auto_accept_threshold=1.00, # Requiere SIEMPRE aprobación humana
                review_threshold=0.00,
                action_below_review_threshold="exception_required",
                version="1.0",
                description="Candado absoluto: las fuentes normativas web nunca se aceptan automáticamente."
            ),
            ConfidencePolicy(
                name="table_structure_general_v1",
                applies_to="table_structure",
                risk_level="high",
                auto_accept_threshold=0.82,
                review_threshold=0.60,
                action_below_review_threshold="exception_required",
                version="1.0",
                description="Umbral para reconstrucción espacial de grilla tabular y celdas."
            ),
            ConfidencePolicy(
                name="table_header_detection_v1",
                applies_to="table_header",
                risk_level="medium",
                auto_accept_threshold=0.85,
                review_threshold=0.65,
                action_below_review_threshold="flag_only",
                version="1.0",
                description="Umbral para detección y validación de encabezados de cuadros técnicos."
            ),
            ConfidencePolicy(
                name="table_type_classification_v1",
                applies_to="table_type",
                risk_level="high",
                auto_accept_threshold=0.80,
                review_threshold=0.55,
                action_below_review_threshold="exception_required",
                version="1.0",
                description="Umbral para tipificación de tablas (vanos, superficies, cargas)."
            ),
            ConfidencePolicy(
                name="symbol_detection_general_v1",
                applies_to="symbol_detection",
                risk_level="high",
                auto_accept_threshold=0.85,
                review_threshold=0.65,
                action_below_review_threshold="exception_required",
                version="1.0",
                description="Umbral para inferencia visual de símbolos técnicos en drawing_area."
            ),
            ConfidencePolicy(
                name="symbol_type_classification_v1",
                applies_to="symbol_type",
                risk_level="medium",
                auto_accept_threshold=0.80,
                review_threshold=0.60,
                action_below_review_threshold="flag_only",
                version="1.0",
                description="Umbral para clasificación de categoría de símbolo (puertas, luminarias, etc.)."
            ),
            ConfidencePolicy(
                name="symbol_library_match_v1",
                applies_to="symbol_library_match",
                risk_level="high",
                auto_accept_threshold=0.88,
                review_threshold=0.70,
                action_below_review_threshold="exception_required",
                version="1.0",
                description="Umbral para coincidencia de símbolo detectado contra biblioteca de template_memory."
            )
        ]

        for p in defaults:
            existing = self.repo.get_policy_by_name(p.name)
            if not existing:
                self.db.add(p)
        self.db.commit()

    def list_policies(self, applies_to: Optional[str] = None) -> List[ConfidencePolicy]:
        return self.repo.list_policies(applies_to)

    def create_policy(self, data: Dict[str, Any]) -> ConfidencePolicy:
        policy = ConfidencePolicy(**data)
        return self.repo.create_policy(policy)

    # ==========================================
    # 3. Cola de Revisión Humana (HITL)
    # ==========================================

    def list_review_tasks(
        self,
        status: Optional[str] = None,
        task_type: Optional[str] = None,
        priority: Optional[str] = None,
        project_id: Optional[str] = None
    ) -> List[ReviewTask]:
        return self.repo.list_review_tasks(
            status=status,
            task_type=task_type,
            priority=priority,
            project_id=project_id
        )

    def get_review_task(self, task_id: str) -> Optional[ReviewTask]:
        return self.repo.get_review_task(task_id)

    def resolve_review_task(
        self,
        task_id: str,
        decision: str,
        corrected_value: Optional[Dict[str, Any]] = None,
        reviewer: str = "auditor_qa",
        reason_code: Optional[str] = None,
        notes: Optional[str] = None
    ) -> ReviewDecision:
        """Registra la decisión humana inmutable y actualiza el estado de la tarea de revisión."""
        decision_record = self.repo.record_decision(
            task_id=task_id,
            decision=decision,
            corrected_value=corrected_value,
            reviewer=reviewer,
            reason_code=reason_code,
            notes=notes
        )

        task = self.repo.get_review_task(task_id)

        # Registrar traza de auditoría de la decisión humana
        self.repo.record_trace(
            trace_type="human_review_decision",
            entity_type="ReviewTask",
            entity_id=task.id,
            engine_name="HumanAuditor",
            engine_version="1.0",
            confidence=1.0,
            decision_status=f"human_{decision}",
            explanation=f"Revisión técnica '{decision}' por {reviewer}. Notas: {notes or 'Sin observaciones'}.",
            evidence_refs={"decision_id": decision_record.id, "original": decision_record.original_value, "corrected": corrected_value},
            project_id=task.project_id if hasattr(task, 'project_id') else None,
            document_id=task.document_id,
            sheet_id=task.sheet_id,
            job_id=task.job_id
        )

        return decision_record

    # ==========================================
    # 4. Trazabilidad de Decisiones
    # ==========================================

    def list_traces_by_entity(self, entity_type: str, entity_id: str) -> List[DecisionTrace]:
        return self.repo.list_traces_by_entity(entity_type, entity_id)
