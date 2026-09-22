from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ProjectExecutiveMetrics(BaseModel):
    project_id: Optional[str] = None
    project_code: Optional[str] = None
    project_name: Optional[str] = None
    client_name: Optional[str] = None
    discipline: Optional[str] = None
    stage: Optional[str] = None
    
    # Documentos y Láminas
    documents_total: int = 0
    documents_processed: int = 0
    sheets_total: int = 0
    sheets_rasterized: int = 0
    progress_percentage: float = 0.0
    
    # Reglas y Cumplimiento
    active_rules_count: int = 0
    compliance_score: float = 0.0
    
    # Hallazgos
    findings_total: int = 0
    findings_critical: int = 0
    findings_high: int = 0
    findings_medium: int = 0
    findings_low: int = 0
    findings_resolved: int = 0
    findings_open: int = 0
    
    # Validaciones Humanas HITL
    pending_validations_count: int = 0
    
    # Cobertura Informacional
    information_coverage_score: float = 0.0
    maturity_stage: Optional[str] = "inicial"
    
    # Último Run de Auditoría
    last_review_run: Optional[Dict[str, Any]] = None


class EngineHealthItem(BaseModel):
    engine_id: str
    name: str
    category: str  # vision, ocr, llm, rules, web, mlops
    status: str    # online, degraded, offline
    latency_ms: int = 0
    description: str


class BackgroundJobsSummary(BaseModel):
    queued: int = 0
    running: int = 0
    completed: int = 0
    failed: int = 0
    total: int = 0


class AgentGlobalHealth(BaseModel):
    overall_status: str  # healthy, degraded, critical
    engines: List[EngineHealthItem] = Field(default_factory=list)
    jobs_summary: BackgroundJobsSummary = Field(default_factory=BackgroundJobsSummary)
    average_confidence: float = 0.0
    knowledge_reuse_count: int = 0
    precedents_applied_count: int = 0
    duplicates_detected_count: int = 0
    system_uptime: str = "99.9%"


class AgentActivityLog(BaseModel):
    id: str
    timestamp: datetime
    activity_type: str  # one_click_review, extraction, hitl_feedback, web_search, maintenance
    title: str
    description: str
    severity: str = "info"  # info, warning, success, error
    project_id: Optional[str] = None
    user_name: Optional[str] = None


class ExecutiveAlert(BaseModel):
    id: str
    alert_type: str  # critical_finding, missing_deliverable, unprocessed_sheet, failed_job, unindexed_norm
    title: str
    message: str
    severity: str    # critical, high, medium, info
    action_label: str
    action_target_tab: str
    created_at: datetime


class ExecutiveDashboardSummary(BaseModel):
    timestamp: datetime
    project_metrics: ProjectExecutiveMetrics
    agent_health: AgentGlobalHealth
    recent_activities: List[AgentActivityLog] = Field(default_factory=list)
    alerts_and_recommendations: List[ExecutiveAlert] = Field(default_factory=list)
    quick_shortcuts: List[Dict[str, Any]] = Field(default_factory=list)
