from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

@dataclass
class ReportFindingDetail:
    id: str
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
    evidence_refs: Dict[str, Any] = field(default_factory=dict)
    expected_value: Optional[Any] = None
    observed_value: Optional[Any] = None
    delta: Optional[Any] = None
    resolutions: List[Dict[str, Any]] = field(default_factory=list)
    source_traces: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class AuditReportData:
    report_id: str
    report_type: str
    report_scope: str # sheet, document, project
    generated_at_utc: str
    engine_version: str
    generated_by: str
    document_id: str
    document_filename: str
    sheet_id: Optional[str] = None
    sheet_code: Optional[str] = None
    sheet_title: Optional[str] = None
    scale_text: Optional[str] = None
    revision: Optional[str] = None
    discipline: str = "general"
    
    total_findings: int = 0
    by_severity: Dict[str, int] = field(default_factory=dict)
    by_status: Dict[str, int] = field(default_factory=dict)
    disciplines_involved: List[str] = field(default_factory=list)
    rules_evaluated: List[Dict[str, Any]] = field(default_factory=list)
    
    findings: List[ReportFindingDetail] = field(default_factory=list)
    traces: List[Dict[str, Any]] = field(default_factory=list)
