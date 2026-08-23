import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship
from app.db.session import Base

class ProcessingJob(Base):
    """Entidad principal que representa la ejecución asíncrona y auditable de un pipeline o tarea pesada."""
    __tablename__ = "processing_jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    job_type = Column(String(50), nullable=False, index=True)
    # document_ingest, document_rasterize, sheet_ocr, document_ocr, sheet_layout, document_layout, title_block_match, source_ingest
    
    target_type = Column(String(50), nullable=False, index=True) # document, sheet, source_asset, project
    target_id = Column(String(36), nullable=False, index=True)
    project_id = Column(String(36), nullable=True, index=True)
    parent_job_id = Column(String(36), nullable=True, index=True)
    
    pipeline_name = Column(String(100), default="standard_pipeline", nullable=False)
    pipeline_version = Column(String(30), default="v1.0", nullable=False)
    requested_by = Column(String(100), default="system", nullable=False)
    
    status = Column(String(30), default="queued", nullable=False, index=True)
    # queued, running, completed, failed, cancelled, retrying, awaiting_review
    
    priority = Column(Integer, default=5, nullable=False) # 1 (más bajo) a 10 (urgente)
    progress_percent = Column(Integer, default=0, nullable=False)
    current_stage = Column(String(100), default="init", nullable=False)
    
    input_payload = Column(JSON, default=dict)
    result_summary = Column(JSON, default=dict)
    
    error_code = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)
    
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)
    
    queued_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    failed_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relaciones
    events = relationship("JobEvent", back_populates="job", cascade="all, delete-orphan", order_by="JobEvent.created_at.asc()")
    review_tasks = relationship("ReviewTask", back_populates="job", cascade="all, delete-orphan")


class JobEvent(Base):
    """Bitácora inmutable de eventos y transiciones de estado por cada job."""
    __tablename__ = "job_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String(36), ForeignKey("processing_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    
    event_type = Column(String(50), nullable=False)
    # queued, started, stage_changed, progress_updated, completed, failed, retried, review_triggered
    
    from_status = Column(String(30), nullable=True)
    to_status = Column(String(30), nullable=False)
    
    stage = Column(String(100), nullable=True)
    message = Column(Text, nullable=True)
    details = Column(JSON, default=dict)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    job = relationship("ProcessingJob", back_populates="events")


class ConfidencePolicy(Base):
    """Reglas declarativas para el enrutamiento de confianza (auto-accept vs human-review)."""
    __tablename__ = "confidence_policies"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    policy_name = Column(String(100), unique=True, nullable=False)
    version = Column(String(30), default="1.0", nullable=False)
    discipline = Column(String(50), default="all", nullable=False)
    task_type = Column(String(50), nullable=False, index=True)
    # ocr_general, title_block_extraction, layout_segmentation, normative_classification, symbol_detection
    
    auto_accept_threshold = Column(Float, default=0.85, nullable=False)
    review_threshold = Column(Float, default=0.60, nullable=False)
    exception_threshold = Column(Float, default=0.40, nullable=False)
    
    is_active = Column(Boolean, default=True, nullable=False)
    action_on_below_review = Column(String(50), default="send_to_review_queue", nullable=False)
    description = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class ReviewTask(Base):
    """Elemento en cola para triage y revisión humana supervisada (HITL)."""
    __tablename__ = "review_tasks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id = Column(String(36), ForeignKey("processing_jobs.id", ondelete="SET NULL"), nullable=True, index=True)
    project_id = Column(String(36), nullable=True, index=True)
    document_id = Column(String(36), nullable=True, index=True)
    sheet_id = Column(String(36), nullable=True, index=True)
    
    task_type = Column(String(50), nullable=False, index=True)
    # title_block_review, ocr_uncertainty, layout_anomaly, normative_approval, symbol_conflict, rule_finding_review
    
    status = Column(String(30), default="open", nullable=False, index=True)
    # open, in_review, resolved, escalated, dismissed
    
    priority = Column(String(20), default="medium", nullable=False) # low, medium, high, critical
    reason_code = Column(String(50), nullable=False)
    reason_message = Column(Text, nullable=False)
    
    confidence = Column(Float, nullable=True)
    policy_name = Column(String(100), nullable=True)
    
    assigned_to = Column(String(100), nullable=True)
    assigned_at = Column(DateTime, nullable=True)
    
    evidence_refs = Column(JSON, default=dict)
    payload = Column(JSON, default=dict)
    resolution = Column(JSON, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    resolved_at = Column(DateTime, nullable=True)

    # Relaciones
    job = relationship("ProcessingJob", back_populates="review_tasks")
    decisions = relationship("ReviewDecision", back_populates="task", cascade="all, delete-orphan")


class ReviewDecision(Base):
    """Registro inmutable de la resolución dictaminada por un revisor humano."""
    __tablename__ = "review_decisions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String(36), ForeignKey("review_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    
    decision = Column(String(50), nullable=False)
    # approved, corrected, rejected, marked_as_exception
    
    original_value = Column(JSON, nullable=True)
    corrected_value = Column(JSON, nullable=True)
    
    reviewer = Column(String(100), default="auditor_qa", nullable=False)
    reason_code = Column(String(50), nullable=True)
    notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    task = relationship("ReviewTask", back_populates="decisions")


class DecisionTrace(Base):
    """Trazabilidad granular de decisiones técnicas, inferencias y políticas aplicadas."""
    __tablename__ = "decision_traces"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    trace_type = Column(String(50), nullable=False, index=True)
    # ocr_extraction, title_block_field, title_block_match, normative_intake, rule_evaluation
    
    entity_type = Column(String(50), nullable=False) # ExtractedText, TitleBlockExtraction, SheetRegion, SourceAsset, RuleFinding
    entity_id = Column(String(36), nullable=False, index=True)
    
    source_asset_id = Column(String(36), nullable=True)
    document_id = Column(String(36), nullable=True)
    sheet_id = Column(String(36), nullable=True)
    job_id = Column(String(36), nullable=True)
    
    evidence_refs = Column(JSON, default=dict)
    engine_name = Column(String(50), nullable=False)
    engine_version = Column(String(30), nullable=False)
    
    template_id = Column(String(36), nullable=True)
    template_version = Column(String(30), nullable=True)
    policy_id = Column(String(36), nullable=True)
    policy_version = Column(String(30), nullable=True)
    
    confidence = Column(Float, nullable=True)
    decision_status = Column(String(30), nullable=False)
    # auto_accepted, review_required, exception_required, human_approved, human_corrected, human_rejected
    
    explanation = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class ReviewPipelineRun(Base):
    """Ejecución consolidada de punta a punta (One-Click Review) sobre un documento o proyecto."""
    __tablename__ = "review_pipeline_runs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    scope_type = Column(String(30), default="document", nullable=False, index=True) # sheet, document, project
    scope_id = Column(String(36), nullable=False, index=True)
    
    pipeline_version = Column(String(30), default="v1.0", nullable=False)
    requested_by = Column(String(100), default="system_user", nullable=False)
    
    status = Column(String(30), default="queued", nullable=False, index=True)
    # queued, running, completed, failed, cancelled, awaiting_review, partially_completed
    
    current_stage = Column(String(50), default="ingest", nullable=False)
    progress_percent = Column(Integer, default=0, nullable=False)
    
    summary = Column(JSON, default=dict) # {"stages_count": 8, "findings_count": 2, "report_id": "..."}
    final_report_id = Column(String(36), ForeignKey("audit_reports.id", ondelete="SET NULL"), nullable=True)
    
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    failed_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relaciones
    stages = relationship("PipelineStageRun", back_populates="pipeline_run", cascade="all, delete-orphan", order_by="PipelineStageRun.stage_order.asc()")
    final_report = relationship("AuditReport")


class PipelineStageRun(Base):
    """Ejecución granular de una etapa dentro del pipeline One-Click."""
    __tablename__ = "pipeline_stage_runs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    pipeline_run_id = Column(String(36), ForeignKey("review_pipeline_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    
    stage_name = Column(String(50), nullable=False)
    # ingest, ocr, layout, title_block, tables, symbols, rules, reports
    
    stage_order = Column(Integer, nullable=False) # 1 a 8
    status = Column(String(30), default="pending", nullable=False) # pending, running, completed, failed, skipped, warning
    job_id = Column(String(36), ForeignKey("processing_jobs.id", ondelete="SET NULL"), nullable=True)
    
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    result_summary = Column(JSON, default=dict)
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relaciones
    pipeline_run = relationship("ReviewPipelineRun", back_populates="stages")
    job = relationship("ProcessingJob")
