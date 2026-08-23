import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, Text, JSON, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.db.session import Base

class AuditObservation(Base):
    """Objeto formal de auditoría técnica, solicitud de información (RFI) o bloqueo documental."""
    __tablename__ = "audit_observations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    
    stage = Column(String(50), nullable=False, index=True) # e.g. "Ingeniería de Detalle"
    code = Column(String(50), nullable=False, index=True) # e.g. "OBS-ARQ-001", "RFI-EST-002", "BLK-GEN-003"
    item_type = Column(String(50), nullable=False, index=True) # technical_observation, information_request, document_blocker, minor_missing
    
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    recommendation = Column(Text, nullable=True)
    discipline = Column(String(50), default="general", nullable=False, index=True)
    severity = Column(String(20), default="medium", nullable=False, index=True) # critical, high, medium, low, info
    status = Column(String(30), default="draft", nullable=False, index=True) # draft, issued, answered, provisioned, validated, closed, rejected, superseded
    
    # Trazabilidad con el origen técnico
    rule_finding_id = Column(String(36), ForeignKey("rule_findings.id", ondelete="SET NULL"), nullable=True, index=True)
    rule_id = Column(String(36), ForeignKey("rule_definitions.id", ondelete="SET NULL"), nullable=True)
    rule_code = Column(String(100), nullable=True, index=True)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True)
    sheet_id = Column(String(36), ForeignKey("document_sheets.id", ondelete="SET NULL"), nullable=True, index=True)
    review_run_id = Column(String(36), ForeignKey("review_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Entregable requerido y nueva evidencia provisionada
    required_deliverable_type = Column(String(50), nullable=True)
    provisioned_document_id = Column(String(36), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    resolution_notes = Column(Text, nullable=True)
    
    issued_by = Column(String(100), default="system", nullable=False)
    assigned_to = Column(String(100), nullable=True)
    
    issued_at = Column(DateTime, nullable=True)
    answered_at = Column(DateTime, nullable=True)
    provisioned_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    
    # Historial y trazabilidad de cambios de estado y re-evaluaciones delta
    history_trace = Column(JSON, default=list) # [{ from_status, to_status, action, author, notes, timestamp, delta_run_details }]
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relaciones
    organization = relationship("Organization")
    project = relationship("Project")
    finding = relationship("RuleFinding")
    rule = relationship("RuleDefinition")
    document = relationship("Document", foreign_keys=[document_id])
    sheet = relationship("DocumentSheet")
    review_run = relationship("ReviewRun")
    provisioned_document = relationship("Document", foreign_keys=[provisioned_document_id])
    responses = relationship("ObservationResponse", back_populates="observation", cascade="all, delete-orphan", order_by="ObservationResponse.created_at.asc()")


class ObservationResponse(Base):
    """Respuesta o aclaración técnica emitida por el proyectista / contratista sobre una observación o RFI."""
    __tablename__ = "observation_responses"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    observation_id = Column(String(36), ForeignKey("audit_observations.id", ondelete="CASCADE"), nullable=False, index=True)
    
    author = Column(String(100), nullable=False)
    author_role = Column(String(50), default="contractor", nullable=False)
    response_text = Column(Text, nullable=False)
    attached_document_id = Column(String(36), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relaciones
    observation = relationship("AuditObservation", back_populates="responses")
    attached_document = relationship("Document")
