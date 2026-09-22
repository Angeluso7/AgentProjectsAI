from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class DetectedSymbolRead(BaseModel):
    id: str
    document_id: str
    sheet_id: str
    region_id: Optional[str] = None
    symbol_type: str
    discipline: str
    bbox: List[float]
    bbox_normalized: List[float]
    polygon_points: Optional[List[List[float]]] = None
    confidence: float
    detection_status: str
    source_engine: str
    source_version: str
    source_asset_template_id: Optional[str] = None
    matched_library_entry_id: Optional[str] = None
    attributes: Dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class SymbolDetectProcessRequest(BaseModel):
    force_reprocess: bool = Field(default=False, description="Fuerza re-detección descartando detecciones previas")
    engine: Optional[str] = Field(default="yolo_sahi_hybrid", description="Motor: yolo_sahi_hybrid, template_matching, geometric_heuristic")
    confidence_threshold: Optional[float] = Field(default=0.50, description="Umbral mínimo de aceptación")
    discipline: Optional[str] = Field(default=None, description="Filtra por disciplina")

class SymbolSummaryItem(BaseModel):
    symbol_type: str
    discipline: str
    count: int
    average_confidence: float

class SheetSymbolsSummaryResponse(BaseModel):
    sheet_id: str
    total_symbols: int
    by_category: List[SymbolSummaryItem]

class PromoteSymbolToTemplateRequest(BaseModel):
    structured_symbol_id: str
    library_name: Optional[str] = "ISA-5.1 Piping Library"
    discipline: Optional[str] = "piping"
    reviewer: Optional[str] = "auditor"
    user_notes: Optional[str] = None

class PromoteSymbolToTemplateResponse(BaseModel):
    template_id: str
    library_id: str
    symbol_class: str
    display_name: str
    reused_for_matching_count: int
    message: str
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    source_structured_symbol_id: Optional[str] = None
    visual_variant_group_id: Optional[str] = None

class LegendExtractionRequest(BaseModel):
    extraction_id: Optional[str] = None
    page_number: int = 1
    discipline: str = "piping"
    preferred_mode: str = "auto" # auto, vector_only, raster_only
    file_path: Optional[str] = None


# ============================================================================
# FASE 2: CURACIÓN HITL, DEDUPLICACIÓN MULTI-FACTOR Y CATÁLOGO CANÓNICO
# ============================================================================

class StructuredSymbolUpdate(BaseModel):
    symbol_name: Optional[str] = None
    canonical_symbol_family: Optional[str] = None
    category: Optional[str] = None
    standard_reference: Optional[str] = None
    human_validation_notes: Optional[str] = None
    visual_variant_group_id: Optional[str] = None
    review_status: Optional[str] = None # "accepted", "rejected", "pending", "flagged_false_positive"

class BatchCurateSymbolsRequest(BaseModel):
    symbol_ids: List[str]
    action: str = Field(..., description="accept, reject, flag_false_positive, update_family")
    canonical_symbol_family: Optional[str] = None
    standard_reference: Optional[str] = None
    notes: Optional[str] = None
    reviewer: Optional[str] = "auditor"

class BatchCurateSymbolsResponse(BaseModel):
    updated_count: int
    accepted_count: int
    rejected_count: int
    flagged_count: int
    message: str

class DeduplicateSymbolsRequest(BaseModel):
    extraction_id: Optional[str] = None
    discipline: str = "piping"
    canonical_symbol_family: Optional[str] = None
    visual_threshold: float = Field(0.85, description="Umbral de similitud dHash (0.0 - 1.0)")
    semantic_threshold: float = Field(0.75, description="Umbral de similitud de nombre y ontología (0.0 - 1.0)")

class VariantClusterItem(BaseModel):
    symbol_id: str
    symbol_name: str
    canonical_symbol_family: str
    crop_image_path: Optional[str] = None
    confidence_score: float
    source_render_mode: str
    visual_similarity: float
    semantic_similarity: float
    combined_score: float
    is_canonical_representative: bool

class DeduplicationCluster(BaseModel):
    group_id: str
    canonical_symbol_family: str
    canonical_name: str
    representative_id: str
    members_count: int
    members: List[VariantClusterItem]

class DeduplicateSymbolsResponse(BaseModel):
    total_evaluated: int
    clusters_count: int
    duplicates_detected: int
    clusters: List[DeduplicationCluster]

class MergeVariantRequest(BaseModel):
    symbol_id: str
    target_group_id: str

class SplitVariantRequest(BaseModel):
    symbol_id: str

class BatchPromoteToTemplateRequest(BaseModel):
    structured_symbol_ids: List[str]
    library_name: Optional[str] = "ISA-5.1 Piping Library"
    discipline: Optional[str] = "piping"
    reviewer: Optional[str] = "auditor"
    user_notes: Optional[str] = None

class BatchPromoteToTemplateResponse(BaseModel):
    promoted_count: int
    library_id: str
    library_name: str
    promoted_templates: List[Dict[str, Any]]
    message: str

class CanonicalTemplateItem(BaseModel):
    id: str
    library_id: str
    symbol_class: str
    display_name: str
    aliases: List[str] = []
    image_template_path: Optional[str] = None
    vector_svg_path: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    source_structured_symbol_id: Optional[str] = None
    visual_variant_group_id: Optional[str] = None
    feature_descriptors: Dict[str, Any] = {}
    created_at: datetime

class CanonicalCatalogResponse(BaseModel):
    library_id: str
    library_name: str
    discipline: str
    standard_name: Optional[str] = None
    total_templates: int
    family_counts: Dict[str, int]
    templates: List[CanonicalTemplateItem]

class SymbolOccurrenceItem(BaseModel):
    occurrence_id: Optional[str] = None
    page_number: int
    sheet_id: Optional[str] = None
    bbox_normalized: List[float] = Field(default_factory=list)
    cell_bbox: Optional[List[float]] = None
    inner_drawing_bbox: Optional[List[float]] = None
    source_document_id: Optional[str] = None
    crop_image_path: Optional[str] = None
    document_title: Optional[str] = None
    row_index: Optional[int] = None
    col_index: Optional[int] = None
    source_reference: Optional[str] = None

class CandidateCurationDetail(BaseModel):
    id: str
    extracted_item_id: str
    symbol_name: str
    standard_family: str
    discipline: str
    category: Optional[str] = None
    crop_image_path: Optional[str] = None
    confidence_score: float
    source_render_mode: str
    layout_context: str
    context_association_mode: str
    standard_reference: Optional[str] = None
    canonical_symbol_family: str
    visual_variant_group_id: Optional[str] = None
    estimated_physical_size_mm: Optional[Dict[str, Any]] = None
    reused_for_matching_count: int
    false_positive_count: int
    human_validation_notes: Optional[str] = None
    created_at: datetime
    # 9 evidencias obligatorias para decisión:
    document_title: Optional[str] = None
    document_id: Optional[str] = None
    extraction_id: Optional[str] = None
    page_number: int = 1
    ocr_associated_text: Optional[str] = None
    review_status: str = "pending"
    possible_matching_template: Optional[Dict[str, Any]] = None
    # Linaje estructural tabla-fila-columna
    source_table_id: Optional[str] = None
    row_index: Optional[int] = None
    col_index: Optional[int] = None
    cell_bbox: Optional[List[float]] = None
    row_bbox: Optional[List[float]] = None
    # Lista consolidada de ocurrencias multipágina para navegación y ampliación
    occurrences: List[SymbolOccurrenceItem] = Field(default_factory=list)
# ============================================================================
# FASE 1: MOTOR DE RECONOCIMIENTO GEOMÉTRICO Y MATCHING DETERMINISTA
# ============================================================================

class MatchedTemplateItem(BaseModel):
    template_id: str
    symbol_class: str
    display_name: str
    score: float
    ncc_score: float
    hu_score: float
    best_rotation_deg: int
    decision_policy: str # "auto_match", "hitl_suggestion", "unknown"
    match_evidence: Dict[str, Any] = {}

class MatchCandidateRequest(BaseModel):
    candidate_id: str = Field(..., description="ID de la entidad candidata (StructuredSymbol o ExtractedItem)")
    discipline: Optional[str] = Field(None, description="Disciplina para acotar el catálogo")
    allowed_rotations: Optional[List[int]] = Field(default=[0, 90, 180, 270], description="Ángulos permitidos para rotación ortogonal")
    top_k: int = Field(default=5, description="Número máximo de coincidencias a retornar")
    organization_id: Optional[str] = Field(None, description="ID de organización para scoping multitenant")

class MatchCandidateResponse(BaseModel):
    candidate_id: str
    total_templates_evaluated: int
    best_match: Optional[MatchedTemplateItem] = None
    matches: List[MatchedTemplateItem] = []
