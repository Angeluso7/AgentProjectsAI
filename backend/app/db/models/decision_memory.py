import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, Text, JSON, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.db.session import Base

class RuleDefinition(Base):
    """Definición declarativa y versionada de una regla determinística QA/QC."""
    __tablename__ = "rule_definitions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code = Column(String(100), unique=True, index=True, nullable=False) # e.g. "RULE_DOOR_COUNT_MATCH_V1"
    name = Column(String(200), nullable=False)
    category = Column(String(50), index=True, nullable=False) # cross_reconciliation, document_integrity, normative_compliance, geometry_qa
    discipline = Column(String(50), default="general", nullable=False) # architecture, electrical, structural, general
    severity_default = Column(String(20), default="medium", nullable=False) # critical, high, medium, low, info
    description = Column(Text, nullable=False)
    
    input_requirements = Column(JSON, default=dict) # {"requires_tables": ["door_schedule"], "requires_symbols": ["door_symbol"]}
    rule_logic_type = Column(String(50), default="count_reconciliation", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    version = Column(String(30), default="1.0", nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relaciones
    executions = relationship("RuleExecution", back_populates="rule", cascade="all, delete-orphan")
    findings = relationship("RuleFinding", back_populates="rule")


class RuleExecution(Base):
    """Registro de la ejecución de una regla sobre un documento o lámina específica."""
    __tablename__ = "rule_executions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String(36), ForeignKey("processing_jobs.id", ondelete="SET NULL"), nullable=True, index=True)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    sheet_id = Column(String(36), ForeignKey("document_sheets.id", ondelete="SET NULL"), nullable=True, index=True)
    rule_id = Column(String(36), ForeignKey("rule_definitions.id", ondelete="CASCADE"), nullable=False, index=True)
    
    rule_version = Column(String(30), default="1.0", nullable=False)
    execution_status = Column(String(30), nullable=False) # passed, failed, warning, not_applicable, insufficient_evidence
    input_snapshot = Column(JSON, default=dict)
    result_summary = Column(JSON, default=dict)
    confidence = Column(Float, default=1.0, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relaciones
    rule = relationship("RuleDefinition", back_populates="executions")
    document = relationship("Document")
    sheet = relationship("DocumentSheet")


class ReviewRun(Base):
    """Sesión o ejecución de auditoría/revisión sobre uno o varios planos."""
    __tablename__ = "review_runs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    
    run_name = Column(String(200), nullable=False) # e.g. "Auditoría Preliminar Entrega 1"
    status = Column(String(30), default="pending") # pending, processing, completed, failed
    rules_applied_count = Column(Integer, default=0)
    findings_count = Column(Integer, default=0)
    execution_time_sec = Column(Float, default=0.0)
    
    summary_stats = Column(JSON, default=dict) # {"critical": 2, "high": 5, "medium": 10, "passed": 45}
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    # Relaciones
    project = relationship("Project", back_populates="review_runs")
    findings = relationship("RuleFinding", back_populates="review_run", cascade="all, delete-orphan")


class RuleFinding(Base):
    """Hallazgo o discrepancia técnica auditada con evidencia vinculada."""
    __tablename__ = "rule_findings"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    review_run_id = Column(String(36), ForeignKey("review_runs.id", ondelete="CASCADE"), nullable=True, index=True)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    sheet_id = Column(String(36), ForeignKey("document_sheets.id", ondelete="CASCADE"), nullable=True, index=True)
    rule_id = Column(String(36), ForeignKey("rule_definitions.id", ondelete="SET NULL"), nullable=True, index=True)
    
    rule_code = Column(String(100), index=True, nullable=False)
    rule_name = Column(String(200), nullable=False)
    category = Column(String(50), nullable=False) # cross_reconciliation, document_integrity, normative_compliance, geometry_qa
    severity = Column(String(20), default="medium", nullable=False) # critical, high, medium, low, info
    status = Column(String(30), default="open", nullable=False) # open, confirmed, dismissed, corrected, accepted_risk
    confidence = Column(Float, default=1.0, nullable=False) # 0.0 - 1.0
    finding_type = Column(String(50), default="reconciliation_mismatch", nullable=False) # reconciliation_mismatch, missing_metadata, missing_required_table, normative_violation, insufficient_evidence
    
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    recommendation = Column(Text, nullable=True)
    
    evidence_refs = Column(JSON, default=dict) # {"symbols": [...], "tables": [...], "normative_clause": "OGUC 4.1.7"}
    expected_value = Column(JSON, nullable=True)
    observed_value = Column(JSON, nullable=True)
    delta = Column(JSON, nullable=True)
    
    source_trace_ids = Column(JSON, default=list)
    review_task_id = Column(String(36), ForeignKey("review_tasks.id", ondelete="SET NULL"), nullable=True, index=True)
    bbox = Column(JSON, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relaciones
    review_run = relationship("ReviewRun", back_populates="findings")
    document = relationship("Document")
    sheet = relationship("DocumentSheet")
    rule = relationship("RuleDefinition", back_populates="findings")
    evidences = relationship("FindingEvidence", back_populates="finding", cascade="all, delete-orphan")
    feedbacks = relationship("HumanFeedback", back_populates="finding", cascade="all, delete-orphan")
    resolutions = relationship("FindingResolution", back_populates="finding", cascade="all, delete-orphan")
    review_task = relationship("ReviewTask")


class FindingResolution(Base):
    """Resolución o dictamen humano sobre un hallazgo de auditoría."""
    __tablename__ = "finding_resolutions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    finding_id = Column(String(36), ForeignKey("rule_findings.id", ondelete="CASCADE"), nullable=False, index=True)
    
    resolution_type = Column(String(50), nullable=False) # confirmed, dismissed, corrected, accepted_risk
    resolved_by = Column(String(100), default="auditor_qa", nullable=False)
    notes = Column(Text, nullable=True)
    corrected_value = Column(JSON, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relaciones
    finding = relationship("RuleFinding", back_populates="resolutions")


class FindingEvidence(Base):
    """Enlace relacional entre un hallazgo y sus evidencias concretas."""
    __tablename__ = "finding_evidences"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    finding_id = Column(String(36), ForeignKey("rule_findings.id", ondelete="CASCADE"), nullable=False)
    
    evidence_type = Column(String(50), nullable=False) # visual_crop, text_snippet, table_row, normative_clause, symbol_count
    reference_id = Column(String(36), nullable=True) # ID de VisualEvidence, ExtractedText, etc.
    description = Column(Text, nullable=True)
    crop_image_path = Column(String(500), nullable=True)
    metadata_info = Column(JSON, default=dict)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relaciones
    finding = relationship("RuleFinding", back_populates="evidences")


class HumanFeedback(Base):
    """Registro de supervisión humana (HITL) sobre un hallazgo."""
    __tablename__ = "human_feedbacks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    finding_id = Column(String(36), ForeignKey("rule_findings.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    action = Column(String(50), nullable=False) # accept_finding, reject_false_positive, correct_detection, mark_exception
    corrected_bbox = Column(JSON, nullable=True)
    corrected_class = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    
    sent_to_active_learning = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relaciones
    finding = relationship("RuleFinding", back_populates="feedbacks")


class DecisionPrecedent(Base):
    """Excepción o criterio aprobado consolidado en la memoria de decisiones."""
    __tablename__ = "decision_precedents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    rule_code = Column(String(100), index=True, nullable=False)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    
    condition_signature = Column(JSON, nullable=False) # Patrón de condiciones que disparan la excepción
    resolution = Column(String(50), nullable=False) # approve_exception, permanent_waiver
    justification = Column(Text, nullable=False)
    approved_by = Column(String(100), nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
