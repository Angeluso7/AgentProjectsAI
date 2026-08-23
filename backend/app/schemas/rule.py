from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from app.schemas.common import SeverityEnum, DisciplineEnum

class RuleDefinitionSchema(BaseModel):
    rule_code: str = Field(..., example="QAQC-TB-001")
    name: str = Field(..., example="Integridad de Datos en Viñeta")
    category: str = Field(..., example="qa_qc")
    discipline: DisciplineEnum = DisciplineEnum.GENERAL
    severity: SeverityEnum = SeverityEnum.HIGH
    description: str = Field(..., example="Valida que la viñeta contenga código de plano, escala y fecha")
    enabled: bool = True
    parameters: Dict[str, Any] = Field(default_factory=dict)

class RuleEvaluationRequest(BaseModel):
    project_id: str
    sheet_ids: Optional[List[str]] = None
    rule_codes: Optional[List[str]] = None

class RuleEvaluationResult(BaseModel):
    rule_code: str
    rule_name: str
    passed: bool
    severity: SeverityEnum
    findings_count: int
    execution_time_ms: float
    details: Dict[str, Any] = Field(default_factory=dict)
