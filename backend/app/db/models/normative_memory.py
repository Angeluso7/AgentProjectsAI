import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Text, JSON, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.db.session import Base

class NormativeDocument(Base):
    """Estándar técnico, ley, ordenanza o norma nacional/internacional (OGUC, NFPA, NEC, ISO, etc.)."""
    __tablename__ = "normative_documents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code = Column(String(50), unique=True, index=True, nullable=False) # e.g. "OGUC-CHILE-2024", "NFPA-101"
    title = Column(String(255), nullable=False)
    authority = Column(String(150), nullable=True) # e.g. "MINVU", "NFPA"
    country = Column(String(10), default="CL")
    discipline = Column(String(50), nullable=False) # architecture, fire_safety, electrical, structural
    version_year = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True)
    
    file_path = Column(String(500), nullable=True)
    metadata_info = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relaciones
    clauses = relationship("NormativeClause", back_populates="document", cascade="all, delete-orphan")


class NormativeClause(Base):
    """Artículo, cláusula o tabla reglamentaria específica."""
    __tablename__ = "normative_clauses"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String(36), ForeignKey("normative_documents.id", ondelete="CASCADE"), nullable=False)
    
    clause_number = Column(String(50), index=True, nullable=False) # e.g. "Art. 4.1.7", "Section 7.2.1"
    title = Column(String(255), nullable=True)
    content_text = Column(Text, nullable=False)
    summary = Column(Text, nullable=True)
    
    scope_keywords = Column(JSON, default=list) # ["puerta", "ancho mínimo", "evacuación"]
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relaciones
    document = relationship("NormativeDocument", back_populates="clauses")
    criteria = relationship("NormativeCriterion", back_populates="clause", cascade="all, delete-orphan")
    embeddings = relationship("NormativeEmbedding", back_populates="clause", cascade="all, delete-orphan")


class NormativeCriterion(Base):
    """Criterio determinístico extraído de la norma parametrizado para validación automática."""
    __tablename__ = "normative_criteria"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    clause_id = Column(String(36), ForeignKey("normative_clauses.id", ondelete="CASCADE"), nullable=False)
    
    criterion_code = Column(String(100), unique=True, index=True, nullable=False) # e.g. "CRIT-OGUC-417-DOOR-MIN-WIDTH"
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    
    target_entity = Column(String(50), nullable=False) # door, corridor, stair, electrical_panel
    property_name = Column(String(50), nullable=False) # width_clear, height, separation_distance
    operator = Column(String(20), nullable=False) # gte, lte, eq, in, range
    threshold_value = Column(JSON, nullable=False) # {"min": 0.90, "unit": "m"}
    severity = Column(String(20), default="high") # critical, high, medium, low, warning
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relaciones
    clause = relationship("NormativeClause", back_populates="criteria")


class NormativeEmbedding(Base):
    """Vector denso semántico para búsqueda y vinculación contextual de notas en planos."""
    __tablename__ = "normative_embeddings"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    clause_id = Column(String(36), ForeignKey("normative_clauses.id", ondelete="CASCADE"), nullable=False)
    
    embedding_model = Column(String(100), default="sentence-transformers/all-MiniLM-L6-v2")
    vector_data = Column(JSON, nullable=False) # Representación serializada del vector
    dimension = Column(Integer, default=384)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relaciones
    clause = relationship("NormativeClause", back_populates="embeddings")
