from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

# ==========================================
# 1. ProcessingJob & JobEvent Schemas
# ==========================================

class JobEventRead(BaseModel):
    id: str
    job_id: str
    event_type: str
    status_before: Optional[str] = None
    status_after: Optional[str] = None
    stage: Optional[str] = None
    message: Optional[str] = None
    details: Dict[str, Any] = {}
    actor_type: str
    actor_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class ProcessingJobCreate(BaseModel):
    job_type: str = Field(..., description="Tipo de proceso: document_ingest, sheet_ocr, document_ocr, sheet_layout, document_layout, title_block_match, source_ingest")
    target_type: str = Field(..., description="document, sheet, source_asset, project")
    target_id: str = Field(..., description="ID de la entidad objetivo")
    project_id: Optional[str] = None
    parent_job_id: Optional[str] = None
    pipeline_name: str = "standard_pipeline"
    pipeline_version: str = "v1.0"
    requested_by: str = "system"
    priority: int = 5
    input_payload: Dict[str, Any] = {}
    max_retries: int = 3

class ProcessingJobRead(BaseModel):
    id: str
    job_type: str
    target_type: str
    target_id: str
    project_id: Optional[str] = None
    parent_job_id: Optional[str] = None
    pipeline_name: str
    pipeline_version: str
    requested_by: str
    status: str
    priority: int
    progress_percent: int
    current_stage: str
    input_payload: Dict[str, Any] = {}
    result_summary: Dict[str, Any] = {}
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int
    max_retries: int
    queued_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    events: Optional[List[JobEventRead]] = None

    class Config:
        from_attributes = True

class AsyncJobAcceptedResponse(BaseModel):
    job_id: str
    status: str
    poll_url: str
    message: str
    target_type: str
    target_id: str

# ==========================================
# 2. ConfidencePolicy Schemas
# ==========================================

class ConfidencePolicyCreate(BaseModel):
    name: str = Field(..., description="Identificador único de la política")
    applies_to: str = Field(..., description="ocr_text, title_block_field, title_block_match, normative_source, rule_finding")
    document_type: Optional[str] = None
    discipline: Optional[str] = None
    field_name: Optional[str] = None
    risk_level: str = "medium"
    auto_accept_threshold: float = Field(..., ge=0.0, le=1.0)
    review_threshold: float = Field(..., ge=0.0, le=1.0)
    action_below_review_threshold: str = "exception_required"
    is_active: bool = True
    version: str = "1.0"
    description: Optional[str] = None

class ConfidencePolicyRead(BaseModel):
    id: str
    name: str
    applies_to: str
    document_type: Optional[str] = None
    discipline: Optional[str] = None
    field_name: Optional[str] = None
    risk_level: str
    auto_accept_threshold: float
    review_threshold: float
    action_below_review_threshold: str
    is_active: bool
    version: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# ==========================================
# 3. ReviewTask & ReviewDecision Schemas
# ==========================================

class ReviewDecisionRequest(BaseModel):
    decision: str = Field(..., description="approved, corrected, rejected, dismissed")
    corrected_value: Optional[Dict[str, Any]] = Field(default=None, description="Valor corregido si decision == 'corrected'")
    reviewer: str = Field(default="auditor_qa", description="Identificador del revisor técnico")
    reason_code: Optional[str] = None
    notes: Optional[str] = None

class ReviewDecisionRead(BaseModel):
    id: str
    review_task_id: str
    decision: str
    original_value: Dict[str, Any] = {}
    corrected_value: Optional[Dict[str, Any]] = None
    reviewer: str
    reason_code: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class ReviewTaskRead(BaseModel):
    id: str
    project_id: Optional[str] = None
    source_asset_id: Optional[str] = None
    document_id: Optional[str] = None
    sheet_id: Optional[str] = None
    job_id: Optional[str] = None
    task_type: str
    priority: str
    status: str
    reason_code: str
    reason_message: str
    confidence: Optional[float] = None
    evidence_refs: Dict[str, Any] = {}
    payload: Dict[str, Any] = {}
    assigned_to: Optional[str] = None
    created_at: datetime
    due_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    decisions: Optional[List[ReviewDecisionRead]] = None

    class Config:
        from_attributes = True

# ==========================================
# 4. DecisionTrace Schemas
# ==========================================

class DecisionTraceRead(BaseModel):
    id: str
    trace_type: str
    entity_type: str
    entity_id: str
    source_asset_id: Optional[str] = None
    document_id: Optional[str] = None
    sheet_id: Optional[str] = None
    job_id: Optional[str] = None
    evidence_refs: Dict[str, Any] = {}
    engine_name: str
    engine_version: str
    template_id: Optional[str] = None
    template_version: Optional[str] = None
    policy_id: Optional[str] = None
    policy_version: Optional[str] = None
    confidence: Optional[float] = None
    decision_status: str
    explanation: str
    created_at: datetime

    class Config:
        from_attributes = True
