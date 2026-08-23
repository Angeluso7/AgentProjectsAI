from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from app.schemas.common import (
    ObservationTypeEnum, ObservationStatusEnum, SeverityEnum, DisciplineEnum
)

class ObservationResponseRead(BaseModel):
    id: str
    observation_id: str
    author: str
    author_role: str
    response_text: str
    attached_document_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class ObservationResponseCreate(BaseModel):
    response_text: str
    author_role: str = "contractor"
    attached_document_id: Optional[str] = None

class AuditObservationRead(BaseModel):
    id: str
    organization_id: str
    project_id: str
    stage: str
    code: str
    item_type: ObservationTypeEnum
    title: str
    description: str
    recommendation: Optional[str] = None
    discipline: str
    severity: str
    status: ObservationStatusEnum
    
    rule_finding_id: Optional[str] = None
    rule_id: Optional[str] = None
    rule_code: Optional[str] = None
    document_id: Optional[str] = None
    document_filename: Optional[str] = None
    sheet_id: Optional[str] = None
    sheet_title: Optional[str] = None
    review_run_id: Optional[str] = None
    
    required_deliverable_type: Optional[str] = None
    provisioned_document_id: Optional[str] = None
    provisioned_document_filename: Optional[str] = None
    resolution_notes: Optional[str] = None
    
    issued_by: str
    assigned_to: Optional[str] = None
    issued_at: Optional[datetime] = None
    answered_at: Optional[datetime] = None
    provisioned_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    
    history_trace: List[Dict[str, Any]] = Field(default_factory=list)
    responses: List[ObservationResponseRead] = Field(default_factory=list)
    
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class GenerateObservationsRequest(BaseModel):
    project_id: str
    review_run_id: Optional[str] = None
    stage: Optional[str] = None

class IssueObservationRequest(BaseModel):
    assigned_to: Optional[str] = None
    notes: Optional[str] = None

class ProvisionEvidenceRequest(BaseModel):
    document_id: str
    notes: Optional[str] = None

class DeltaReevaluationResponse(BaseModel):
    observation_id: str
    code: str
    status_before: ObservationStatusEnum
    status_after: ObservationStatusEnum
    verdict_after: str
    is_resolved: bool
    affected_rules_evaluated: List[str]
    affected_sheets_evaluated: List[str]
    message: str
    trace_entry: Dict[str, Any]

class ReopenObservationRequest(BaseModel):
    reason: Optional[str] = None
