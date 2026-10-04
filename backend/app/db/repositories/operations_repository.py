from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from app.db.models.operations import (
    ProcessingJob, JobEvent, ConfidencePolicy, ReviewTask, ReviewDecision, DecisionTrace
)

class OperationsRepository:
    """Repositorio unificado para gestión de jobs, políticas, review queue y trazabilidad de decisiones."""

    def __init__(self, db: Session):
        self.db = db

    # ==========================================
    # 1. ProcessingJob & JobEvent
    # ==========================================

    def create_job(
        self,
        job_type: str,
        target_type: str,
        target_id: str,
        project_id: Optional[str] = None,
        parent_job_id: Optional[str] = None,
        pipeline_name: str = "standard_pipeline",
        pipeline_version: str = "v1.0",
        requested_by: str = "system",
        priority: int = 5,
        input_payload: Optional[Dict[str, Any]] = None,
        max_retries: int = 3,
        organization_id: Optional[str] = None
    ) -> ProcessingJob:
        if not organization_id and project_id:
            from app.db.models.core import Project
            proj = self.db.query(Project).filter(Project.id == project_id).first()
            if proj:
                organization_id = proj.organization_id

        if not organization_id and target_type == "sheet":
            from app.db.models.document_memory import DocumentSheet, Document
            sheet = self.db.query(DocumentSheet).filter(DocumentSheet.id == target_id).first()
            if sheet and sheet.document_id:
                doc = self.db.query(Document).filter(Document.id == sheet.document_id).first()
                if doc:
                    organization_id = doc.organization_id
                    if not project_id:
                        project_id = doc.project_id

        if not organization_id:
            from app.db.models.core import Organization
            org = self.db.query(Organization).first()
            if org:
                organization_id = org.id
            else:
                organization_id = "default-org-uuid"

        job = ProcessingJob(
            organization_id=organization_id,
            job_type=job_type,
            target_type=target_type,
            target_id=target_id,
            project_id=project_id,
            parent_job_id=parent_job_id,
            pipeline_name=pipeline_name,
            pipeline_version=pipeline_version,
            requested_by=requested_by,
            priority=priority,
            input_payload=input_payload or {},
            max_retries=max_retries,
            status="queued",
            progress_percent=0,
            current_stage="queued"
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)

        self.record_event(
            job_id=job.id,
            event_type="created",
            status_after="queued",
            stage="init",
            message=f"Job de tipo '{job_type}' creado y encolado.",
            actor_type="system"
        )
        return job

    def get_job(self, job_id: str) -> Optional[ProcessingJob]:
        return self.db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()

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
        query = self.db.query(ProcessingJob)
        if status:
            query = query.filter(ProcessingJob.status == status)
        if job_type:
            query = query.filter(ProcessingJob.job_type == job_type)
        if target_type:
            query = query.filter(ProcessingJob.target_type == target_type)
        if target_id:
            query = query.filter(ProcessingJob.target_id == target_id)
        if project_id:
            query = query.filter(ProcessingJob.project_id == project_id)
        return query.order_by(ProcessingJob.created_at.desc()).offset(offset).limit(limit).all()

    def update_job_status(
        self,
        job_id: str,
        status: str,
        stage: Optional[str] = None,
        progress_percent: Optional[int] = None,
        result_summary: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        actor_type: str = "worker"
    ) -> Optional[ProcessingJob]:
        job = self.get_job(job_id)
        if not job:
            return None

        status_before = job.status
        job.status = status
        if stage:
            job.current_stage = stage
        if progress_percent is not None:
            job.progress_percent = progress_percent
        if result_summary is not None:
            job.result_summary = result_summary
        if error_code is not None:
            job.error_code = error_code
        if error_message is not None:
            job.error_message = error_message

        now = datetime.utcnow()
        if status == "running" and not job.started_at:
            job.started_at = now
        elif status == "completed":
            job.completed_at = now
            job.progress_percent = 100
        elif status == "failed":
            job.failed_at = now
        elif status == "cancelled":
            job.cancelled_at = now

        self.db.commit()
        self.db.refresh(job)

        self.record_event(
            job_id=job.id,
            event_type=status,
            status_before=status_before,
            status_after=status,
            stage=stage or job.current_stage,
            message=error_message if status == "failed" else f"Job en estado '{status}' (etapa: {job.current_stage})",
            actor_type=actor_type
        )
        return job

    def record_event(
        self,
        job_id: str,
        event_type: str,
        status_before: Optional[str] = None,
        status_after: Optional[str] = None,
        stage: Optional[str] = None,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        actor_type: str = "system",
        actor_id: Optional[str] = None
    ) -> JobEvent:
        event_details = dict(details or {})
        if actor_type:
            event_details["actor_type"] = actor_type
        if actor_id:
            event_details["actor_id"] = actor_id

        event = JobEvent(
            job_id=job_id,
            event_type=event_type,
            from_status=status_before,
            to_status=status_after or "queued",
            actor_type=actor_type or "system",
            actor_id=actor_id,
            stage=stage,
            message=message,
            details=event_details
        )
        self.db.add(event)
        self.db.commit()
        try:
            self.db.refresh(event)
        except Exception:
            pass
        return event

    def list_events_by_job(self, job_id: str) -> List[JobEvent]:
        return self.db.query(JobEvent).filter(JobEvent.job_id == job_id).order_by(JobEvent.created_at.asc()).all()

    # ==========================================
    # 2. ConfidencePolicy
    # ==========================================

    def create_policy(self, policy: ConfidencePolicy) -> ConfidencePolicy:
        self.db.add(policy)
        self.db.commit()
        self.db.refresh(policy)
        return policy

    def get_policy_by_name(self, name: str) -> Optional[ConfidencePolicy]:
        return self.db.query(ConfidencePolicy).filter(ConfidencePolicy.name == name).first()

    def get_active_policy(
        self,
        task_type: Optional[str] = None,
        applies_to: Optional[str] = None,
        discipline: Optional[str] = None
    ) -> Optional[ConfidencePolicy]:
        target_type = task_type or applies_to or "all"
        query = self.db.query(ConfidencePolicy).filter(
            ConfidencePolicy.is_active == True
        )
        if target_type and target_type != "all":
            query = query.filter(
                (ConfidencePolicy.task_type == target_type) | (ConfidencePolicy.task_type == "all")
            )
        if discipline and discipline != "all":
            query_disc = query.filter(
                (ConfidencePolicy.discipline == discipline) | (ConfidencePolicy.discipline == "all")
            ).first()
            if query_disc:
                return query_disc
        return query.first()

    def list_policies(self, task_type: Optional[str] = None) -> List[ConfidencePolicy]:
        query = self.db.query(ConfidencePolicy)
        if task_type:
            query = query.filter(ConfidencePolicy.task_type == task_type)
        return query.order_by(ConfidencePolicy.task_type.asc(), ConfidencePolicy.name.asc()).all()

    # ==========================================
    # 3. ReviewTask & ReviewDecision
    # ==========================================

    def create_review_task(
        self,
        task_type: str,
        reason_code: str,
        reason_message: str,
        confidence: Optional[float] = None,
        priority: str = "medium",
        organization_id: Optional[str] = None,
        project_id: Optional[str] = None,
        source_asset_id: Optional[str] = None,
        document_id: Optional[str] = None,
        sheet_id: Optional[str] = None,
        job_id: Optional[str] = None,
        evidence_refs: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None
    ) -> ReviewTask:
        # Resolver organization_id si no se provee directamente
        resolved_org_id = organization_id
        if not resolved_org_id and document_id:
            from app.db.models.document_memory import Document
            doc = self.db.query(Document).filter(Document.id == document_id).first()
            if doc and doc.organization_id:
                resolved_org_id = doc.organization_id

        if not resolved_org_id and sheet_id:
            from app.db.models.document_memory import DocumentSheet, Document
            sheet = self.db.query(DocumentSheet).filter(DocumentSheet.id == sheet_id).first()
            if sheet:
                doc = self.db.query(Document).filter(Document.id == sheet.document_id).first()
                if doc and doc.organization_id:
                    resolved_org_id = doc.organization_id

        if not resolved_org_id:
            from app.db.models.core import Organization
            first_org = self.db.query(Organization).first()
            resolved_org_id = first_org.id if first_org else "388d7837-9c5d-45fb-b3eb-69909a915e43"

        # Sanitizar y truncar reason_code a 50 caracteres (límite de la columna BD)
        safe_reason_code = (reason_code or "UNSPECIFIED")[:50]

        # Prevenir duplicados de tareas abiertas con el mismo target y reason_code
        query = self.db.query(ReviewTask).filter(
            ReviewTask.status == "open",
            ReviewTask.task_type == task_type,
            ReviewTask.reason_code == safe_reason_code
        )
        if sheet_id:
            query = query.filter(ReviewTask.sheet_id == sheet_id)
        elif document_id:
            query = query.filter(ReviewTask.document_id == document_id)
        elif job_id:
            query = query.filter(ReviewTask.job_id == job_id)

        existing = query.first()
        if existing:
            return existing

        task = ReviewTask(
            organization_id=resolved_org_id,
            task_type=task_type,
            priority=priority,
            status="open",
            reason_code=safe_reason_code,
            reason_message=reason_message,
            confidence=confidence,
            project_id=project_id,
            document_id=document_id,
            sheet_id=sheet_id,
            job_id=job_id,
            evidence_refs=evidence_refs or {},
            payload=payload or {}
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def get_review_task(self, task_id: str) -> Optional[ReviewTask]:
        return self.db.query(ReviewTask).filter(ReviewTask.id == task_id).first()

    def list_review_tasks(
        self,
        status: Optional[str] = None,
        task_type: Optional[str] = None,
        priority: Optional[str] = None,
        project_id: Optional[str] = None
    ) -> List[ReviewTask]:
        query = self.db.query(ReviewTask)
        if status:
            query = query.filter(ReviewTask.status == status)
        if task_type:
            query = query.filter(ReviewTask.task_type == task_type)
        if priority:
            query = query.filter(ReviewTask.priority == priority)
        if project_id:
            query = query.filter(ReviewTask.project_id == project_id)
        return query.order_by(ReviewTask.created_at.desc()).all()

    def record_decision(
        self,
        task_id: str,
        decision: str,
        corrected_value: Optional[Dict[str, Any]] = None,
        reviewer: str = "auditor_qa",
        reason_code: Optional[str] = None,
        notes: Optional[str] = None
    ) -> ReviewDecision:
        task = self.get_review_task(task_id)
        if not task:
            raise ValueError(f"ReviewTask '{task_id}' no encontrada.")

        # Crear registro inmutable de decisión humana
        decision_rec = ReviewDecision(
            review_task_id=task.id,
            decision=decision,
            original_value=task.payload,
            corrected_value=corrected_value,
            reviewer=reviewer,
            reason_code=reason_code or task.reason_code,
            notes=notes
        )
        self.db.add(decision_rec)

        # Actualizar estado de la tarea
        task.status = decision
        task.resolved_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(decision_rec)
        return decision_rec

    # ==========================================
    # 4. DecisionTrace
    # ==========================================

    def record_trace(
        self,
        trace_type: str,
        entity_type: str,
        entity_id: str,
        engine_name: str,
        engine_version: str,
        decision_status: str,
        explanation: str,
        confidence: Optional[float] = None,
        organization_id: Optional[str] = None,
        project_id: Optional[str] = None,
        policy_id: Optional[str] = None,
        policy_version: Optional[str] = None,
        template_id: Optional[str] = None,
        template_version: Optional[str] = None,
        evidence_refs: Optional[Dict[str, Any]] = None,
        source_asset_id: Optional[str] = None,
        document_id: Optional[str] = None,
        sheet_id: Optional[str] = None,
        job_id: Optional[str] = None,
        **kwargs
    ) -> DecisionTrace:
        # Resolver organization_id si no se provee directamente
        resolved_org_id = organization_id
        if not resolved_org_id and project_id:
            from app.db.models.core import Project
            proj = self.db.query(Project).filter(Project.id == project_id).first()
            if proj and proj.organization_id:
                resolved_org_id = proj.organization_id

        if not resolved_org_id and document_id:
            from app.db.models.document_memory import Document
            doc = self.db.query(Document).filter(Document.id == document_id).first()
            if doc and doc.organization_id:
                resolved_org_id = doc.organization_id

        if not resolved_org_id and sheet_id:
            from app.db.models.document_memory import DocumentSheet, Document
            sheet = self.db.query(DocumentSheet).filter(DocumentSheet.id == sheet_id).first()
            if sheet:
                doc = self.db.query(Document).filter(Document.id == sheet.document_id).first()
                if doc and doc.organization_id:
                    resolved_org_id = doc.organization_id

        if not resolved_org_id:
            from app.db.models.core import Organization
            first_org = self.db.query(Organization).first()
            resolved_org_id = first_org.id if first_org else "388d7837-9c5d-45fb-b3eb-69909a915e43"

        trace = DecisionTrace(
            organization_id=resolved_org_id,
            trace_type=(trace_type or "unspecified")[:50],
            entity_type=(entity_type or "unspecified")[:50],
            entity_id=(entity_id or "")[:36],
            project_id=project_id,
            engine_name=(engine_name or "default")[:100],
            engine_version=(engine_version or "1.0")[:30],
            decision_status=(decision_status or "auto_accepted")[:50],
            explanation=explanation,
            confidence=confidence,
            policy_id=policy_id[:36] if policy_id else None,
            policy_version=policy_version[:30] if policy_version else None,
            template_id=template_id[:36] if template_id else None,
            template_version=template_version[:30] if template_version else None,
            evidence_refs=evidence_refs or {},
            source_asset_id=source_asset_id[:36] if source_asset_id else None,
            document_id=document_id[:36] if document_id else None,
            sheet_id=sheet_id[:36] if sheet_id else None,
            job_id=job_id[:36] if job_id else None
        )
        self.db.add(trace)
        self.db.commit()
        self.db.refresh(trace)
        return trace

    def list_traces_by_entity(self, entity_type: str, entity_id: str) -> List[DecisionTrace]:
        return self.db.query(DecisionTrace).filter(
            DecisionTrace.entity_type == entity_type,
            DecisionTrace.entity_id == entity_id
        ).order_by(DecisionTrace.created_at.asc()).all()
