from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field

class DetectInformationGapRequest(BaseModel):
    project_id: Optional[str] = None
    stage: Optional[str] = None
    discipline: str = "general"
    topic_query: str
    detection_source: str = "assistant_evaluator"
    auto_request_permission: bool = True

class DetectInformationGapResponse(BaseModel):
    is_gap_detected: bool
    missing_topic: str
    internal_rag_status: str # resolved, insufficient, not_found
    internal_rag_score: float
    internal_rag_matches_count: int
    acquisition_request_id: Optional[str] = None
    recommended_action: str # "use_internal_rag", "request_web_search_permission", "request_document_directly"
    message: str

class WebSearchPermissionActionRequest(BaseModel):
    action: str = Field(..., description="'approve' para autorizar búsqueda web o 'reject' para rechazar")
    query_override: Optional[str] = None
    rejection_reason: Optional[str] = None
    force_document_request: bool = False # Si el usuario prefiere pedir documento directo sin web
    max_iterations_override: Optional[int] = None
    sources_limit_override: Optional[int] = None

class SufficiencyEvaluationDTO(BaseModel):
    relevance_score: float
    confidence_score: float
    coverage_score: float
    overall_adequacy_score: float
    classification: str # sufficient, partially_sufficient, insufficient, not_found, not_applicable
    rationale: str

class EscalationDiagnosticDTO(BaseModel):
    missing_information_details: str
    why_web_internal_failed: str
    requested_document_type: str
    suggested_responsible: str
    audit_impact_justification: str
    unlocked_deliverables_and_rules: List[str] = []
    escalated_at: Optional[str] = None

class ViewerKnowledgeCaptureRequest(BaseModel):
    project_id: Optional[str] = None
    document_id: Optional[str] = None
    sheet_id: Optional[str] = None
    sheet_code: Optional[str] = None
    page_number: Optional[int] = 1
    bbox_normalized: Optional[List[float]] = None
    element_type: str = "symbol" # symbol, table, detail, photo, schema, vignette, legend, other
    name: str
    normalized_category: Optional[str] = None # e.g. "extinguisher_pqs_6kg", "electrical_board_teg"
    aliases: List[str] = Field(default_factory=list) # e.g. ["Extintor PQS", "EXT 6KG", "Extintor de Polvo"]
    description: Optional[str] = None
    discipline: str = "general"
    domain: str = "symbol_knowledge" # symbol_knowledge, template_knowledge, guide_knowledge, lesson_knowledge
    legend_text: Optional[str] = None
    related_table_code: Optional[str] = None # e.g. "TAB-SIMB-ELEC-01"
    related_rule_code: Optional[str] = None # e.g. "R-ARQ-DOOR-MIN-WIDTH"
    crop_image_base64: Optional[str] = None
    auto_approve: bool = False # Si es True, pasa directo a approved_for_reuse = True
    deduplication_mode: str = "auto" # auto, link_occurrence, new_version, create_new
    target_existing_item_id: Optional[str] = None

class VisualDeduplicationMatchDTO(BaseModel):
    item_id: str
    title: str
    normalized_category: str
    discipline: str
    similarity_score: float
    visual_crop_url: Optional[str] = None
    total_occurrences: int = 1
    status: str
    is_active_for_reuse: bool

class VisualDeduplicationCheckRequest(BaseModel):
    name: str
    normalized_category: Optional[str] = None
    discipline: str = "general"
    element_type: str = "symbol"

class VisualDeduplicationCheckResponse(BaseModel):
    has_potential_duplicates: bool
    suggested_mode: str # create_new, link_occurrence, new_version
    matches: List[VisualDeduplicationMatchDTO] = []
    message: str

class InformationAcquisitionRequestRead(BaseModel):
    id: str
    organization_id: str
    project_id: Optional[str] = None
    stage: Optional[str] = None
    discipline: str
    
    missing_topic: str
    gap_description: str
    detection_source: str
    
    internal_rag_status: str
    internal_rag_score: float
    internal_rag_matches_count: int
    
    permission_status: str
    permission_requested_at: datetime
    permission_granted_by: Optional[str] = None
    permission_granted_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    
    action_type: str
    web_search_query: Optional[str] = None
    web_search_executed: bool
    web_search_executed_at: Optional[datetime] = None
    web_search_result_summary: Optional[str] = None
    web_search_sources: List[Dict[str, Any]] = []
    
    iteration_count: int = 0
    max_iterations: int = 3
    search_sources_limit: int = 5
    
    relevance_score: float = 0.0
    confidence_score: float = 0.0
    coverage_score: float = 0.0
    overall_adequacy_score: float = 0.0
    adequacy_classification: str = "pending"
    termination_reason: Optional[str] = None
    
    adequacy_status: str
    requested_document_type: Optional[str] = None
    requested_document_justification: Optional[str] = None
    suggested_responsible: Optional[str] = None
    escalation_details: Dict[str, Any] = {}
    
    created_knowledge_item_id: Optional[str] = None
    status: str
    metadata_payload: Dict[str, Any] = {}
    
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class IngestionChannelSummaryItem(BaseModel):
    channel_code: str
    channel_name: str
    description: str
    total_items: int
    approved_reusable_items: int
    pending_validation_items: int
    modalities_count: Dict[str, int]
    requires_human_approval: bool
    is_active: bool

class IngestionChannelSummaryResponse(BaseModel):
    total_knowledge_items: int
    total_active_for_reuse: int
    channels: List[IngestionChannelSummaryItem]
