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

class DocumentUploadResponse(BaseModel):
    document_id: str
    id: str
    filename: str
    content_type: str
    mime_type: str
    size_bytes: int
    file_size_bytes: int
    sha256: str
    file_hash_sha256: str
    storage_status: str = "stored"
    processing_status: str = "uploaded"
    status: str = "uploaded"
    upload_timestamp: datetime
    created_at: datetime
    project_id: str
    discipline: Optional[str] = None
    document_type: Optional[str] = None
    evidence_classification: Optional[str] = None
    execution_mode: Optional[str] = None
    warnings: List[str] = []
    page_count: int = 1
    sheets: List[DocumentSheetRead] = []
    error_message: Optional[str] = None

    class Config:
        from_attributes = True

class UploadValidationErrorResponse(BaseModel):
    code: str = "UPLOAD_VALIDATION_ERROR"
    message: str
    details: Dict[str, Any]

class DocumentProcessRequest(BaseModel):
    dpi: Optional[int] = Field(default=None, description="DPI para rasterizado (opcional, usa DEFAULT_RENDER_DPI por defecto)")

class BatchFileResultItem(BaseModel):
    filename: str
    status: str # "uploaded", "ready", "already_exists", "failed"
    document_id: Optional[str] = None
    file_size_bytes: int = 0
    mime_type: Optional[str] = None
    page_count: int = 0
    sheets_count: int = 0
    error_message: Optional[str] = None

class BatchUploadResponse(BaseModel):
    project_id: str
    total_files: int
    successful_count: int
    duplicated_count: int
    failed_count: int
    documents: List[DocumentRead] = []
    results: List[BatchFileResultItem] = []

class DocumentStructuralNodeRead(BaseModel):
    id: str
    document_id: str
    sheet_id: Optional[str] = None
    node_type: str
    hierarchy_path: Optional[str] = None
    level: int = 0
    title: Optional[str] = None
    content_text: str
    structured_payload: Dict[str, Any] = {}
    page_number: Optional[int] = 1
    bbox_normalized: Optional[List[float]] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class CadEntitiesSummaryRead(BaseModel):
    filename: str
    dxf_version: Optional[str] = None
    layers: List[Dict[str, Any]] = []
    blocks_inserted: List[Dict[str, Any]] = []
    texts: List[Dict[str, Any]] = []
    summary: Dict[str, Any] = {}
    error: Optional[str] = None


class ProjectDocumentView(BaseModel):
    """Contrato de lectura unificado para documentos de proyecto en la UI."""
    id: str
    project_id: str
    organization_id: str
    filename: str
    original_filename: str
    content_type: str
    size_bytes: int
    sha256: str
    document_type: str = "unknown"  # "pid" | "legend" | "specification" | "unknown"
    discipline: str = "general"
    storage_status: str = "stored"  # "stored" | "failed" | "pending_cleanup"
    processing_status: str = "uploaded"  # "uploaded" | "queued" | "processing" | "processed" | "failed" | "cancelled"
    processing_error_summary: Optional[str] = None
    uploaded_at: datetime
    uploaded_by: Optional[str] = None
    page_count: Optional[int] = 1
    can_process: bool = True
    can_retry: bool = False
    can_open: bool = True
    sheets_count: int = 0
    sheets: Optional[List[DocumentSheetRead]] = []
    context_metadata: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


# Alias unificado
UnifiedDocumentRead = ProjectDocumentView


def to_project_document_view(doc: Any, project: Optional[Any] = None) -> ProjectDocumentView:
    """Convierte un modelo Document de SQLAlchemy a ProjectDocumentView normalizado."""
    import os

    meta = doc.metadata_info or {}
    
    # 1. Determinar storage_status
    storage_status = "stored"
    if not doc.file_path or not os.path.exists(doc.file_path):
        storage_status = "failed"

    # 2. Normalizar processing_status
    raw_status = (doc.status or "uploaded").lower()
    if raw_status in ("ready", "processed"):
        proc_status = "processed"
    elif raw_status == "processing":
        proc_status = "processing"
    elif raw_status == "failed":
        proc_status = "failed"
    elif raw_status == "queued":
        proc_status = "queued"
    elif raw_status == "cancelled":
        proc_status = "cancelled"
    else:
        proc_status = "uploaded"

    # 3. Document Type
    doc_type = meta.get("document_type")
    if not doc_type:
        fname_lower = (doc.filename or "").lower()
        if "pid" in fname_lower or "p&id" in fname_lower:
            doc_type = "pid"
        elif "leyenda" in fname_lower or "legend" in fname_lower:
            doc_type = "legend"
        elif "spec" in fname_lower or "especificaci" in fname_lower or "memoria" in fname_lower:
            doc_type = "specification"
        else:
            doc_type = "unknown"

    # 4. Disciplina
    disc = meta.get("discipline")
    if not disc and project and hasattr(project, "discipline"):
        disc = project.discipline
    if not disc:
        disc = "general"

    # 5. Capacidades operativas
    can_process = proc_status in ("uploaded", "failed")
    can_retry = proc_status == "failed"
    can_open = storage_status == "stored"

    # 6. Sábanas / láminas
    sheet_list = []
    if hasattr(doc, "sheets") and doc.sheets:
        sheet_list = [DocumentSheetRead.model_validate(s) for s in doc.sheets]
    sheets_count = len(sheet_list) if sheet_list else (doc.page_count or 1)

    return ProjectDocumentView(
        id=doc.id,
        project_id=doc.project_id,
        organization_id=doc.organization_id,
        filename=doc.filename,
        original_filename=meta.get("original_filename") or doc.filename,
        content_type=doc.mime_type or "application/pdf",
        size_bytes=doc.file_size_bytes or 0,
        sha256=doc.file_hash_sha256,
        document_type=doc_type,
        discipline=disc,
        storage_status=storage_status,
        processing_status=proc_status,
        processing_error_summary=doc.error_message if proc_status == "failed" else None,
        uploaded_at=doc.created_at or datetime.utcnow(),
        uploaded_by=meta.get("uploaded_by"),
        page_count=doc.page_count,
        can_process=can_process,
        can_retry=can_retry,
        can_open=can_open,
        sheets_count=sheets_count,
        sheets=sheet_list,
        context_metadata=meta
    )



