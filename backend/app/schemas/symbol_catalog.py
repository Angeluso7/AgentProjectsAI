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
    source_revision: Optional[str] = None
    source_date: Optional[str] = None


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
    candidate_id: str # StructuredSymbol.id
    canonical_code: str # e.g. "PIP-VALVE-GATE"
    canonical_name: str # e.g. "Gate Valve"
    category: str = "valve"
    subcategory: str = "gate_valve"
    discipline: str = "piping"
    technical_function: Optional[str] = "Isolation or shutoff valve"
    standard_reference: Optional[str] = "PIP PNC00001 / ISA-5.1"
    evidence_kind: str = "synthetic" # synthetic, redacted_real, real_authorized
    orientation_policy: str = "rotation_equivalent_180"
    reviewer_id: str = "auditor"
    notes: Optional[str] = None


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


class MatchOccurrenceResponse(BaseModel):
    occurrence_id: Optional[str] = None
    matching_status: str # matched, ambiguous, unknown_symbol, not_applicable
    best_match: Optional[ProgressiveMatchResult] = None
    candidate_matches: List[ProgressiveMatchResult] = Field(default_factory=list)
    rejection_reason: Optional[str] = None
    research_case_id: Optional[str] = None


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
