import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, Text, JSON, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.db.session import Base

class ProjectDeliverableRequirement(Base):
    """Requisito documental normativo o estándar por etapa y disciplina."""
    __tablename__ = "project_deliverable_requirements"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    
    stage = Column(String(50), nullable=False, index=True) # e.g. "Ingeniería Básica", "Ingeniería de Detalle"
    discipline = Column(String(50), default="general", nullable=False, index=True) # architecture, structural, etc.
    deliverable_type = Column(String(50), nullable=False, index=True) # plano_general, especificaciones_tecnicas, etc.
    
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    is_mandatory = Column(Boolean, default=True, nullable=False)
    blocked_rule_codes = Column(JSON, default=list) # Reglas que se bloquean si este entregable no está eligible_as_evidence
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relaciones
    organization = relationship("Organization")


class DocumentDeliverable(Base):
    """Asociación de un documento con su tipo de entregable y ciclo de vida de evidencia."""
    __tablename__ = "document_deliverables"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    
    discipline_code = Column(String(50), nullable=True, index=True)
    deliverable_type = Column(String(50), default="plano_general", nullable=False, index=True)
    readiness_status = Column(String(50), default="uploaded", nullable=False, index=True)
    # uploaded, classified, validated, eligible_as_evidence, rejected
    
    validation_notes = Column(Text, nullable=True)
    classified_by = Column(String(100), default="system", nullable=False)
    validated_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relaciones
    project = relationship("Project")
    document = relationship("Document")


class ProjectCompletenessEvaluation(Base):
    """Registro histórico y persistido de la evaluación de completitud documental (Gatekeeper)."""
    __tablename__ = "project_completeness_evaluations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    
    stage = Column(String(50), nullable=False)
    completeness_percentage = Column(Float, default=0.0, nullable=False)
    is_gate_passed = Column(Boolean, default=False, nullable=False)
    
    total_required_count = Column(Integer, default=0, nullable=False)
    eligible_count = Column(Integer, default=0, nullable=False)
    missing_mandatory_count = Column(Integer, default=0, nullable=False)
    missing_optional_count = Column(Integer, default=0, nullable=False)
    blocked_rules_count = Column(Integer, default=0, nullable=False)
    
    deliverables_matrix = Column(JSON, default=list) # Detalle de cada entregable requerido con sus docs asociados
    missing_deliverables = Column(JSON, default=list) # Lista de entregables faltantes
    blocked_rules = Column(JSON, default=list) # Reglas bloqueadas con detalle de motivo
    
    evaluated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relaciones
    project = relationship("Project")
