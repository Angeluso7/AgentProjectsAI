from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from app.schemas.common import (
    ProjectStageEnum, DeliverableTypeEnum, EvidenceReadinessStatusEnum,
    AuditVerdictEnum, UnverifiableReasonEnum, DisciplineEnum
)

class DeliverableRequirementRead(BaseModel):
    id: str
    stage: str
    discipline: str
    deliverable_type: DeliverableTypeEnum
    title: str
    description: Optional[str] = None
    is_mandatory: bool
    blocked_rule_codes: List[str] = Field(default_factory=list)

    class Config:
        from_attributes = True

class DocumentDeliverableRead(BaseModel):
    id: str
    project_id: str
    document_id: str
    discipline_code: Optional[str] = None
    deliverable_type: DeliverableTypeEnum
    readiness_status: EvidenceReadinessStatusEnum
    validation_notes: Optional[str] = None
    classified_by: str
    validated_at: Optional[datetime] = None
    document_filename: Optional[str] = None
    document_title: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ClassifyDocumentDeliverableRequest(BaseModel):
    deliverable_type: DeliverableTypeEnum
    discipline_code: Optional[str] = None
    readiness_status: Optional[EvidenceReadinessStatusEnum] = EvidenceReadinessStatusEnum.CLASSIFIED
    validation_notes: Optional[str] = None

class UpdateDocumentReadinessRequest(BaseModel):
    readiness_status: EvidenceReadinessStatusEnum
    validation_notes: Optional[str] = None

class BlockedRuleInfo(BaseModel):
    rule_code: str
    rule_name: str
    discipline: str
    blocked_by_deliverable_title: str
    blocked_by_deliverable_type: DeliverableTypeEnum
    reason: UnverifiableReasonEnum = UnverifiableReasonEnum.BLOCKED_BY_MISSING_DOC
    detail: str

class CompletenessMatrixItem(BaseModel):
    requirement: DeliverableRequirementRead
    provided_documents: List[DocumentDeliverableRead] = Field(default_factory=list)
    is_fulfilled: bool
    status: str # "eligible", "pending_validation", "missing_mandatory", "missing_optional"

class ProjectCompletenessEvaluationRead(BaseModel):
    id: str
    project_id: str
    stage: str
    completeness_percentage: float
    is_gate_passed: bool
    total_required_count: int
    eligible_count: int
    missing_mandatory_count: int
    missing_optional_count: int
    blocked_rules_count: int
    deliverables_matrix: List[Dict[str, Any]] = Field(default_factory=list)
    missing_deliverables: List[Dict[str, Any]] = Field(default_factory=list)
    blocked_rules: List[Dict[str, Any]] = Field(default_factory=list)
    evaluated_at: datetime

    class Config:
        from_attributes = True
