import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, Text, JSON, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.db.session import Base

class ManualAnnotation(Base):
    """Anotación y recorte manual capturado por el usuario desde el visor de planos."""
    __tablename__ = "manual_annotations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    sheet_id = Column(String(36), ForeignKey("document_sheets.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    # Coordenadas normalizadas [x0, y0, x1, y1] en rango [0..1]
    bbox_normalized = Column(JSON, nullable=False)
    # Coordenadas en píxeles [px0, py0, px1, py1]
    bbox_pixels = Column(JSON, default=list)

    # Ruta relativa al recorte PNG guardado en disco (ej. storage/crops/doc_id/sheet_id/id.png)
    crop_image_path = Column(String(500), nullable=True)

    # Taxonomía requerida
    # symbol, table, layout_region, text_note, title_block, legend, view_elevation_plan, stamp_signature, diagram_sketch, other
    element_type = Column(String(50), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    
    # Texto OCR extraído y/o corregido por el usuario
    ocr_text = Column(Text, nullable=True)
    
    # Clasificaciones técnicas complementarias
    discipline = Column(String(50), default="general", nullable=False)
    category = Column(String(100), nullable=True)
    confidence = Column(Float, default=1.0)
    tags = Column(JSON, default=list)

    # Estado del ciclo de vida:
    # draft (borrador), confirmed (confirmado), promoted_to_knowledge (en biblioteca guía), promoted_to_active_learning, archived
    status = Column(String(40), default="confirmed", nullable=False, index=True)
    extra_metadata = Column(JSON, default=dict)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class KnowledgeLibraryEntry(Base):
    """Nivel 1: Catálogo y Base de Conocimiento Guía & Plantillas Curadas."""
    __tablename__ = "knowledge_library_entries"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    source_annotation_id = Column(String(36), ForeignKey("manual_annotations.id", ondelete="SET NULL"), nullable=True, index=True)

    # Tipo de plantilla/conocimiento:
    # symbol_template, table_template, title_block_spec, note_clause, standard_region, legend_entry, sketch_sample, other
    entry_type = Column(String(50), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    discipline = Column(String(50), default="general", nullable=False)

    crop_image_path = Column(String(500), nullable=True)
    canonical_text = Column(Text, nullable=True)
    tags = Column(JSON, default=list)
    
    is_verified = Column(Boolean, default=True, nullable=False)
    created_by_user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # active, deprecated, archived
    status = Column(String(30), default="active", nullable=False, index=True)
    extra_metadata = Column(JSON, default=dict)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class ActiveLearningPromotion(Base):
    """Nivel 2: MLOps & Active Learning Pool para reentrenamiento y calibración de motores IA."""
    __tablename__ = "active_learning_promotions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    knowledge_entry_id = Column(String(36), ForeignKey("knowledge_library_entries.id", ondelete="SET NULL"), nullable=True, index=True)
    manual_annotation_id = Column(String(36), ForeignKey("manual_annotations.id", ondelete="SET NULL"), nullable=True, index=True)

    # Motor IA objetivo: ocr, symbol_detector, layout_parser, table_extractor, qa_rules
    target_engine = Column(String(50), nullable=False, index=True)
    # Split de dataset: train, validation, test, few_shot_pool
    dataset_split = Column(String(30), default="few_shot_pool", nullable=False)

    crop_image_path = Column(String(500), nullable=True)
    label = Column(String(100), nullable=False)
    ground_truth_text = Column(Text, nullable=True)
    ground_truth_bbox = Column(JSON, default=list)

    promoted_by_user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    # staged, training_used, validated, archived
    status = Column(String(30), default="staged", nullable=False, index=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
