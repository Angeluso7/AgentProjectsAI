from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class EvidenceManifestRead(BaseModel):
    id: str
    report_id: str
    manifest_json: Dict[str, Any]
    sha256_bundle: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class AuditReportRead(BaseModel):
    id: str
    document_id: str
    sheet_id: Optional[str] = None
    report_type: str
    report_scope: str
    status: str
    generated_by: str
    source_rule_execution_ids: List[str] = []
    source_finding_ids: List[str] = []
    summary: Dict[str, Any] = {}
    artifact_pdf_path: Optional[str] = None
    artifact_json_path: Optional[str] = None
    artifact_bundle_path: Optional[str] = None
    manifest_hash: Optional[str] = None
    manifest: Optional[EvidenceManifestRead] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class AuditReportCreateRequest(BaseModel):
    report_type: Optional[str] = Field(default="technical_audit_qaqc", description="Tipo de reporte")
    generated_by: Optional[str] = Field(default="auditor_qa", description="Identificador del autor o sistema")

class AuditReportSummaryResponse(BaseModel):
    total_reports: int
    by_type: Dict[str, int]
    by_scope: Dict[str, int]
    latest_report: Optional[AuditReportRead] = None
