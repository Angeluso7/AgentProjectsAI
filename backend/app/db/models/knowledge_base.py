import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, Text, JSON, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.db.session import Base

class KnowledgeItem(Base):
    """
    Unidad atómica y estructurada de conocimiento operacional del asistente.
    Representa normas, reglas, entregables, lecciones aprendidas de observaciones,
    documentos guía y decisiones de proyecto con ciclo de vida y trazabilidad.
    """
    __tablename__ = "knowledge_items"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True)
    
    # Dominio y tipo de conocimiento
    domain = Column(String(50), nullable=False, index=True)
    # normative_knowledge, rule_knowledge, deliverable_knowledge, guide_document_knowledge,
    # review_knowledge, observation_rfi_knowledge, project_knowledge, feedback_learning_knowledge
    
    item_type = Column(String(50), nullable=False, index=True)
    # e.g. normative_article, qaqc_rule, stage_deliverable_spec, sheet_legend_pattern,
    # resolved_observation_lesson, stage_decision_rationale, human_correction_rule
    
    title = Column(String(255), nullable=False)
    summary = Column(Text, nullable=True)
    content_text = Column(Text, nullable=False)
    structured_payload = Column(JSON, default=dict)
    
    discipline = Column(String(50), default="general", nullable=False, index=True)
    stage = Column(String(50), nullable=True, index=True) # e.g. "Ingeniería Básica", "Ingeniería de Detalle"
    
    # Ciclo de vida y gobernanza
    status = Column(String(30), default="draft", nullable=False, index=True)
    # draft, extracted, reviewed, validated, approved_for_reuse, superseded, archived, rejected
    
    is_active_for_reuse = Column(Boolean, default=False, nullable=False, index=True)
    confidence_score = Column(Float, default=1.0, nullable=False)
    
    # Versionamiento y linaje
    version_number = Column(Integer, default=1, nullable=False)
    parent_item_id = Column(String(36), ForeignKey("knowledge_items.id", ondelete="SET NULL"), nullable=True, index=True)
    superseded_by_id = Column(String(36), ForeignKey("knowledge_items.id", ondelete="SET NULL"), nullable=True)
    
    # Vigencia temporal
    valid_from = Column(DateTime, default=datetime.utcnow, nullable=False)
    valid_until = Column(DateTime, nullable=True)
    
    # Trazabilidad al origen del sistema
    source_asset_id = Column(String(36), ForeignKey("source_assets.id", ondelete="SET NULL"), nullable=True, index=True)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True)
    sheet_id = Column(String(36), ForeignKey("document_sheets.id", ondelete="SET NULL"), nullable=True)
    rule_id = Column(String(36), ForeignKey("rule_definitions.id", ondelete="SET NULL"), nullable=True, index=True)
    observation_id = Column(String(36), ForeignKey("audit_observations.id", ondelete="SET NULL"), nullable=True, index=True)
    review_run_id = Column(String(36), ForeignKey("review_runs.id", ondelete="SET NULL"), nullable=True)
    stage_snapshot_id = Column(String(36), ForeignKey("project_stage_report_snapshots.id", ondelete="SET NULL"), nullable=True)
    
    author = Column(String(100), default="system", nullable=False)
    origin_type = Column(String(50), default="manual_entry", nullable=False)
    # manual_auditor, auto_extraction, rule_baseline, observation_resolution, snapshot_synthesis, viewer_capture, web_research
    
    # Canal de Ingesta & Modalidad Canónica
    ingestion_channel = Column(String(50), default="manual_entry", nullable=False, index=True)
    # manual_intake, manual_entry, viewer_capture, rule_derivation, review_finding, ai_web_search, document_request
    
    modality = Column(String(50), default="text", nullable=False, index=True)
    # text, image, table, symbol, rule, observation, web_research, checklist, deliverable_spec
    
    # Metadatos visuales
    visual_crop_url = Column(String(500), nullable=True)
    legend_reference = Column(String(255), nullable=True)
    
    provenance_trace = Column(JSON, default=list) # [{action, from_status, to_status, author, timestamp, notes}]
    tags = Column(JSON, default=list) # ["OGUC", "ancho_puertas", "ARQ", "resuelto"]
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relaciones
    organization = relationship("Organization")
    project = relationship("Project")
    chunks = relationship("KnowledgeChunk", back_populates="knowledge_item", cascade="all, delete-orphan")
    source_asset = relationship("SourceAsset")
    document = relationship("Document")
    sheet = relationship("DocumentSheet")
    rule = relationship("RuleDefinition")
    observation = relationship("AuditObservation")
    stage_snapshot = relationship("ProjectStageReportSnapshot")


class KnowledgeChunk(Base):
    """
    Fragmento de texto normalizado e indexable derivado de un KnowledgeItem.
    Preparado para búsqueda semántica, scoring contextual y vectorización RAG.
    """
    __tablename__ = "knowledge_chunks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    knowledge_item_id = Column(String(36), ForeignKey("knowledge_items.id", ondelete="CASCADE"), nullable=False, index=True)
    
    chunk_index = Column(Integer, default=0, nullable=False)
    chunk_title = Column(String(200), nullable=True)
    chunk_text = Column(Text, nullable=False)
    token_count = Column(Integer, default=0, nullable=False)
    
    metadata_payload = Column(JSON, default=dict) # Metadatos contextuales para el recuperador
    embedding_json = Column(JSON, nullable=True) # Array numérico serializado para RAG / embeddings
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relaciones
    knowledge_item = relationship("KnowledgeItem", back_populates="chunks")
