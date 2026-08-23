from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

class RuleContext(BaseModel):
    """Contexto de datos proporcionado a una regla durante la evaluación."""
    sheet_id: str
    sheet_metadata: Dict[str, Any] = Field(default_factory=dict)
    extracted_texts: List[Dict[str, Any]] = Field(default_factory=list)
    detected_symbols: List[Dict[str, Any]] = Field(default_factory=list)
    extracted_tables: List[Dict[str, Any]] = Field(default_factory=list)
    regions: List[Dict[str, Any]] = Field(default_factory=list)

class FindingDraft(BaseModel):
    """Borrador de hallazgo generado por una regla."""
    rule_code: str
    rule_name: str
    severity: str # critical, high, medium, low, info
    confidence: float = 1.0
    title: str
    description: str
    recommendation: Optional[str] = None
    bbox: Optional[List[float]] = None
    evidence_data: Dict[str, Any] = Field(default_factory=dict)

class RuleResult(BaseModel):
    """Resultado de la ejecución de una regla."""
    rule_code: str
    passed: bool
    findings: List[FindingDraft] = Field(default_factory=list)
    execution_time_ms: float = 0.0

class BaseRule(ABC):
    """Clase base abstracta para todas las reglas determinísticas del sistema."""

    rule_code: str = "BASE-000"
    name: str = "Base Rule"
    category: str = "general"
    discipline: str = "general"
    severity: str = "medium"
    description: str = ""

    @abstractmethod
    def evaluate(self, context: RuleContext) -> RuleResult:
        """Evalúa la regla contra el contexto de la hoja y devuelve el resultado."""
        pass
