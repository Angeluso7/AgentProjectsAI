from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from app.schemas.common import RegionTypeEnum

class ExtractedTextRead(BaseModel):
    id: str
    sheet_id: str
    region_id: Optional[str] = None
    text: str
    clean_text: Optional[str] = None
    bbox: List[float] # [x0, y0, x1, y1] en píxeles
    bbox_normalized: List[float] # [x0, y0, x1, y1] en rango normalizado 0.0 - 1.0
    confidence: float
    font_name: Optional[str] = None
    font_size: Optional[float] = None
    angle: float = 0.0
    source: str = "vector"
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class OcrProcessRequest(BaseModel):
    force_reprocess: bool = Field(default=False, description="Fuerza el reprocesamiento eliminando textos previos")
    engine: Optional[str] = Field(default=None, description="Motor específico a utilizar ('paddleocr', 'tesseract', 'vector_pdf')")

class OcrResultSummary(BaseModel):
    sheet_id: str
    sheet_number: int
    texts_count: int
    avg_confidence: float
    engine_used: str
    execution_time_sec: float

class SheetRegionRead(BaseModel):
    id: str
    sheet_id: str
    region_type: str
    polygon_points: List[List[float]]
    bbox: List[float] # en píxeles
    bbox_normalized: List[float] # normalizado 0.0 - 1.0
    confidence: float
    detection_method: str = "hybrid_heuristic"
    source_version: str = "v1.0"
    attributes: Dict[str, Any] = {}
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class TitleBlockExtractionRead(BaseModel):
    id: str
    sheet_id: str
    template_id: Optional[str] = None
    match_score: float
    extraction_status: str
    sheet_code: Optional[str] = None
    sheet_title: Optional[str] = None
    revision: Optional[str] = None
    scale_text: Optional[str] = None
    date_text: Optional[str] = None
    project_name: Optional[str] = None
    discipline: Optional[str] = None
    drawn_by: Optional[str] = None
    checked_by: Optional[str] = None
    approved_by: Optional[str] = None
    matched_anchors: List[str] = []
    unmatched_required_fields: List[str] = []
    raw_fields: Dict[str, Any] = {}
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class LayoutProcessRequest(BaseModel):
    force_reprocess: bool = Field(default=False, description="Fuerza la regeneración de regiones eliminando anteriores")

class TitleBlockMatchRequest(BaseModel):
    force_reprocess: bool = Field(default=False, description="Fuerza re-matching y re-extracción")
    template_id: Optional[str] = Field(default=None, description="ID opcional de plantilla específica a evaluar")

class DetectedSymbolRead(BaseModel):
    id: str
    symbol_class: str
    category: str
    bbox: List[float]
    confidence: float
    detector_name: str
    attributes: Dict[str, Any] = {}

    class Config:
        from_attributes = True

class DocumentSheetRead(BaseModel):
    id: str
    sheet_number: int
    sheet_code: Optional[str] = None
    title: Optional[str] = None
    scale: Optional[str] = None
    revision: Optional[str] = None
    date_str: Optional[str] = None
    width_px: int
    height_px: int
    width_mm: Optional[float] = None
    height_mm: Optional[float] = None
    dpi: int
    rotation_deg: Optional[int] = 0
    raster_image_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    created_at: Optional[datetime] = None
    regions: List[SheetRegionRead] = []
    title_block_extraction: Optional[TitleBlockExtractionRead] = None
    texts_count: Optional[int] = 0
    symbols_count: Optional[int] = 0

    class Config:
        from_attributes = True

class DocumentBase(BaseModel):
    filename: str
    file_size_bytes: int
    mime_type: str = "application/pdf"
    is_vector_pdf: Optional[bool] = True
    page_count: int = 1

class DocumentCreate(BaseModel):
    project_id: str
    project_version_id: Optional[str] = None

class DocumentRead(DocumentBase):
    id: str
    project_id: str
    project_version_id: Optional[str] = None
    file_hash_sha256: str
    status: str
    error_message: Optional[str] = None
    metadata_info: Optional[Dict[str, Any]] = {}
    created_at: datetime
    processed_at: Optional[datetime] = None
    sheets: List[DocumentSheetRead] = []

    class Config:
        from_attributes = True

class DocumentProcessRequest(BaseModel):
    dpi: Optional[int] = Field(default=None, description="DPI para rasterizado (opcional, usa DEFAULT_RENDER_DPI por defecto)")
