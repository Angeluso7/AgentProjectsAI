from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class StageDeliverableMatrixItem(BaseModel):
    requirement_id: str
    title: str
    deliverable_type: str
    is_mandatory: bool
    readiness_status: str
    provided_files_count: int = 0
    is_fulfilled: bool = False
    blocked_rule_codes: List[str] = Field(default_factory=list)

class StageCompletenessSummary(BaseModel):
    completeness_percentage: float
    is_gate_passed: bool
    total_required_count: int
    eligible_count: int
    missing_mandatory_count: int
    missing_optional_count: int
    blocked_rules_count: int
    deliverables_matrix: List[StageDeliverableMatrixItem] = Field(default_factory=list)
    missing_deliverables: List[Dict[str, Any]] = Field(default_factory=list)
    blocked_rules: List[Dict[str, Any]] = Field(default_factory=list)

class AuditVerdictItem(BaseModel):
    rule_code: str
    rule_name: str
    category: str
    discipline: str
    verdict: str # cumple, no_cumple, no_verificable, no_aplica
    unverifiable_reason: Optional[str] = None
    findings_count: int = 0
    sheet_code: Optional[str] = None
    document_filename: Optional[str] = None

class AuditVerdictsBreakdown(BaseModel):
    cumple_count: int
    no_cumple_count: int
    no_verificable_count: int
    no_aplica_count: int
    total_rules_evaluated: int
    by_discipline: Dict[str, Dict[str, int]] = Field(default_factory=dict)
    verdicts_list: List[AuditVerdictItem] = Field(default_factory=list)

class ObservationReportItem(BaseModel):
    id: str
    code: str
    item_type: str # technical_observation, information_request, document_blocker, minor_missing
    title: str
    discipline: str
    severity: str
    status: str # draft, issued, answered, provisioned, validated, closed
    rule_code: Optional[str] = None
    document_filename: Optional[str] = None
    provisioned_filename: Optional[str] = None
    responses_count: int = 0

class ObservationsBreakdown(BaseModel):
    total_obs: int = 0
    open_obs: int = 0
    closed_obs: int = 0
    critical_obs: int = 0
    high_obs: int = 0
    medium_obs: int = 0
    low_obs: int = 0
    total_rfi: int = 0
    open_rfi: int = 0
    answered_rfi: int = 0
    closed_rfi: int = 0
    total_blk: int = 0
    active_blk: int = 0
    resolved_blk: int = 0
    total_min: int = 0
    items: List[ObservationReportItem] = Field(default_factory=list)

class DeltaEvolutionBreakdown(BaseModel):
    previous_snapshot_id: Optional[str] = None
    previous_revision_number: Optional[int] = None
    resolved_since_last_rev: List[Dict[str, Any]] = Field(default_factory=list)
    new_since_last_rev: List[Dict[str, Any]] = Field(default_factory=list)
    unblocked_rules_since_last_rev: List[str] = Field(default_factory=list)
    status_changes: List[Dict[str, Any]] = Field(default_factory=list)
    summary_narrative: str = "Primera emisión de revisión técnica para esta etapa."

class ConsolidatedStageReportRead(BaseModel):
    id: Optional[str] = None
    project_id: str
    project_name: str
    project_code: str
    stage: str
    revision_number: int = 1
    title: str
    global_stage_verdict: str # aprobable, aprobable_con_observaciones, parcial_incompleta, no_aprobable_bloqueada
    verdict_rationale: str
    issued_by: str
    issued_at: Optional[datetime] = None
    
    completeness: StageCompletenessSummary
    audit_verdicts: AuditVerdictsBreakdown
    observations: ObservationsBreakdown
    delta_evolution: DeltaEvolutionBreakdown
    
    artifact_pdf_path: Optional[str] = None
    artifact_json_path: Optional[str] = None
    manifest_hash: Optional[str] = None
    is_live_preview: bool = False

    class Config:
        from_attributes = True

class EmitStageReportRequest(BaseModel):
    project_id: str
    stage: Optional[str] = None
    title: Optional[str] = None
    notes: Optional[str] = None

class ProjectStageReportSnapshotSummary(BaseModel):
    id: str
    project_id: str
    stage: str
    revision_number: int
    title: str
    global_stage_verdict: str
    completeness_percentage: float
    open_obs_count: int
    open_rfi_count: int
    active_blk_count: int
    issued_by: str
    created_at: datetime

    class Config:
        from_attributes = True
