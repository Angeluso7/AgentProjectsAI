from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

class RuleDefinitionRead(BaseModel):
    id: str
    code: str
    name: str
    category: str
    discipline: str
    severity_default: str
    description: str
    input_requirements: Dict[str, Any] = {}
    rule_logic_type: str
    is_active: bool
    enabled: bool = True
    source_status: str = "approved"
    execution_phase: int = 5
    version: str
    source_candidate_id: Optional[str] = None
    source_document_id: Optional[str] = None
    source_page: Optional[int] = None
    source_bbox: Optional[Any] = None
    source_excerpt: Optional[str] = None
    source_hash: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class RuleExecutionRead(BaseModel):
    id: str
    job_id: Optional[str] = None
    document_id: str
    sheet_id: Optional[str] = None
    rule_id: str
    rule_version: str
    execution_status: str
    input_snapshot: Dict[str, Any] = {}
    result_summary: Dict[str, Any] = {}
    confidence: float
    created_at: datetime

    class Config:
        from_attributes = True

class FindingResolutionRead(BaseModel):
    id: str
    finding_id: str
    resolution_type: str
    resolved_by: str
    notes: Optional[str] = None
    corrected_value: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True

class RuleFindingRead(BaseModel):
    id: str
    document_id: str
    sheet_id: Optional[str] = None
    rule_id: Optional[str] = None
    rule_code: str
    rule_name: str
    category: str
    severity: str
    status: str
    confidence: float
    finding_type: str
    title: str
    description: str
    recommendation: Optional[str] = None
    evidence_refs: Dict[str, Any] = {}
    expected_value: Optional[Any] = None
    observed_value: Optional[Any] = None
    delta: Optional[Any] = None
    source_trace_ids: List[str] = []
    review_task_id: Optional[str] = None
    bbox: Optional[List[float]] = None
    resolutions: Optional[List[FindingResolutionRead]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class FindingResolutionRequest(BaseModel):
    resolution_type: str = Field(..., description="confirmed, dismissed, corrected, accepted_risk")
    resolved_by: Optional[str] = Field(default="auditor_qa", description="Identificador del auditor")
    notes: Optional[str] = Field(default=None, description="Justificación técnica o dictamen")
    corrected_value: Optional[Dict[str, Any]] = Field(default=None, description="Valores corregidos si aplica")

class RuleEvaluationSummaryResponse(BaseModel):
    document_id: Optional[str] = None
    sheet_id: Optional[str] = None
    total_rules_evaluated: int
    passed_count: int
    failed_count: int
    warning_count: int
    insufficient_evidence_count: int
    findings_generated: int
    by_severity: Dict[str, int]


class UpdateRuleStatusRequest(BaseModel):
    enabled: bool = Field(..., description="Estado de activación de la regla (sincroniza enabled e is_active)")

    model_config = ConfigDict(extra="forbid")


class DeleteRuleResponse(BaseModel):
    message: str
    code: str
    deleted: bool = False
    deactivated: bool = False

    model_config = ConfigDict(extra="forbid")

