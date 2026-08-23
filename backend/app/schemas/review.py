from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from app.schemas.common import SeverityEnum, FindingStatusEnum, FeedbackActionEnum

class FindingEvidenceRead(BaseModel):
    id: str
    evidence_type: str
    reference_id: Optional[str] = None
    description: Optional[str] = None
    crop_image_path: Optional[str] = None
    metadata_info: Dict[str, Any] = {}
    class Config:
        from_attributes = True

class HumanFeedbackCreate(BaseModel):
    action: FeedbackActionEnum
    corrected_bbox: Optional[List[float]] = None
    corrected_class: Optional[str] = None
    notes: Optional[str] = None

class HumanFeedbackRead(BaseModel):
    id: str
    finding_id: str
    user_id: Optional[str] = None
    action: FeedbackActionEnum
    corrected_bbox: Optional[List[float]] = None
    corrected_class: Optional[str] = None
    notes: Optional[str] = None
    sent_to_active_learning: bool
    created_at: datetime
    class Config:
        from_attributes = True

class FindingRead(BaseModel):
    id: str
    review_run_id: str
    sheet_id: Optional[str] = None
    rule_code: str
    rule_name: str
    category: str
    severity: SeverityEnum
    confidence: float
    title: str
    description: str
    recommendation: Optional[str] = None
    status: FindingStatusEnum
    bbox: Optional[List[float]] = None
    created_at: datetime
    evidences: List[FindingEvidenceRead] = []
    feedbacks: List[HumanFeedbackRead] = []
    class Config:
        from_attributes = True

class ReviewRunCreate(BaseModel):
    project_id: str
    run_name: str
    document_ids: Optional[List[str]] = None

class ReviewRunRead(BaseModel):
    id: str
    project_id: str
    run_name: str
    status: str
    rules_applied_count: int
    findings_count: int
    execution_time_sec: float
    summary_stats: Dict[str, Any] = {}
    created_at: datetime
    completed_at: Optional[datetime] = None
    findings: List[FindingRead] = []
    class Config:
        from_attributes = True
