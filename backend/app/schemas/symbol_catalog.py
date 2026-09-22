from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class SymbolGeometricFeatureDTO(BaseModel):
    id: Optional[str] = None
    feature_type: str # line_segment, triangle, polygon, connection_port, symmetry_axis, etc.
    feature_count: int = 1
    feature_parameters: Dict[str, Any] = Field(default_factory=dict)
    normalized_bbox: List[float] = Field(default_factory=list) # [x0, y0, x1, y1]
    relative_position: Optional[str] = None
    orientation_degrees: Optional[float] = None
    confidence: float = 1.0
    relationship_group: Optional[str] = None


class SymbolFeatureRelationDTO(BaseModel):
    id: Optional[str] = None
    source_feature_id: str
    target_feature_id: str
    relation_type: str # touches, connected_to, intersects, symmetric_to, etc.
    confidence: float = 1.0
    relation_parameters: Dict[str, Any] = Field(default_factory=dict)


class SymbolSourceEvidenceDTO(BaseModel):
    id: Optional[str] = None
    source_document_id: Optional[str] = None
    source_document_hash: Optional[str] = None
    evidence_kind: str = "synthetic" # synthetic, redacted_real, real_authorized
    page_number: int = 1
    sheet_id: Optional[str] = None
    table_id: Optional[str] = None
    cell_id: Optional[str] = None
    bbox_normalized: List[float] = Field(default_factory=list)
    cell_bbox: Optional[List[float]] = None
    inner_drawing_bbox: Optional[List[float]] = None
    symbol_crop_bbox: Optional[List[float]] = None
    crop_image_path: Optional[str] = None
    crop_image_hash: Optional[str] = None
    source_excerpt: Optional[str] = None
    grid_source: Optional[str] = None
    geometric_confidence: float = 1.0
    source_standard_or_project: Optional[str] = None
    source_authority: Optional[str] = None
    source_revision: Optional[str] = None
    source_date: Optional[str] = None
    discipline: Optional[str] = None
    sheet_name: Optional[str] = None
    sheet_code: Optional[str] = None
    extractor_version: Optional[str] = None
    evidence_metadata: Dict[str, Any] = Field(default_factory=dict)


class SymbolTemplateVersionDetail(BaseModel):
    id: str
    symbol_template_id: str
    version_number: int
    approval_status: str
    source_kind: str
    canonical_crop_path: Optional[str] = None
    canonical_crop_hash: Optional[str] = None
    orientation_policy: str = "rotation_equivalent_180"
    scale_policy: str = "isotropic_bounded"
    geometric_signature: Dict[str, Any] = Field(default_factory=dict)
    perceptual_signature: Dict[str, Any] = Field(default_factory=dict)
    matcher_thresholds: Dict[str, Any] = Field(default_factory=dict)
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime
    geometric_features: List[SymbolGeometricFeatureDTO] = Field(default_factory=list)
    source_evidence: Optional[SymbolSourceEvidenceDTO] = None

    class Config:
        from_attributes = True


class CanonicalSymbolTemplateDetail(BaseModel):
    id: str
    canonical_code: str
    canonical_name: str
    category: str
    subcategory: str
    discipline: str = "piping"
    technical_function: Optional[str] = None
    standard_reference: Optional[str] = None
    status: str = "active"
    current_version_id: Optional[str] = None
    aliases: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    versions: List[SymbolTemplateVersionDetail] = Field(default_factory=list)

    class Config:
        from_attributes = True


class PromoteCandidateToCanonicalRequest(BaseModel):
    candidate_id: str # StructuredSymbol.id or DetectedSymbol.id
    canonical_code: str # e.g. "PIP-VALVE-GATE"
    canonical_name: str # e.g. "Gate Valve"
    category: str = "valve"
    subcategory: str = "gate_valve"
    discipline: str = "piping"
    technical_function: Optional[str] = "Isolation or shutoff valve"
    standard_reference: Optional[str] = "PIP PNC00001 / ISA-5.1"
    evidence_kind: str = "synthetic" # synthetic, redacted_real, real_authorized
    source_document_id: Optional[str] = None
    source_document_hash: Optional[str] = None
    source_authority: Optional[str] = None
    sheet_name: Optional[str] = None
    sheet_code: Optional[str] = None
    page_number: Optional[int] = None
    source_revision: Optional[str] = None
    source_date: Optional[str] = None
    extractor_version: Optional[str] = "1.0.0"
    orientation_policy: str = "rotation_equivalent_180"
    reviewer_id: str = "auditor"
    rationale: Optional[str] = None
    notes: Optional[str] = None
    evidence_metadata: Dict[str, Any] = Field(default_factory=dict)


class PromoteCandidateToCanonicalResponse(BaseModel):
    template_id: str
    canonical_code: str
    version_id: str
    version_number: int
    features_extracted: int
    status: str
    message: str


class ProgressiveMatchResult(BaseModel):
    template_id: str
    version_id: str
    canonical_code: str
    canonical_name: str
    total_score: float
    geometric_score: float
    topology_score: float
    visual_score: float
    context_score: float
    rotation_deg: int = 0
    is_mirrored: bool = False
    matching_verdict: str # matched, ambiguous, rejected


class MatchOccurrenceRequest(BaseModel):
    occurrence_id: Optional[str] = None # DetectedSymbol / SymbolOccurrence id
    crop_image_path: Optional[str] = None
    inner_drawing_bbox: Optional[List[float]] = None
    symbol_crop_bbox: Optional[List[float]] = None
    geometric_evidence: bool = True
    geometric_confidence: float = 1.0
    classification: str = "symbol"
    context_text: Optional[str] = None
    detected_tag: Optional[str] = None
    discipline: str = "piping"
    project_id: Optional[str] = None
    project_document_id: Optional[str] = None
    sheet_id: Optional[str] = None
    page_number: int = 1
    execution_mode: str = "production" # production, sandbox


class MatchOccurrenceResponse(BaseModel):
    occurrence_id: Optional[str] = None
    record_kind: str = "occurrence"
    environment: str = "production"
    matching_status: str # matched, ambiguous, unknown_symbol, not_applicable
    best_match: Optional[ProgressiveMatchResult] = None
    candidate_matches: List[ProgressiveMatchResult] = Field(default_factory=list)
    rejection_reason: Optional[str] = None
    research_case_id: Optional[str] = None
    is_sandbox_or_test_only: bool = False
    warning: Optional[str] = None


class OccurrenceItemDetail(BaseModel):
    id: str
    record_kind: str = "occurrence" # candidate, occurrence
    environment: str = "production" # production, sandbox
    classification: str = "symbol"
    matching_status: str = "unmatched"
    matched_template_id: Optional[str] = None
    matched_template_version_id: Optional[str] = None
    canonical_code: Optional[str] = None
    canonical_name: Optional[str] = None
    template_status: Optional[str] = None
    is_sandbox_or_test_only: bool = False
    evidence_kind: Optional[str] = None
    document_id: Optional[str] = None
    sheet_id: Optional[str] = None
    page_number: int = 1
    sheet_name: Optional[str] = None
    sheet_code: Optional[str] = None
    table_id: Optional[str] = None
    cell_id: Optional[str] = None
    bbox: List[float] = Field(default_factory=list)
    bbox_normalized: List[float] = Field(default_factory=list)
    cell_bbox: Optional[List[float]] = None
    inner_drawing_bbox: Optional[List[float]] = None
    symbol_crop_bbox: Optional[List[float]] = None
    crop_image_path: Optional[str] = None
    crop_image_hash: Optional[str] = None
    geometric_evidence: bool = True
    geometric_confidence: float = 1.0
    match_score: Optional[float] = None
    geometry_score: Optional[float] = None
    topology_score: Optional[float] = None
    visual_score: Optional[float] = None
    context_score: Optional[float] = None
    context_text: Optional[str] = None
    detected_tag_or_code: Optional[str] = None
    review_status: str = "unreviewed"
    created_at: Optional[datetime] = None
    context_navigation: Dict[str, Any] = Field(default_factory=dict)


class OccurrenceListResponse(BaseModel):
    total: int
    items: List[OccurrenceItemDetail] = Field(default_factory=list)


class SymbolReviewDecisionRequest(BaseModel):
    subject_type: str # candidate, template_version, occurrence
    subject_id: str
    decision: str # approve, reject, mark_unknown, link_template, create_template, retire_template, override_match
    reviewer_id: str
    rationale: Optional[str] = None
    evidence_snapshot: Dict[str, Any] = Field(default_factory=dict)
    override_template_id: Optional[str] = None
    override_version_id: Optional[str] = None


class SymbolReviewDecisionResponse(BaseModel):
    decision_id: str
    subject_type: str
    subject_id: str
    decision: str
    reviewer_id: str
    recorded_at: datetime
    message: str


class CandidateCurationViewResponse(BaseModel):
    candidate_id: str
    record_kind: str = "candidate"
    classification: str = "symbol"
    page_number: int = 1
    document_id: Optional[str] = None
    sheet_name: Optional[str] = None
    sheet_code: Optional[str] = None
    visual_context_bbox: List[float] = Field(default_factory=list)
    cell_bbox: Optional[List[float]] = None
    inner_drawing_bbox: Optional[List[float]] = None
    symbol_crop_bbox: Optional[List[float]] = None
    crop_image_path: Optional[str] = None
    crop_image_hash: Optional[str] = None
    grid_source: Optional[str] = None
    geometric_evidence: bool = True
    geometric_confidence: float = 1.0
    geometric_features: List[Dict[str, Any]] = Field(default_factory=list)
    orientation_degrees: Optional[float] = None
    ocr_secondary_context: Dict[str, Any] = Field(default_factory=dict)
    source_evidence: Optional[SymbolSourceEvidenceDTO] = None
    suggested_canonical_code: str = "PIP-VALVE-GATE"
    suggested_canonical_name: str = "Gate Valve"


class CurateAndApproveCandidateRequest(BaseModel):
    candidate_id: str
    confirmed_canonical_code: str = "PIP-VALVE-GATE"
    confirmed_canonical_name: str = "Gate Valve"
    reviewed_crop: bool = True
    reviewed_source: bool = True
    explicit_approval: bool = True
    reviewer_id: str
    rationale: str
    evidence_kind: str = "redacted_real" # real_authorized, redacted_real
    source_document_id: Optional[str] = None
    source_document_hash: Optional[str] = None
    source_authority: Optional[str] = None
    discipline: str = "piping"
    sheet_name: Optional[str] = None
    sheet_code: Optional[str] = None
    source_revision: Optional[str] = None
    source_date: Optional[str] = None
    extractor_version: Optional[str] = "1.0.0"
    evidence_metadata: Dict[str, Any] = Field(default_factory=dict)


class CurateAndApproveCandidateResponse(BaseModel):
    template_id: str
    version_id: str
    decision_id: str
    canonical_code: str
    canonical_name: str
    template_status: str = "active"
    approval_status: str = "approved"
    features_count: int
    reviewer_id: str
    approved_at: datetime
    evidence_snapshot: Dict[str, Any] = Field(default_factory=dict)
    message: str

