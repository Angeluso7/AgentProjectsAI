from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class PipelineStageRunRead(BaseModel):
    id: str
    pipeline_run_id: str
    stage_name: str
    stage_order: int
    status: str
    job_id: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result_summary: Dict[str, Any] = {}
    error_message: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class ReviewPipelineRunRead(BaseModel):
    id: str
    scope_type: str
    scope_id: str
    pipeline_version: str
    requested_by: str
    status: str
    current_stage: str
    progress_percent: int
    summary: Dict[str, Any] = {}
    final_report_id: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    stages: Optional[List[PipelineStageRunRead]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ReviewPipelineRunCreateRequest(BaseModel):
    force_reprocess: Optional[bool] = Field(default=False, description="Forzar reprocesamiento de etapas previamente ejecutadas")
    requested_by: Optional[str] = Field(default="auditor_qa", description="Usuario o sistema solicitante")

class PipelineActionResponse(BaseModel):
    pipeline_run_id: str
    status: str
    current_stage: str
    progress_percent: int
    poll_url: str
    message: str
