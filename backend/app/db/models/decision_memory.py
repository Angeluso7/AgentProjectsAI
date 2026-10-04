from __future__ import annotations
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, Text, JSON, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.db.session import Base


class ReviewDiscipline(Base):
    """Especialidad técnica o disciplina de ingeniería (ej: PIPING, ARCHITECTURE)."""
    __tablename__ = "review_disciplines"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code = Column(String(50), unique=True, index=True, nullable=False) # e.g. "PIPING", "GENERAL"
    name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    order_index = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relaciones
    topics = relationship("ReviewTopic", back_populates="discipline", cascade="all, delete-orphan")
    applicabilities = relationship("RuleApplicability", back_populates="discipline", cascade="all, delete-orphan")


class ReviewTopic(Base):
    """Punto o tema de revisión dentro de una especialidad o transversal."""
    __tablename__ = "review_topics"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    discipline_id = Column(String(36), ForeignKey("review_disciplines.id", ondelete="SET NULL"), nullable=True, index=True)
    code = Column(String(100), unique=True, index=True, nullable=False) # e.g. "PID_SYMBOLS", "DOCUMENT_COMPLETENESS"
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    is_transversal = Column(Boolean, default=False, nullable=False)
    enabled_mvp = Column(Boolean, default=False, nullable=False) # Solo PID_SYMBOLS = True en MVP inicial
    order_index = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relaciones
    discipline = relationship("ReviewDiscipline", back_populates="topics")
    applicabilities = relationship("RuleApplicability", back_populates="topic", cascade="all, delete-orphan")


class RuleApplicability(Base):
    """Relación canónica de aplicabilidad entre una regla, una disciplina y un tema de revisión."""
    __tablename__ = "rule_applicabilities"
    __table_args__ = (
        UniqueConstraint("rule_id", "discipline_id", "topic_id", name="uq_rule_discipline_topic"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    rule_id = Column(String(36), ForeignKey("rule_definitions.id", ondelete="CASCADE"), nullable=False, index=True)
    discipline_id = Column(String(36), ForeignKey("review_disciplines.id", ondelete="CASCADE"), nullable=False, index=True)
    topic_id = Column(String(36), ForeignKey("review_topics.id", ondelete="CASCADE"), nullable=False, index=True)

    role = Column(String(30), default="primary", nullable=False) # primary, secondary, general
    source = Column(String(30), default="human", nullable=False) # human, ai_suggested, imported
    approval_status = Column(String(30), default="draft", nullable=False) # draft, proposed, approved, rejected
    reviewer = Column(String(100), nullable=True)
    rationale = Column(Text, nullable=True)
    confidence = Column(Float, default=1.0, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relaciones
    rule = relationship("RuleDefinition", back_populates="applicabilities")
    discipline = relationship("ReviewDiscipline", back_populates="applicabilities")
    topic = relationship("ReviewTopic", back_populates="applicabilities")


class RuleExecutionDependency(Base):
    """Dependencia declarativa entre reglas para ordenamiento topológico y evaluación."""
    __tablename__ = "rule_execution_dependencies"
    __table_args__ = (
        UniqueConstraint("rule_id", "depends_on_rule_id", name="uq_rule_dependency"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    rule_id = Column(String(36), ForeignKey("rule_definitions.id", ondelete="CASCADE"), nullable=False, index=True)
    depends_on_rule_id = Column(String(36), ForeignKey("rule_definitions.id", ondelete="CASCADE"), nullable=False, index=True)
    dependency_type = Column(String(50), default="requires_success", nullable=False) # requires_success, requires_evaluated

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relaciones
    rule = relationship("RuleDefinition", foreign_keys=[rule_id], back_populates="dependencies")
    depends_on_rule = relationship("RuleDefinition", foreign_keys=[depends_on_rule_id], back_populates="dependent_rules")


class RuleDefinition(Base):
    """Definición declarativa y versionada de una regla determinística QA/QC."""
    __tablename__ = "rule_definitions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code = Column(String(100), unique=True, index=True, nullable=False) # e.g. "SYM-UNKNOWN-001"
    name = Column(String(200), nullable=False)
    category = Column(String(50), index=True, nullable=False) # cross_reconciliation, document_integrity, normative_compliance, geometry_qa
    discipline = Column(String(50), default="general", nullable=False) # backward-compatibility string
    severity_default = Column(String(20), default="medium", nullable=False) # critical, high, medium, low, info
    description = Column(Text, nullable=False)

    # Metadatos canónicos de la regla
    rule_scope = Column(String(50), default="specialty", nullable=False) # general, specialty
    execution_phase = Column(Integer, default=5, nullable=False) # 1 a 9
    priority = Column(Integer, default=100, nullable=False) # Prioridad topológica
    enabled = Column(Boolean, default=True, nullable=False)
    source_status = Column(String(30), default="approved", nullable=False) # draft, proposed, approved, deprecated
    requires_data = Column(JSON, default=list) # ["detected_symbols", "symbol_legend"]
    suggested_by_ai = Column(Boolean, default=False, nullable=False)
    classification_confidence = Column(Float, default=1.0, nullable=False)
    classification_rationale = Column(Text, nullable=True)
    applicable_document_types = Column(JSON, default=list) # ["P&ID", "DIAGRAM", "LEGEND"]

    input_requirements = Column(JSON, default=dict) # Requisitos legados o extendidos
    rule_logic_type = Column(String(50), default="count_reconciliation", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    version = Column(String(30), default="1.0", nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Linaje fuente inmutable de la regla
    source_candidate_id = Column(String(36), nullable=True, index=True)
    source_document_id = Column(String(36), nullable=True, index=True)
    source_page = Column(Integer, nullable=True)
    source_bbox = Column(JSON, nullable=True)
    source_excerpt = Column(Text, nullable=True)
    source_hash = Column(String(64), nullable=True)

    # Relaciones
    applicabilities = relationship("RuleApplicability", back_populates="rule", cascade="all, delete-orphan")
    dependencies = relationship("RuleExecutionDependency", foreign_keys=[RuleExecutionDependency.rule_id], back_populates="rule", cascade="all, delete-orphan")
    dependent_rules = relationship("RuleExecutionDependency", foreign_keys=[RuleExecutionDependency.depends_on_rule_id], back_populates="depends_on_rule", cascade="all, delete-orphan")
    executions = relationship("RuleExecution", back_populates="rule", cascade="all, delete-orphan")
    findings = relationship("RuleFinding", back_populates="rule")
    review_decisions = relationship("RuleReviewDecision", back_populates="rule_definition")


class RuleReviewDecision(Base):
    """Auditoría y registro inmutable de decisiones HITL sobre candidatos de reglas normativas."""
    __tablename__ = "rule_review_decisions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    candidate_id = Column(String(36), nullable=False, index=True)
    rule_definition_id = Column(String(36), ForeignKey("rule_definitions.id", ondelete="SET NULL"), nullable=True, index=True)
    decision = Column(String(30), nullable=False) # approve, reject, modify, supersede
    reviewer_id = Column(String(100), nullable=False)
    reviewer_role = Column(String(50), default="auditor", nullable=False)
    reviewer_rationale = Column(Text, nullable=True)
    rule_code = Column(String(100), nullable=True, index=True)
    payload_snapshot = Column(JSON, default=dict)
    previous_state = Column(JSON, default=dict)
    new_state = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relaciones
    rule_definition = relationship("RuleDefinition", back_populates="review_decisions")


class ReviewRun(Base):
    """Sesión o ejecución de auditoría/revisión orquestada por Especialidad y Punto de Revisión."""
    __tablename__ = "review_runs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)

    discipline_id = Column(String(36), ForeignKey("review_disciplines.id", ondelete="SET NULL"), nullable=True, index=True)
    topic_id = Column(String(36), ForeignKey("review_topics.id", ondelete="SET NULL"), nullable=True, index=True)

    run_name = Column(String(200), nullable=False) # e.g. "Piping P&ID Symbols Review"
    execution_mode = Column(String(30), default="production", nullable=False) # production, sandbox
    status = Column(String(30), default="pending", nullable=False) # pending, running, completed, failed, partial
    requested_by = Column(String(100), default="user", nullable=False)
    requested_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    rule_count = Column(Integer, default=0, nullable=False)
    document_count = Column(Integer, default=0, nullable=False)
    rules_applied_count = Column(Integer, default=0, nullable=False)
    findings_count = Column(Integer, default=0, nullable=False)
    execution_time_sec = Column(Float, default=0.0, nullable=False)

    summary = Column(JSON, default=dict) # Resumen de ejecución y hallazgos
    summary_stats = Column(JSON, default=dict) # {"critical": 0, "high": 1, "passed": 4, "not_evaluable": 0}

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    # Relaciones
    project = relationship("Project", back_populates="review_runs")
    discipline = relationship("ReviewDiscipline")
    topic = relationship("ReviewTopic")
    steps = relationship("ReviewRunStep", back_populates="review_run", cascade="all, delete-orphan", order_by="ReviewRunStep.phase")
    executions = relationship("RuleExecution", back_populates="review_run", cascade="all, delete-orphan")
    findings = relationship("RuleFinding", back_populates="review_run", cascade="all, delete-orphan")
    run_documents = relationship("ReviewRunDocument", back_populates="review_run", cascade="all, delete-orphan")
    reports = relationship("ReviewReport", back_populates="review_run", cascade="all, delete-orphan")
    symbol_inventory_groups = relationship("SymbolInventoryGroup", back_populates="review_run", cascade="all, delete-orphan", order_by="SymbolInventoryGroup.display_code.asc()")


class ReviewRunDocument(Base):
    """Documentos incluidos, requeridos o excluidos dentro de una corrida de revisión."""
    __tablename__ = "review_run_documents"
    __table_args__ = (
        UniqueConstraint("review_run_id", "document_id", name="uq_review_run_document"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    review_run_id = Column(String(36), ForeignKey("review_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)

    inclusion_reason = Column(String(100), default="user_selected", nullable=False) # user_selected, auto_required, reference
    document_role = Column(String(50), default="primary", nullable=False) # primary, reference, legend, specification
    status = Column(String(30), default="included", nullable=False) # included, excluded, missing

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relaciones
    review_run = relationship("ReviewRun", back_populates="run_documents")
    document = relationship("Document")


class ReviewRunStep(Base):
    """Etapa técnica de orquestación (Fases 1 a 9) que separa preparación de datos de evaluación QA/QC."""
    __tablename__ = "review_run_steps"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    review_run_id = Column(String(36), ForeignKey("review_runs.id", ondelete="CASCADE"), nullable=False, index=True)

    phase = Column(Integer, nullable=False) # 1 a 9
    phase_name = Column(String(100), nullable=False) # e.g. "Extracción de Simbología"
    step_type = Column(String(50), nullable=False) # preparation | extraction | normalization | evaluation | reporting
    status = Column(String(30), default="queued", nullable=False) # queued | running | succeeded | failed | skipped

    input_summary = Column(JSON, default=dict)
    output_summary = Column(JSON, default=dict)
    error_summary = Column(Text, nullable=True)

    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relaciones
    review_run = relationship("ReviewRun", back_populates="steps")


class RuleExecution(Base):
    """Registro de la evaluación individual de una regla sobre un documento o lámina."""
    __tablename__ = "rule_executions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    review_run_id = Column(String(36), ForeignKey("review_runs.id", ondelete="CASCADE"), nullable=True, index=True)
    job_id = Column(String(36), ForeignKey("processing_jobs.id", ondelete="SET NULL"), nullable=True, index=True)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=True, index=True)
    sheet_id = Column(String(36), ForeignKey("document_sheets.id", ondelete="SET NULL"), nullable=True, index=True)
    rule_id = Column(String(36), ForeignKey("rule_definitions.id", ondelete="CASCADE"), nullable=False, index=True)

    phase = Column(Integer, default=5, nullable=False)
    rule_version = Column(String(30), default="1.0", nullable=False)
    execution_status = Column(String(30), nullable=False) # queued, running, passed, failed, warning, not_evaluable, skipped, error
    input_snapshot = Column(JSON, default=dict)
    result_summary = Column(JSON, default=dict)
    evidence = Column(JSON, default=dict)
    confidence = Column(Float, default=1.0, nullable=False)

    # Not Evaluable Estructurado
    not_evaluable_reason_code = Column(String(50), nullable=True)
    not_evaluable_reason_message = Column(Text, nullable=True)
    missing_requirements = Column(JSON, default=list)
    recommended_action = Column(Text, nullable=True)

    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relaciones
    rule = relationship("RuleDefinition", back_populates="executions")
    review_run = relationship("ReviewRun", back_populates="executions")
    document = relationship("Document")
    sheet = relationship("DocumentSheet")
    findings = relationship("RuleFinding", back_populates="rule_execution")


class RuleFinding(Base):
    """Hallazgo o discrepancia técnica auditada con evidencia vinculada."""
    __tablename__ = "rule_findings"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    review_run_id = Column(String(36), ForeignKey("review_runs.id", ondelete="CASCADE"), nullable=True, index=True)
    rule_execution_id = Column(String(36), ForeignKey("rule_executions.id", ondelete="SET NULL"), nullable=True, index=True)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=True, index=True)
    sheet_id = Column(String(36), ForeignKey("document_sheets.id", ondelete="CASCADE"), nullable=True, index=True)
    rule_id = Column(String(36), ForeignKey("rule_definitions.id", ondelete="SET NULL"), nullable=True, index=True)

    rule_code = Column(String(100), index=True, nullable=False)
    rule_name = Column(String(200), nullable=False)
    category = Column(String(50), nullable=False) # cross_reconciliation, document_integrity, normative_compliance, geometry_qa
    severity = Column(String(20), default="medium", nullable=False) # critical, high, medium, low, info
    status = Column(String(30), default="open", nullable=False) # open, confirmed, dismissed, corrected, accepted_risk
    confidence = Column(Float, default=1.0, nullable=False) # 0.0 - 1.0
    finding_type = Column(String(50), default="reconciliation_mismatch", nullable=False)

    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    recommendation = Column(Text, nullable=True)

    evidence_refs = Column(JSON, default=dict)
    expected_value = Column(JSON, nullable=True)
    observed_value = Column(JSON, nullable=True)
    delta = Column(JSON, nullable=True)

    source_trace_ids = Column(JSON, default=list)
    review_task_id = Column(String(36), ForeignKey("review_tasks.id", ondelete="SET NULL"), nullable=True, index=True)
    bbox = Column(JSON, nullable=True)
    navigation_context = Column(JSON, default=dict) # {"document_id": "...", "page": 1, "bbox": [...], "crop_url": "..."}

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relaciones
    review_run = relationship("ReviewRun", back_populates="findings")
    rule_execution = relationship("RuleExecution", back_populates="findings")
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
    reference_id = Column(String(36), nullable=True)
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

    condition_signature = Column(JSON, nullable=False)
    resolution = Column(String(50), nullable=False) # approve_exception, permanent_waiver
    justification = Column(Text, nullable=False)
    approved_by = Column(String(100), nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class ReviewReport(Base):
    """Reporte persistido de auditoría/revisión exportable en múltiples formatos (JSON, XLSX, PDF)."""
    __tablename__ = "review_reports"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    review_run_id = Column(String(36), ForeignKey("review_runs.id", ondelete="CASCADE"), nullable=False, index=True)

    discipline_id = Column(String(36), ForeignKey("review_disciplines.id", ondelete="SET NULL"), nullable=True, index=True)
    topic_id = Column(String(36), ForeignKey("review_topics.id", ondelete="SET NULL"), nullable=True, index=True)

    report_name = Column(String(255), nullable=False)
    format = Column(String(20), nullable=False) # json | xlsx | pdf
    artifact_path = Column(String(500), nullable=False) # Ruta física relativa/absoluta del archivo generado
    sha256 = Column(String(64), nullable=False) # Hash del archivo para inmutabilidad y auditoría
    status = Column(String(30), default="ready", nullable=False) # generating | ready | failed

    documents_snapshot = Column(JSON, default=list) # Snapshot de IDs y nombres de documentos auditados
    baseline_catalog_version = Column(String(50), nullable=True)
    stats_summary = Column(JSON, default=dict)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relaciones
    project = relationship("Project")
    review_run = relationship("ReviewRun", back_populates="reports")
    discipline = relationship("ReviewDiscipline")
    topic = relationship("ReviewTopic")


class SymbolInventoryGroup(Base):
    """Grupo de ocurrencias de símbolos visualmente equivalentes auditadas en un ReviewRun."""
    __tablename__ = "symbol_inventory_groups"
    __table_args__ = (
        UniqueConstraint("review_run_id", "grouping_key", name="uq_run_grouping_key"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    review_run_id = Column(String(36), ForeignKey("review_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    grouping_key = Column(String(150), nullable=False)
    grouping_method = Column(String(50), default="template_match", nullable=False) # template_match, geometry_signature, visual_similarity, manual
    grouping_confidence = Column(Float, default=1.0, nullable=False)
    grouping_version = Column(String(30), default="v1.0", nullable=False)
    display_code = Column(String(50), nullable=False) # e.g. "SYM-VALVE-001", "U-001", "FIG-001"
    unknown_group_id = Column(String(36), nullable=True) # UUID interno para trazabilidad si luego se cura
    representative_occurrence_id = Column(String(36), nullable=True)
    representative_selection_reason = Column(String(255), nullable=True)

    matched_template_id = Column(String(36), ForeignKey("symbol_templates.id", ondelete="SET NULL"), nullable=True, index=True)
    matched_template_version_id = Column(String(36), ForeignKey("symbol_template_versions.id", ondelete="SET NULL"), nullable=True, index=True)
    canonical_name = Column(String(150), nullable=True)
    description = Column(Text, nullable=True)
    technical_function = Column(Text, nullable=True)
    standard_reference = Column(String(150), nullable=True)
    catalog_status = Column(String(40), default="unknown_symbol", nullable=False, index=True)
    # recognized_production, recognized_sandbox, recognized_reference_only, unknown_symbol, ambiguous_symbol, requires_review, figure_excluded, not_symbol
    confidence_summary = Column(JSON, default=dict) # {"min": 0.85, "max": 0.98, "avg": 0.92}
    total_occurrences = Column(Integer, default=0, nullable=False)
    occurrences_by_document = Column(JSON, default=dict)
    occurrences_by_sheet = Column(JSON, default=dict)
    requires_human_review = Column(Boolean, default=False, nullable=False)
    explanation = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relaciones
    review_run = relationship("ReviewRun", back_populates="symbol_inventory_groups")
    matched_template = relationship("SymbolTemplate", foreign_keys=[matched_template_id])
    matched_template_version = relationship("SymbolTemplateVersion", foreign_keys=[matched_template_version_id])
    occurrences = relationship("DetectedSymbol", back_populates="inventory_group")

