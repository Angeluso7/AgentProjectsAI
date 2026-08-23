import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, JSON, Boolean
from app.db.session import Base

class KnowledgeAsset(Base):
    """Activo de conocimiento guía unificado (norma, catálogo de símbolos, manual de criterios, plantilla)."""
    __tablename__ = "knowledge_assets"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code = Column(String(100), unique=True, index=True, nullable=False) # e.g. "OGUC-CHILE-2024-ASSET"
    title = Column(String(255), nullable=False)
    asset_type = Column(String(50), nullable=False) # standard, guide_manual, title_block_template, symbol_library, ontology
    discipline = Column(String(50), default="general", nullable=False)
    version = Column(String(30), default="1.0")
    
    description = Column(Text, nullable=True)
    file_path = Column(String(500), nullable=True)
    content_payload = Column(JSON, default=dict)
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
