from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict

class SourceAssetCreate(BaseModel):
    organization_id: Optional[str] = None
    project_id: Optional[str] = None
    source_type: str = Field(..., description="analysis_document, template_document, symbol_reference, normative_document, web_normative_source")
    source_origin: str = Field(default="local_upload", description="local_upload, web_scrape, api_sync, manual_entry")
    document_type: Optional[str] = Field(default="blueprint_pdf", description="blueprint_pdf, standard_doc, symbol_catalog, webpage_article")
    discipline: str = Field(default="general", description="architecture, electrical, structural, general")
    title: str = Field(..., description="Título representativo de la fuente")
    description: Optional[str] = None
    source_url: Optional[str] = None
    original_filename: Optional[str] = None
    file_size_bytes: Optional[int] = None
    version: str = "1.0"
    owner: str = "system"
    metadata_payload: Dict[str, Any] = {}

class SourceAssetApprovalRequest(BaseModel):
    approved: bool = Field(..., description="True para aprobar, False para rechazar")
    notes: Optional[str] = Field(default=None, description="Observaciones técnicas de la aprobación o motivo de rechazo")
    reviewer: str = Field(default="lead_reviewer", description="Identificador del revisor técnico")

class SourceAssetRead(BaseModel):
    id: str
    organization_id: str
    project_id: Optional[str] = None
    source_type: str
    source_origin: str
    document_type: Optional[str] = None
    discipline: str
    title: str
    description: Optional[str] = None
    file_path: Optional[str] = None
    original_filename: Optional[str] = None
    file_size_bytes: Optional[int] = None
    source_url: Optional[str] = None
    sha256: Optional[str] = None
    mime_type: str
    version: str
    status: str
    approval_status: str
    linked_memory_target: str
    owner: str
    approval_notes: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    metadata_payload: Dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class SourceDependenciesResponse(BaseModel):
    source_id: str
    title: str
    has_file: bool
    file_path: Optional[str] = None
    original_filename: Optional[str] = None
    file_size_bytes: Optional[int] = None
    extractions_count: int = 0
    rule_documents_count: int = 0
    can_hard_delete: bool = True
    warnings: List[str] = []

class SourceDeleteResponse(BaseModel):
    source_id: str
    deleted: bool
    mode: str # hard_delete, soft_delete_archived
    file_removed: bool
    message: str

class SourceAssetIngestResponse(BaseModel):
    source_id: str
    status: str
    target_memory: str
    message: str
    details: Dict[str, Any] = {}

# =========================================================
# SCHEMAS PARA INVESTIGACIONES WEB PERSISTENTES
# =========================================================

class ResearchSourceRead(BaseModel):
    id: str
    title: str
    url: str
    domain: str
    snippet: Optional[str] = None
    retrieved_at: datetime
    reliability_score: float = 0.9

    model_config = ConfigDict(from_attributes=True)

class ResearchItemRead(BaseModel):
    id: str
    item_type: str
    item_nature: str
    title: str
    code_or_number: Optional[str] = None
    description: Optional[str] = None
    content_text: Optional[str] = None
    source_reference: Optional[str] = None
    governance_note: Optional[str] = None
    validation_status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ResearchResultRead(BaseModel):
    id: str
    query_id: str
    source_extraction_id: Optional[str] = None
    title: str
    executive_summary: Optional[str] = None
    total_items_found: int
    metadata_info: Dict[str, Any] = {}
    sources: List[ResearchSourceRead] = []
    items: List[ResearchItemRead] = []
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ResearchQueryRead(BaseModel):
    id: str
    organization_id: str
    project_id: Optional[str] = None
    search_prompt: str
    discipline: str
    document_type: str
    authority: Optional[str] = None
    focus_areas: List[str] = []
    status: str
    created_at: datetime
    updated_at: datetime
    results_count: int = 0
    total_sources_count: int = 0
    total_items_count: int = 0

    model_config = ConfigDict(from_attributes=True)

class ResearchQueryDetailRead(BaseModel):
    id: str
    organization_id: str
    project_id: Optional[str] = None
    search_prompt: str
    discipline: str
    document_type: str
    authority: Optional[str] = None
    focus_areas: List[str] = []
    status: str
    metadata_payload: Dict[str, Any] = {}
    results: List[ResearchResultRead] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# =========================================================
# SCHEMAS PARA VISOR DOCUMENTAL REAL, RECORTES Y RESUMEN
# =========================================================

class SourceDocumentPageRead(BaseModel):
    page_number: int
    image_url: str
    width_px: int
    height_px: int
    width_pt: float
    height_pt: float
    text_preview: Optional[str] = None

class SourceDocumentPagesResponse(BaseModel):
    source_id: str
    title: str
    document_type: str
    discipline: str
    total_pages: int
    file_exists: bool
    mime_type: str
    pages: List[SourceDocumentPageRead] = []

class PageCropRequest(BaseModel):
    page_number: int = Field(default=1, ge=1)
    bbox: List[float] = Field(..., description="[x0, y0, x1, y1] coordenadas normalizadas entre 0 y 1")
    title: Optional[str] = None
    item_type: Optional[str] = "imagen"

class PageCropResponse(BaseModel):
    source_id: str
    page_number: int
    bbox: List[float]
    crop_image_url: str
    crop_image_base64: Optional[str] = None
    ocr_text: Optional[str] = None
    width_px: int
    height_px: int

class RuleSummarizeRequest(BaseModel):
    text_content: str = Field(..., min_length=3, description="Texto extraído del documento normativo")
    discipline: Optional[str] = "general"
    title: Optional[str] = None
    item_type: Optional[str] = "rule"

class RuleSummarizeResponse(BaseModel):
    rule_code: str
    rule_statement: str
    summary: str
    discipline: str
    item_nature: str
    extracted_parameters: Dict[str, Any] = {}

class BatchSourceFileResultItem(BaseModel):
    filename: str
    status: str # "success", "already_exists", "failed"
    source_id: Optional[str] = None
    title: Optional[str] = None
    file_size_bytes: int = 0
    mime_type: Optional[str] = None
    error_message: Optional[str] = None

class BatchSourceUploadResponse(BaseModel):
    total_files: int
    successful_count: int
    duplicated_count: int
    failed_count: int
    sources: List[SourceAssetRead] = []
    results: List[BatchSourceFileResultItem] = []

