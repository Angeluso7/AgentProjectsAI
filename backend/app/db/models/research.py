import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, Text, JSON, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.db.session import Base

class ResearchQuery(Base):
    """Registro persistente de consultas y prompts de investigación técnica en Internet."""
    __tablename__ = "research_queries"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    
    search_prompt = Column(Text, nullable=False)
    discipline = Column(String(50), default="Arquitectura", nullable=False, index=True)
    document_type = Column(String(50), default="norma", nullable=False)
    authority = Column(String(150), nullable=True)
    focus_areas = Column(JSON, default=list) # e.g. ["accesibilidad", "rampas", "evacuacion"]
    
    status = Column(String(30), default="completed", nullable=False) # in_progress, completed, failed
    metadata_payload = Column(JSON, default=dict)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relaciones
    results = relationship("ResearchResult", back_populates="query", cascade="all, delete-orphan")


class ResearchResult(Base):
    """Resultado estructurado y sintetizado de una investigación en Internet."""
    __tablename__ = "research_results"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    query_id = Column(String(36), ForeignKey("research_queries.id", ondelete="CASCADE"), nullable=False, index=True)
    source_extraction_id = Column(String(36), ForeignKey("source_extractions.id", ondelete="SET NULL"), nullable=True, index=True)
    
    title = Column(String(255), nullable=False)
    executive_summary = Column(Text, nullable=True)
    total_items_found = Column(Integer, default=0, nullable=False)
    
    raw_payload = Column(JSON, default=dict)
    metadata_info = Column(JSON, default=dict)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relaciones
    query = relationship("ResearchQuery", back_populates="results")
    sources = relationship("ResearchSource", back_populates="result", cascade="all, delete-orphan")
    items = relationship("ResearchItem", back_populates="result", cascade="all, delete-orphan")


class ResearchSource(Base):
    """Cita, fuente web, enlace o documento externo recuperado durante la investigación."""
    __tablename__ = "research_sources"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    result_id = Column(String(36), ForeignKey("research_results.id", ondelete="CASCADE"), nullable=False, index=True)
    
    title = Column(String(255), nullable=False)
    url = Column(String(500), nullable=False)
    domain = Column(String(150), nullable=False)
    snippet = Column(Text, nullable=True)
    retrieved_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    reliability_score = Column(Float, default=0.9, nullable=False)

    # Relaciones
    result = relationship("ResearchResult", back_populates="sources")


class ResearchItem(Base):
    """Elemento individual estructurado derivado de la investigación web (regla propuesta, parámetro, concepto)."""
    __tablename__ = "research_items"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    result_id = Column(String(36), ForeignKey("research_results.id", ondelete="CASCADE"), nullable=False, index=True)
    
    item_type = Column(String(50), nullable=False) # rule, definition, procedure, table, reference
    item_nature = Column(String(50), default="proposed_rule", nullable=False) # proposed_rule, support_research, concept, reference
    
    title = Column(String(255), nullable=False)
    code_or_number = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    content_text = Column(Text, nullable=True)
    source_reference = Column(String(500), nullable=True)
    governance_note = Column(Text, nullable=True)
    
    validation_status = Column(String(30), default="pending_review", nullable=False) # pending_review, validated, rejected
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relaciones
    result = relationship("ResearchResult", back_populates="items")
