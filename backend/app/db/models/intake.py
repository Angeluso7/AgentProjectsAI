import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Text, JSON, Boolean, ForeignKey
from app.db.session import Base

class SourceAsset(Base):
    """Entidad unificada de intake y gobierno para el registro, clasificación y trazabilidad de entradas al sistema."""
    __tablename__ = "source_assets"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Clasificación y Origen
    source_type = Column(String(50), nullable=False, index=True) 
    # analysis_document, template_document, symbol_reference, normative_document, web_normative_source
    
    source_origin = Column(String(50), default="local_upload", nullable=False)
    # local_upload, web_scrape, api_sync, manual_entry
    
    document_type = Column(String(50), nullable=True) # blueprint_pdf, standard_doc, symbol_catalog, webpage_article
    discipline = Column(String(50), default="general", nullable=False, index=True) # architecture, electrical, structural, general
    
    # Metadatos del activo
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    file_path = Column(String(500), nullable=True)
    original_filename = Column(String(255), nullable=True)
    file_size_bytes = Column(Integer, nullable=True)
    source_url = Column(String(500), nullable=True)
    sha256 = Column(String(64), nullable=True, index=True)
    mime_type = Column(String(100), default="application/pdf", nullable=False)
    version = Column(String(50), default="1.0", nullable=False)
    
    # Ciclo de vida y gobierno
    status = Column(String(30), default="registered", nullable=False) 
    # registered, ingesting, ingested, rejected, failed
    
    approval_status = Column(String(30), default="pending_review", nullable=False, index=True)
    # pending_review, approved, rejected, not_required
    
    linked_memory_target = Column(String(50), nullable=False, index=True)
    # document_memory, template_memory, normative_memory
    
    owner = Column(String(100), default="system", nullable=False)
    approval_notes = Column(Text, nullable=True)
    reviewed_by = Column(String(100), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    
    metadata_payload = Column(JSON, default=dict)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
