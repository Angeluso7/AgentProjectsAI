import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, Text, JSON, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.db.session import Base

class InformationAcquisitionRequest(Base):
    """
    Entidad operativa para el registro, trazabilidad y gobernanza de faltantes de información,
    solicitudes de permiso de búsqueda Web-First con IA y solicitudes formales de documentación técnica.
    """
    __tablename__ = "information_acquisition_requests"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True)
    
    stage = Column(String(50), nullable=True, index=True) # e.g. "Ingeniería Básica", "Ingeniería de Detalle"
    discipline = Column(String(50), default="general", nullable=False, index=True) # architecture, electrical, structural, general
    
    # -------------------------------------------------------------------------
    # 1. Detección del Faltante
    # -------------------------------------------------------------------------
    missing_topic = Column(String(255), nullable=False) # e.g. "Criterio de Resistencia al Fuego de Muros Medianeros"
    gap_description = Column(Text, nullable=False)
    detection_source = Column(String(50), default="assistant_evaluator", nullable=False) 
    # assistant_evaluator, rule_engine_verifier, completeness_gatekeeper, manual_auditor
    
    # -------------------------------------------------------------------------
    # 2. Evaluación Interna RAG
    # -------------------------------------------------------------------------
    internal_rag_status = Column(String(30), default="insufficient", nullable=False) # resolved, insufficient, not_found
    internal_rag_score = Column(Float, default=0.0, nullable=False)
    internal_rag_matches_count = Column(Integer, default=0, nullable=False)
    
    # -------------------------------------------------------------------------
    # 3. Política Web-First & Permiso de Búsqueda
    # -------------------------------------------------------------------------
    permission_status = Column(String(30), default="pending_permission", nullable=False, index=True)
    # pending_permission, approved, rejected, not_required
    
    permission_requested_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    permission_granted_by = Column(String(100), nullable=True) # Email o ID del usuario que autorizó
    permission_granted_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    
    # -------------------------------------------------------------------------
    # 4. Ejecución de Búsqueda Web Asistida con IA & Límites
    # -------------------------------------------------------------------------
    action_type = Column(String(50), default="web_search", nullable=False) # web_search, document_request, internal_lookup
    web_search_query = Column(String(500), nullable=True)
    web_search_executed = Column(Boolean, default=False, nullable=False)
    web_search_executed_at = Column(DateTime, nullable=True)
    web_search_result_summary = Column(Text, nullable=True)
    web_search_sources = Column(JSON, default=list) # [{title, url, snippet, credibility_score}]
    
    # Límites operativos de búsqueda
    iteration_count = Column(Integer, default=0, nullable=False)
    max_iterations = Column(Integer, default=3, nullable=False)
    search_sources_limit = Column(Integer, default=5, nullable=False)
    
    # -------------------------------------------------------------------------
    # 5. Evaluación de Suficiencia & Escalamiento a Documentación
    # -------------------------------------------------------------------------
    adequacy_status = Column(String(50), default="pending_evaluation", nullable=False)
    # pending_evaluation, sufficient, partially_sufficient, insufficient_project_doc_needed, rejected_by_user
    
    adequacy_classification = Column(String(64), default="pending", nullable=False)
    # sufficient, partially_sufficient, insufficient, not_found, not_applicable
    
    relevance_score = Column(Float, default=0.0, nullable=False)
    confidence_score = Column(Float, default=0.0, nullable=False)
    coverage_score = Column(Float, default=0.0, nullable=False)
    overall_adequacy_score = Column(Float, default=0.0, nullable=False)
    
    termination_reason = Column(String(64), nullable=True)
    # resolved_satisfactory, partial_needs_validation, insufficient_document_requested,
    # cancelled_by_user, exhausted_max_attempts, not_applicable_private_project_data
    
    requested_document_type = Column(String(100), nullable=True) # e.g. "Memoria de Cálculo de Estructuras", "Plano de Detalles"
    requested_document_justification = Column(Text, nullable=True)
    suggested_responsible = Column(String(100), nullable=True) # e.g. "Ingeniero Calculista"
    escalation_details = Column(JSON, default=dict) # {missing_information_details, why_web_internal_failed, requested_document_type, suggested_responsible, audit_impact_justification, unlocked_deliverables_and_rules, escalated_at}
    
    # -------------------------------------------------------------------------
    # 6. Trazabilidad & Conocimiento Incorporado
    # -------------------------------------------------------------------------
    created_knowledge_item_id = Column(String(36), ForeignKey("knowledge_items.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(String(30), default="open", nullable=False, index=True) # open, in_progress, resolved, escalated, closed
    
    metadata_payload = Column(JSON, default=dict)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relaciones
    organization = relationship("Organization")
    project = relationship("Project")
    created_knowledge_item = relationship("KnowledgeItem")
