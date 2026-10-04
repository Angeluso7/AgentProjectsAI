import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, Text, JSON, ForeignKey, UniqueConstraint
from app.db.session import Base

class Translation(Base):
    """
    Entidad de persistencia y caché de traducciones asistidas por IA.
    Garantiza inmutabilidad de la fuente, tenancy estricta y versionamiento con estado 'stale'.
    """
    __tablename__ = "translations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    
    source_entity_type = Column(String(50), nullable=False, index=True)
    # extracted_item, source_extraction, rule_document, rule_item, table_cell, etc.
    
    source_entity_id = Column(String(36), nullable=False, index=True)
    source_language = Column(String(10), nullable=False)
    source_language_confidence = Column(Float, nullable=True)
    target_language = Column(String(10), nullable=False, index=True)
    
    # Hash SHA-256 canónico del JSON de campos fuente ordenados por clave
    source_text_hash = Column(String(64), nullable=False, index=True)
    
    translated_title = Column(Text, nullable=True)
    translated_content = Column(Text, nullable=True)
    translated_summary = Column(Text, nullable=True)
    
    # Almacena granularmente cada campo traducido (description, technical_function, standard_reference, ocr_text, etc.)
    translated_fields = Column(JSON, default=dict, nullable=False)
    
    provider = Column(String(50), default="gemini", nullable=False)
    model = Column(String(50), default="gemini-1.5-pro", nullable=False)
    prompt_version = Column(String(20), default="v1.0", nullable=False)
    
    # Estados: pending | processing | completed | failed | stale
    translation_status = Column(String(20), default="completed", nullable=False, index=True)
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "source_entity_type",
            "source_entity_id",
            "target_language",
            "source_text_hash",
            name="uq_translations_entity_target_hash"
        ),
    )
