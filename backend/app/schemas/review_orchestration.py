from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class ReviewDisciplineResponse(BaseModel):
    id: str
    code: str
    name: str
    description: Optional[str] = None
    order_index: int = 0
    is_active: bool = True

    class Config:
        from_attributes = True


class ReviewTopicResponse(BaseModel):
    id: str
    discipline_id: Optional[str] = None
    code: str
    name: str
    description: Optional[str] = None
    is_transversal: bool = False
    enabled_mvp: bool = False
    order_index: int = 0
    is_active: bool = True

    class Config:
        from_attributes = True


class ReviewPlanRequest(BaseModel):
    project_id: str = Field(..., description="ID del proyecto activo")
    discipline_code: str = Field(..., description="Código de la especialidad (e.g. PIPING, GENERAL)")
    topic_code: str = Field(..., description="Código del punto de revisión (e.g. PID_SYMBOLS)")
    document_ids: Optional[List[str]] = Field(None, description="IDs de documentos del proyecto a evaluar")
    mode: str = Field("production", description="production o sandbox")


class ReviewPlanResponse(BaseModel):
    project_id: str
    project_code: Optional[str] = None
    project_name: Optional[str] = None
    discipline_code: str
    discipline_name: str
    topic_code: str
    topic_name: str
    execution_mode: str
    can_execute: bool
    empty_reason: Optional[str] = None
    applicable_rules: List[Dict[str, Any]] = []
    unapproved_rules: List[Dict[str, Any]] = []
    included_documents: List[Dict[str, Any]] = []
    excluded_documents: List[Dict[str, Any]] = []
    missing_required_document_types: List[Dict[str, Any]] = []
    phases_blueprint: List[Dict[str, Any]] = []
    warnings: List[str] = []
    limitations: List[str] = []


class ReviewRunCreateRequest(BaseModel):
    project_id: str = Field(..., description="ID del proyecto activo")
    discipline_code: str = Field(..., description="Código de especialidad")
    topic_code: str = Field(..., description="Código de punto de revisión")
    document_ids: List[str] = Field(..., description="Lista de IDs de documentos del proyecto")
    mode: str = Field("production", description="production o sandbox")
    run_name: Optional[str] = Field(None, description="Nombre personalizado para la auditoría")


class ReviewRunExecuteResponse(BaseModel):
    review_run_id: str
    project_id: str
    run_name: str
    discipline_code: str
    topic_code: str
    execution_mode: str
    status: str
    execution_time_sec: float
    rules_applied_count: int
    findings_count: int
    summary_stats: Dict[str, Any] = {}
    report_id: Optional[str] = None
    report_sha256: Optional[str] = None


class SymbolOccurrenceSummary(BaseModel):
    occurrence_id: str
    inventory_group_id: Optional[str] = None
    project_id: Optional[str] = None
    document_id: str
    document_name: str
    sheet_id: Optional[str] = None
    sheet_name: Optional[str] = None
    page_number: int = 1
    bbox_normalized: List[float]
    inner_drawing_bbox: Optional[List[float]] = None
    symbol_crop_bbox: Optional[List[float]] = None
    symbol_crop_path: Optional[str] = None
    symbol_crop_hash: Optional[str] = None
    occurrence_context_crop_bbox: Optional[List[float]] = None
    occurrence_context_crop_path: Optional[str] = None
    occurrence_context_crop_hash: Optional[str] = None
    context_margin_mm: float = 15.0
    geometric_confidence: float = 1.0
    geometry_score: Optional[float] = None
    topology_score: Optional[float] = None
    visual_score: Optional[float] = None
    context_score: Optional[float] = None
    match_score: Optional[float] = None
    classification: str = "symbol"
    matching_status: str = "unmatched"
    orientation: Optional[int] = None
    crop_quality_status: str = "valid"
    text_mask_overlap_ratio: float = 0.0
    detected_tag_or_code: Optional[str] = None
    table_id: Optional[str] = None
    cell_id: Optional[str] = None
    cell_bbox: Optional[List[float]] = None
    navigation_context: Dict[str, Any] = {}


class SymbolInventoryGroupResponse(BaseModel):
    id: str
    review_run_id: str
    grouping_key: str
    grouping_method: str = "template_match"
    grouping_confidence: float = 1.0
    grouping_version: str = "v1.0"
    display_code: str
    unknown_group_id: Optional[str] = None
    representative_occurrence_id: Optional[str] = None
    representative_selection_reason: Optional[str] = None
    representative_crop_path: Optional[str] = None
    matched_template_id: Optional[str] = None
    matched_template_version_id: Optional[str] = None
    canonical_name: Optional[str] = None
    description: Optional[str] = None
    technical_function: Optional[str] = None
    standard_reference: Optional[str] = None
    catalog_status: str
    confidence_summary: Dict[str, Any] = {}
    total_occurrences: int = 0
    occurrences_by_document: Dict[str, int] = {}
    occurrences_by_sheet: Dict[str, int] = {}
    requires_human_review: bool = False
    explanation: Optional[str] = None
    created_at: Optional[str] = None


class SymbolInventoryMetricsResponse(BaseModel):
    documents_reviewed: int = 0
    sheets_reviewed: int = 0
    geometric_candidates: int = 0
    valid_symbol_occurrences: int = 0
    inventory_groups: int = 0
    recognized_production: int = 0
    recognized_sandbox: int = 0
    recognized_reference_only: int = 0
    unknown: int = 0
    ambiguous: int = 0
    requires_review: int = 0
    figures_excluded: int = 0
    not_symbols: int = 0
    inventory_coverage: float = 0.0
    production_coverage: float = 0.0
    sandbox_coverage: float = 0.0
    unknown_rate: float = 0.0
    review_required_rate: float = 0.0
    exclusion_rate: float = 0.0
    by_document: Dict[str, Any] = {}


class SymbolExecutiveSummaryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_index: int = Field(..., description="Índice numérico correlativo (ITEM)")
    symbol_code: str = Field(..., description="Código corto del símbolo (ej. V-001 o PIP-VALVE-GATE)")
    description: str = Field(..., description="Descripción o función técnica en lenguaje simple")
    found: bool = Field(..., description="Indica si fue encontrado en el proyecto evaluado (Sí/No)")
    quantity: int = Field(0, description="Cantidad total de apariciones encontradas")
    sheet_labels: List[str] = Field(default_factory=list, description="Lista de láminas donde aparece el símbolo")
    sheets_display: str = Field("-", description="Texto formateado de páginas/láminas separadas por coma")


class SymbolInventoryResponse(BaseModel):
    status: str = Field("available", description="Estado del inventario: available | pending | unavailable | failed")
    metrics: SymbolInventoryMetricsResponse = Field(default_factory=SymbolInventoryMetricsResponse)
    groups: List[SymbolInventoryGroupResponse] = Field(default_factory=list)
    excluded_groups: List[SymbolInventoryGroupResponse] = Field(default_factory=list)
    executive_summary: List[SymbolExecutiveSummaryItem] = Field(default_factory=list, description="Resumen gráfico de simbología por punto de revisión")
    reason_code: Optional[str] = None
    reason_message: Optional[str] = None
    can_generate: bool = False
    inventory_version: Optional[str] = None
    inventory_generated_at: Optional[str] = None
    inventory_source_snapshot_hash: Optional[str] = None


class ReviewRunDetailsResponse(BaseModel):
    id: str
    project_id: str
    run_name: str
    discipline_code: str
    discipline_name: str
    topic_code: str
    topic_name: str
    execution_mode: str
    status: str
    requested_by: str
    requested_at: Optional[str] = None
    completed_at: Optional[str] = None
    execution_time_sec: float
    rule_count: int
    document_count: int
    findings_count: int
    summary_stats: Dict[str, Any] = {}
    documents: List[Dict[str, Any]] = []
    steps: List[Dict[str, Any]] = []
    executions: List[Dict[str, Any]] = []
    findings: List[Dict[str, Any]] = []
    reports: List[Dict[str, Any]] = []
    baseline_catalog_version: Optional[str] = None
    symbol_inventory: SymbolInventoryResponse = Field(default_factory=SymbolInventoryResponse)


ReviewRunDetailResponse = ReviewRunDetailsResponse


class ReviewExportCreateRequest(BaseModel):
    format: str = Field("json", description="Formato de exportación: json, xlsx, pdf")


class ReviewReportResponse(BaseModel):
    id: str
    project_id: str
    review_run_id: str
    report_name: str
    format: str
    artifact_path: str
    sha256: str
    status: str
    baseline_catalog_version: Optional[str] = None
    stats_summary: Dict[str, Any] = {}
    created_at: datetime

    class Config:
        from_attributes = True
