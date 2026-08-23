import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship
from app.db.session import Base

class Document(Base):
    """Documento técnico raíz (PDF cargado en el sistema)."""
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    project_version_id = Column(String(36), ForeignKey("project_versions.id", ondelete="SET NULL"), nullable=True)
    
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_hash_sha256 = Column(String(64), unique=True, index=True, nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    mime_type = Column(String(100), default="application/pdf", nullable=False)
    page_count = Column(Integer, default=1, nullable=False)
    status = Column(String(30), default="uploaded") # uploaded, processing, ready, error
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relaciones
    project = relationship("Project", back_populates="documents")
    project_version = relationship("ProjectVersion", back_populates="documents")
    sheets = relationship("DocumentSheet", back_populates="document", cascade="all, delete-orphan", order_by="DocumentSheet.sheet_number.asc()")
    extracted_tables = relationship("ExtractedTable", back_populates="document", cascade="all, delete-orphan")
    symbols = relationship("DetectedSymbol", back_populates="document", cascade="all, delete-orphan")


class DocumentSheet(Base):
    """Lámina individual o página rasterizada perteneciente a un documento."""
    __tablename__ = "document_sheets"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    
    sheet_number = Column(Integer, nullable=False) # 1-indexed
    sheet_code = Column(String(100), nullable=True) # e.g. "ARQ-01", "EST-102"
    title = Column(String(255), nullable=True) # e.g. "Planta Primer Piso"
    scale = Column(String(50), nullable=True) # e.g. "1:50", "Indicadas"
    revision = Column(String(50), nullable=True) # e.g. "A", "0"
    date_str = Column(String(50), nullable=True)
    
    # Geometría y dimensiones
    width_px = Column(Integer, nullable=False)
    height_px = Column(Integer, nullable=False)
    width_mm = Column(Float, nullable=True)
    height_mm = Column(Float, nullable=True)
    dpi = Column(Integer, default=150, nullable=False)
    
    # Rutas de artefactos visuales
    raster_image_path = Column(String(500), nullable=True)
    thumbnail_path = Column(String(500), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relaciones
    document = relationship("Document", back_populates="sheets")
    regions = relationship("SheetRegion", back_populates="sheet", cascade="all, delete-orphan")
    texts = relationship("ExtractedText", back_populates="sheet", cascade="all, delete-orphan")
    tables = relationship("ExtractedTable", back_populates="sheet", cascade="all, delete-orphan")
    symbols = relationship("DetectedSymbol", back_populates="sheet", cascade="all, delete-orphan")
    evidences = relationship("VisualEvidence", back_populates="sheet", cascade="all, delete-orphan")
    title_block_extraction = relationship("TitleBlockExtraction", back_populates="sheet", uselist=False, cascade="all, delete-orphan")


class SheetRegion(Base):
    """Macro-región segmentada del plano (Viñeta, Dibujo, Notas, Leyendas, Cuadros)."""
    __tablename__ = "sheet_regions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    sheet_id = Column(String(36), ForeignKey("document_sheets.id", ondelete="CASCADE"), nullable=False)
    
    region_type = Column(String(50), nullable=False) # title_block, drawing_area, notes_area, legend_area, table_candidate
    polygon_points = Column(JSON, nullable=False) # [[x0,y0], [x1,y1], [x2,y2], ...] coordenadas normalizadas 0.0-1.0
    bbox = Column(JSON, nullable=False) # [x0, y0, x1, y1] en píxeles
    bbox_normalized = Column(JSON, nullable=False) # [x0, y0, x1, y1] normalizado 0.0 - 1.0
    confidence = Column(Float, default=1.0)
    detection_method = Column(String(50), default="hybrid_heuristic") # hybrid_heuristic, template_match, ml_layout
    source_version = Column(String(30), default="v1.0")
    attributes = Column(JSON, default=dict)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relaciones
    sheet = relationship("DocumentSheet", back_populates="regions")
    tables = relationship("ExtractedTable", back_populates="region")
    symbols = relationship("DetectedSymbol", back_populates="region")


class TitleBlockExtraction(Base):
    """Resultado estructurado del matching y extracción de viñeta técnica por lámina."""
    __tablename__ = "title_block_extractions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    sheet_id = Column(String(36), ForeignKey("document_sheets.id", ondelete="CASCADE"), nullable=False, unique=True)
    template_id = Column(String(36), ForeignKey("title_block_templates.id", ondelete="SET NULL"), nullable=True)
    
    match_score = Column(Float, default=0.0)
    extraction_status = Column(String(30), default="extracted") # extracted, partial, not_found, failed
    
    # Metadatos estructurados extraídos
    sheet_code = Column(String(100), nullable=True)
    sheet_title = Column(String(255), nullable=True)
    revision = Column(String(50), nullable=True)
    scale_text = Column(String(50), nullable=True)
    date_text = Column(String(50), nullable=True)
    project_name = Column(String(255), nullable=True)
    discipline = Column(String(50), nullable=True)
    drawn_by = Column(String(100), nullable=True)
    checked_by = Column(String(100), nullable=True)
    approved_by = Column(String(100), nullable=True)
    
    matched_anchors = Column(JSON, default=list)
    unmatched_required_fields = Column(JSON, default=list)
    raw_fields = Column(JSON, default=dict)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relaciones
    sheet = relationship("DocumentSheet", back_populates="title_block_extraction")
    template = relationship("TitleBlockTemplate")


class ExtractedText(Base):
    """Bloque o línea de texto posicional extraído con OCR o capas vectoriales."""
    __tablename__ = "extracted_texts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    sheet_id = Column(String(36), ForeignKey("document_sheets.id", ondelete="CASCADE"), nullable=False)
    region_id = Column(String(36), ForeignKey("sheet_regions.id", ondelete="SET NULL"), nullable=True)
    
    text = Column(Text, nullable=False)
    clean_text = Column(Text, nullable=True) # Texto normalizado sin acentos/espacios raros
    bbox = Column(JSON, nullable=False) # [x0, y0, x1, y1] en píxeles de referencia
    bbox_normalized = Column(JSON, nullable=False) # [x0, y0, x1, y1] normalizado 0.0 - 1.0
    confidence = Column(Float, default=1.0)
    font_name = Column(String(100), nullable=True)
    font_size = Column(Float, nullable=True)
    angle = Column(Float, default=0.0) # 0, 90, 180, 270 grados
    source = Column(String(30), default="vector") # vector, paddleocr, tesseract, vector_pdf
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relaciones
    sheet = relationship("DocumentSheet", back_populates="texts")


class ExtractedTable(Base):
    """Tabla de especificaciones o cuadro técnico estructurado extraído del plano/documento."""
    __tablename__ = "extracted_tables"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    sheet_id = Column(String(36), ForeignKey("document_sheets.id", ondelete="CASCADE"), nullable=True, index=True)
    region_id = Column(String(36), ForeignKey("sheet_regions.id", ondelete="SET NULL"), nullable=True, index=True)
    
    table_type = Column(String(50), default="unknown_table", nullable=False, index=True) 
    # window_schedule, door_schedule, area_schedule, load_schedule, material_list, unknown_table
    
    title = Column(String(255), nullable=True)
    bbox = Column(JSON, nullable=False) # [x0, y0, x1, y1] en píxeles
    bbox_normalized = Column(JSON, nullable=False) # [x0, y0, x1, y1] normalizado 0.0 - 1.0
    
    row_count = Column(Integer, default=0, nullable=False)
    column_count = Column(Integer, default=0, nullable=False)
    confidence = Column(Float, default=1.0, nullable=False)
    extraction_status = Column(String(30), default="extracted", nullable=False) # extracted, partial, failed, low_confidence
    
    source_engine = Column(String(50), default="spatial_grid_reconstruction", nullable=False)
    source_version = Column(String(30), default="v1.0", nullable=False)
    raw_structure = Column(JSON, default=dict)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relaciones
    document = relationship("Document", back_populates="extracted_tables")
    sheet = relationship("DocumentSheet", back_populates="tables")
    region = relationship("SheetRegion", back_populates="tables")
    cells = relationship("ExtractedTableCell", back_populates="table", cascade="all, delete-orphan", order_by="[ExtractedTableCell.row_index.asc(), ExtractedTableCell.column_index.asc()]")


class ExtractedTableCell(Base):
    """Celda individual con coordenadas espaciales, texto, posición en grilla y trazabilidad."""
    __tablename__ = "extracted_table_cells"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    table_id = Column(String(36), ForeignKey("extracted_tables.id", ondelete="CASCADE"), nullable=False, index=True)
    
    row_index = Column(Integer, nullable=False) # 0-indexed
    column_index = Column(Integer, nullable=False) # 0-indexed
    row_span = Column(Integer, default=1, nullable=False)
    col_span = Column(Integer, default=1, nullable=False)
    
    text = Column(Text, default="", nullable=False)
    normalized_text = Column(Text, nullable=True)
    confidence = Column(Float, default=1.0, nullable=False)
    
    bbox = Column(JSON, nullable=False) # [x0, y0, x1, y1] píxeles
    bbox_normalized = Column(JSON, nullable=False) # [x0, y0, x1, y1] normalizado 0.0 - 1.0
    
    is_header = Column(Boolean, default=False, nullable=False)
    source_text_refs = Column(JSON, default=list) # IDs de ExtractedText que alimentan la celda
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relaciones
    table = relationship("ExtractedTable", back_populates="cells")


class DetectedSymbol(Base):
    """Símbolo o elemento visual detectado por el modelo de visión, SAHI o template matching."""
    __tablename__ = "detected_symbols"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    sheet_id = Column(String(36), ForeignKey("document_sheets.id", ondelete="CASCADE"), nullable=False, index=True)
    region_id = Column(String(36), ForeignKey("sheet_regions.id", ondelete="SET NULL"), nullable=True, index=True)
    
    symbol_type = Column(String(100), index=True, nullable=False) 
    # door_symbol, window_symbol, luminaire_symbol, switch_symbol, outlet_symbol, sanitary_fixture, panel_symbol, unknown_symbol_candidate
    
    discipline = Column(String(50), default="architecture", nullable=False) # architecture, electrical, plumbing, structural
    bbox = Column(JSON, nullable=False) # [x0, y0, x1, y1] en píxeles
    bbox_normalized = Column(JSON, nullable=False) # [x0, y0, x1, y1] normalizado 0.0 - 1.0
    polygon_points = Column(JSON, nullable=True) # opcional para geometrías complejas
    
    confidence = Column(Float, default=1.0, nullable=False)
    detection_status = Column(String(30), default="detected", nullable=False) # detected, verified, low_confidence, disputed
    
    source_engine = Column(String(50), default="yolo_sahi_hybrid", nullable=False) # yolo_sahi_hybrid, template_matching, geometric_heuristic
    source_version = Column(String(30), default="v1.0", nullable=False)
    source_asset_template_id = Column(String(36), nullable=True)
    matched_library_entry_id = Column(String(36), ForeignKey("symbol_templates.id", ondelete="SET NULL"), nullable=True)
    
    attributes = Column(JSON, default=dict) # {"orientation_deg": 90, "sahi_slice_id": "slice_01"}
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relaciones
    document = relationship("Document", back_populates="symbols")
    sheet = relationship("DocumentSheet", back_populates="symbols")
    region = relationship("SheetRegion", back_populates="symbols")
    library_entry = relationship("SymbolTemplate")


class VisualEvidence(Base):
    """Recorte de imagen o evidencia visual vinculada a un hallazgo de auditoría."""
    __tablename__ = "visual_evidences"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    sheet_id = Column(String(36), ForeignKey("document_sheets.id", ondelete="CASCADE"), nullable=False)
    
    crop_image_path = Column(String(500), nullable=False)
    bbox = Column(JSON, nullable=False) # [x0, y0, x1, y1] del recorte
    caption = Column(String(255), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relaciones
    sheet = relationship("DocumentSheet", back_populates="evidences")
