from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class ReviewDisciplineResponse(BaseModel):
    id: str
    code: str
    name: str
    description: Optional[str] = None
    order_index: int = 0
    is_active: bool = True

    class Config:
        from_attributes = True


class ReviewTopicResponse(BaseModel):
    id: str
    discipline_id: Optional[str] = None
    code: str
    name: str
    description: Optional[str] = None
    is_transversal: bool = False
    enabled_mvp: bool = False
    order_index: int = 0
    is_active: bool = True

    class Config:
        from_attributes = True


class ReviewPlanRequest(BaseModel):
    project_id: str = Field(..., description="ID del proyecto activo")
    discipline_code: str = Field(..., description="Código de la especialidad (e.g. PIPING, GENERAL)")
    topic_code: str = Field(..., description="Código del punto de revisión (e.g. PID_SYMBOLS)")
    document_ids: Optional[List[str]] = Field(None, description="IDs de documentos del proyecto a evaluar")
    mode: str = Field("production", description="production o sandbox")


class ReviewPlanResponse(BaseModel):
    project_id: str
    project_code: Optional[str] = None
    project_name: Optional[str] = None
    discipline_code: str
    discipline_name: str
    topic_code: str
    topic_name: str
    execution_mode: str
    can_execute: bool
    empty_reason: Optional[str] = None
    applicable_rules: List[Dict[str, Any]] = []
    unapproved_rules: List[Dict[str, Any]] = []
    included_documents: List[Dict[str, Any]] = []
    excluded_documents: List[Dict[str, Any]] = []
    missing_required_document_types: List[Dict[str, Any]] = []
    phases_blueprint: List[Dict[str, Any]] = []
    warnings: List[str] = []
    limitations: List[str] = []


class ReviewRunCreateRequest(BaseModel):
    project_id: str = Field(..., description="ID del proyecto activo")
    discipline_code: str = Field(..., description="Código de especialidad")
    topic_code: str = Field(..., description="Código de punto de revisión")
    document_ids: List[str] = Field(..., description="Lista de IDs de documentos del proyecto")
    mode: str = Field("production", description="production o sandbox")
    run_name: Optional[str] = Field(None, description="Nombre personalizado para la auditoría")


class ReviewRunExecuteResponse(BaseModel):
    review_run_id: str
    project_id: str
    run_name: str
    discipline_code: str
    topic_code: str
    execution_mode: str
    status: str
    execution_time_sec: float
    rules_applied_count: int
    findings_count: int
    summary_stats: Dict[str, Any] = {}
    report_id: Optional[str] = None
    report_sha256: Optional[str] = None


class ReviewRunDetailsResponse(BaseModel):
    id: str
    project_id: str
    run_name: str
    discipline_code: str
    discipline_name: str
    topic_code: str
    topic_name: str
    execution_mode: str
    status: str
    requested_by: str
    requested_at: Optional[str] = None
    completed_at: Optional[str] = None
    execution_time_sec: float
    rule_count: int
    document_count: int
    findings_count: int
    summary_stats: Dict[str, Any] = {}
    documents: List[Dict[str, Any]] = []
    steps: List[Dict[str, Any]] = []
    executions: List[Dict[str, Any]] = []
    findings: List[Dict[str, Any]] = []


class ReviewExportCreateRequest(BaseModel):
    format: str = Field("json", description="Formato de exportación: json, xlsx, pdf")


class ReviewReportResponse(BaseModel):
    id: str
    project_id: str
    review_run_id: str
    report_name: str
    format: str
    artifact_path: str
    sha256: str
    status: str
    baseline_catalog_version: Optional[str] = None
    stats_summary: Dict[str, Any] = {}
    created_at: datetime

    class Config:
        from_attributes = True
