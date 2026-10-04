from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from pydantic import BaseModel, Field

# ============================================================================
# SCHEMAS DE ANOTACIONES GROUND TRUTH (VALIDACIÓN ESTRUCTURADA)
# ============================================================================

class OcrAnnotationItem(BaseModel):
    text: str
    bbox: List[float] = Field(description="[x0, y0, x1, y1] normalizado 0.0 - 1.0")
    page_number: int = 1
    rotation: int = 0
    language: Optional[str] = "es"
    criticality: Literal["critical", "normal"] = "normal"

class OcrAnnotationPayload(BaseModel):
    items: List[OcrAnnotationItem]

class LayoutAnnotationItem(BaseModel):
    region_type: Literal["drawing_area", "title_block", "table_candidate", "notes_area", "legend_area", "margins"]
    bbox: List[float] = Field(description="[x0, y0, x1, y1] normalizado 0.0 - 1.0")
    human_confidence: float = 1.0

class LayoutAnnotationPayload(BaseModel):
    items: List[LayoutAnnotationItem]

class TitleBlockAnnotationItem(BaseModel):
    field_name: str # e.g. "sheet_code", "sheet_title", "project_name", "scale", "revision"
    expected_value: str
    normalized_value: Optional[str] = None
    bbox: Optional[List[float]] = None
    required: bool = True

class TitleBlockAnnotationPayload(BaseModel):
    items: List[TitleBlockAnnotationItem]

class TableCellAnnotation(BaseModel):
    row_index: int
    col_index: int
    cell_text: str
    normalized_unit: Optional[str] = None

class TableAnnotationItem(BaseModel):
    table_type: str = "general_schedule"
    bbox: List[float] = Field(description="[x0, y0, x1, y1] normalizado")
    total_rows: int
    total_cols: int
    headers: List[str] = []
    cells: List[TableCellAnnotation] = []

class TableAnnotationPayload(BaseModel):
    items: List[TableAnnotationItem]

class SymbolAnnotationItem(BaseModel):
    class_name: str # e.g. "door_single", "window_standard", "column_rect", etc.
    bbox: Optional[List[float]] = None # [x0, y0, x1, y1] si está anotado
    count: int = 1
    human_confidence: float = 1.0
    ignored: bool = False

class SymbolAnnotationPayload(BaseModel):
    items: List[SymbolAnnotationItem]

class RuleFindingAnnotationItem(BaseModel):
    rule_code: str # e.g. "RULE-DOOR-COUNT-001"
    expected_outcome: Literal["pass", "fail", "insufficient_evidence"]
    expected_severity: Literal["critical", "high", "medium", "low", "info"] = "medium"
    expected_delta: Optional[Dict[str, Any]] = None
    evidence_refs: Dict[str, Any] = {}
    notes: Optional[str] = None

class RuleFindingAnnotationPayload(BaseModel):
    items: List[RuleFindingAnnotationItem]


# ============================================================================
# DTOS DE GOBIERNO Y CONSULTA
# ============================================================================

class EvaluationDatasetCreate(BaseModel):
    name: str
    description: Optional[str] = None
    dataset_type: Literal["golden", "regression", "benchmark", "pilot"] = "golden"
    discipline: Literal["architecture", "structure", "electrical", "plumbing", "hvac", "mixed"] = "architecture"
    version: str = "1.0"
    source_policy: Literal["consented", "anonymized", "synthetic", "internal"] = "consented"

class EvaluationDatasetRead(BaseModel):
    id: str
    organization_id: Optional[str] = None
    name: str
    description: Optional[str] = None
    dataset_type: str
    discipline: str
    version: str
    status: str
    source_policy: str
    snapshot_manifest_hash: Optional[str] = None
    frozen_at: Optional[datetime] = None
    created_by: str
    created_at: datetime
    updated_at: datetime
    samples_count: Optional[int] = 0

    class Config:
        from_attributes = True

class EvaluationSampleCreate(BaseModel):
    sample_key: str
    discipline: str = "architecture"
    drawing_type: str = "floor_plan"
    source_checksum: str
    source_asset_id: Optional[str] = None
    document_id: Optional[str] = None
    sheet_id: Optional[str] = None
    split: Literal["test", "holdout", "validation"] = "test"
    metadata_json: Dict[str, Any] = {}

class EvaluationSampleRead(BaseModel):
    id: str
    dataset_id: str
    source_asset_id: Optional[str] = None
    document_id: Optional[str] = None
    sheet_id: Optional[str] = None
    sample_key: str
    discipline: str
    drawing_type: str
    source_checksum: str
    split: str
    annotation_status: str
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    metadata_json: Dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class AnnotationSetCreate(BaseModel):
    annotation_type: Literal["ocr", "layout", "title_block", "table", "symbol", "rule_finding"]
    schema_version: str = "v1.0"
    source: Literal["human", "imported", "synthetic", "system_bootstrap"] = "human"
    payload: Dict[str, Any]

class AnnotationStatusUpdate(BaseModel):
    status: Literal["submitted", "reviewed", "approved", "rejected"]
    notes: Optional[str] = None

class AnnotationSetRead(BaseModel):
    id: str
    sample_id: str
    annotation_type: str
    schema_version: str
    status: str
    annotator_id: Optional[str] = None
    reviewer_id: Optional[str] = None
    source: str
    payload: Dict[str, Any]
    superseded_by_id: Optional[str] = None
    created_at: datetime
    reviewed_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class EvaluationRunCreate(BaseModel):
    split_evaluated: Literal["test", "holdout", "all"] = "test"
    pipeline_version: str = "v1.0"
    rule_pack_version: str = "v1.0-oguc"
    config: Dict[str, Any] = {}

class EvaluationMetricRead(BaseModel):
    id: str
    evaluation_run_id: str
    category: str
    component: str
    metric_name: str
    metric_value: float
    metric_unit: str
    scope: Dict[str, Any] = {}
    confidence_interval: Optional[Dict[str, Any]] = None
    sample_count: int
    created_at: datetime

    class Config:
        from_attributes = True

class EvaluationRunRead(BaseModel):
    id: str
    dataset_id: str
    dataset_version: str
    pipeline_version: str
    git_commit_hash: Optional[str] = None
    model_versions: Dict[str, Any] = {}
    rule_pack_version: str
    ocr_raster_config: Dict[str, Any] = {}
    inference_thresholds: Dict[str, Any] = {}
    prompts_and_rules_config: Dict[str, Any] = {}
    split_evaluated: str
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    config: Dict[str, Any] = {}
    summary: Dict[str, Any] = {}
    artifact_paths: Dict[str, Any] = {}
    created_by: str
    created_at: datetime
    metrics: List[EvaluationMetricRead] = []

    class Config:
        from_attributes = True

