import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, Text, JSON, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.db.session import Base

class AuditReport(Base):
    """Informe técnico formal de auditoría y control de calidad (QA/QC)."""
    __tablename__ = "audit_reports"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    sheet_id = Column(String(36), ForeignKey("document_sheets.id", ondelete="SET NULL"), nullable=True, index=True)
    
    report_type = Column(String(50), default="technical_audit_qaqc", nullable=False) # technical_audit_qaqc, normative_compliance_matrix, executive_summary
    report_scope = Column(String(30), default="sheet", nullable=False) # sheet, document, project
    status = Column(String(30), default="completed", nullable=False) # generating, completed, failed
    generated_by = Column(String(100), default="system_audit_engine", nullable=False)
    
    source_rule_execution_ids = Column(JSON, default=list)
    source_finding_ids = Column(JSON, default=list)
    summary = Column(JSON, default=dict) # {"total_findings": 3, "by_severity": {...}, "by_status": {...}, "rules_evaluated_count": 6}
    
    artifact_pdf_path = Column(String(500), nullable=True)
    artifact_json_path = Column(String(500), nullable=True)
    artifact_bundle_path = Column(String(500), nullable=True)
    manifest_hash = Column(String(64), nullable=True) # SHA-256 del manifest.json
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relaciones
    document = relationship("Document")
    sheet = relationship("DocumentSheet")
    manifest = relationship("EvidenceManifest", back_populates="report", uselist=False, cascade="all, delete-orphan")


class EvidenceManifest(Base):
    """Manifiesto de integridad basado en hashes SHA-256 de los artefactos y evidencias."""
    __tablename__ = "evidence_manifests"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    report_id = Column(String(36), ForeignKey("audit_reports.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    
    manifest_json = Column(JSON, nullable=False) # {"report_id": "...", "files": [{"path": "...", "sha256": "...", "size_bytes": 123}]}
    sha256_bundle = Column(String(64), nullable=True) # SHA-256 del archivo zip exportable
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relaciones
    report = relationship("AuditReport", back_populates="manifest")


class ProjectStageReportSnapshot(Base):
    """Snapshot inmutable de cierre y consolidación de auditoría técnica por proyecto y por etapa."""
    __tablename__ = "project_stage_report_snapshots"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    
    stage = Column(String(50), nullable=False, index=True) # e.g. "Ingeniería Básica", "Ingeniería de Detalle"
    revision_number = Column(Integer, default=1, nullable=False, index=True) # 1, 2, 3...
    title = Column(String(255), nullable=False)
    
    global_stage_verdict = Column(String(50), nullable=False, index=True) 
    # aprobable, aprobable_con_observaciones, parcial_incompleta, no_aprobable_bloqueada
    verdict_rationale = Column(Text, nullable=False)
    
    completeness_summary = Column(JSON, default=dict, nullable=False)
    audit_verdicts_summary = Column(JSON, default=dict, nullable=False)
    observations_summary = Column(JSON, default=dict, nullable=False)
    delta_evolution_summary = Column(JSON, default=dict, nullable=False)
    
    artifact_pdf_path = Column(String(500), nullable=True)
    artifact_json_path = Column(String(500), nullable=True)
    manifest_hash = Column(String(64), nullable=True) # SHA-256 del json emitido
    
    issued_by = Column(String(100), default="auditor_lead", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relaciones
    organization = relationship("Organization")
    project = relationship("Project")

