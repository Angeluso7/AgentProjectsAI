from datetime import datetime
from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class MaturityLevelEnum(str, Enum):
    insufficient = "insufficient"
    basic = "basic"
    intermediate = "intermediate"
    advanced = "advanced"
    exhaustive = "exhaustive"

class CriticalGapItem(BaseModel):
    id: str
    dimension: str
    discipline: str
    title: str
    description: str
    impact_rationale: str
    priority: str = "medium" # critical, high, medium, low
    blocked_rules_count: int = 0
    blocked_disciplines: List[str] = Field(default_factory=list)
    is_resolved: bool = False

class AcquisitionRouteItem(BaseModel):
    id: str
    gap_id: str
    gap_title: str
    suggested_source_type: str
    suggested_repository: str
    intake_method: str
    suggested_responsible: str
    target_discipline: str
    unlock_impact: str
    estimated_score_gain: float = 0.0
    status: str = "pending" # pending, in_progress, completed

class DimensionScoreDetail(BaseModel):
    score: float
    weight: float
    weighted_score: float
    title: str
    details: str
    sub_metrics: Dict[str, Any] = Field(default_factory=dict)

class DisciplineScoreDetail(BaseModel):
    score: float
    status: str # adequate, partial, insufficient
    doc_count: int = 0
    rule_count: int = 0
    gaps_count: int = 0

class AcquiredKnowledgeSummary(BaseModel):
    available_documents_count: int = 0
    validated_evidence_count: int = 0
    approved_kb_items_count: int = 0
    closed_rfis_count: int = 0
    unblocked_rules_count: int = 0
    recently_acquired_items: List[Dict[str, Any]] = Field(default_factory=list)

class AssistantUsageSummary(BaseModel):
    total_interactions: int = 0
    tasks_executed: List[str] = Field(default_factory=list)
    project_chunks_used_count: int = 0
    top_used_knowledge_items: List[Dict[str, Any]] = Field(default_factory=list)
    average_confidence: float = 0.0
    estimated_savings_usd: float = 0.0

class ReviewCapabilityAssessment(BaseModel):
    auditable_scope: str
    partially_auditable_scope: str
    blind_blocked_scope: str
    can_issue_stage_verdict: bool = False

class DeltaSummary(BaseModel):
    previous_score: Optional[float] = None
    score_delta: float = 0.0
    previous_level: Optional[str] = None
    level_changed: bool = False
    newly_resolved_gaps_count: int = 0
    evaluation_date: Optional[str] = None

class ProjectMaturityEvaluationRequest(BaseModel):
    stage: Optional[str] = None
    target_level: Optional[str] = "advanced"
    evaluated_by: Optional[str] = "system_maturity_engine"

class ProjectMaturityProfileRead(BaseModel):
    id: str
    organization_id: str
    project_id: str
    stage: str
    overall_score: float
    maturity_level: MaturityLevelEnum
    target_level: str
    is_target_achieved: bool
    dimension_scores: Dict[str, Any]
    discipline_scores: Dict[str, Any]
    critical_gaps: List[Dict[str, Any]]
    acquisition_routes: List[Dict[str, Any]]
    acquired_knowledge_summary: Dict[str, Any]
    assistant_usage_summary: Dict[str, Any]
    review_capability_assessment: Dict[str, Any]
    delta_summary: Dict[str, Any]
    evaluated_by: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
