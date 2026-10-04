from abc import ABC, abstractmethod
from typing import Dict, Any
from app.services.rules.contracts import RuleInput, RuleResult

class BaseRule(ABC):
    """Clase base abstracta para todas las reglas determinísticas QA/QC."""
    code: str
    name: str
    category: str
    discipline: str
    severity_default: str
    version: str = "1.0"
    description: str
    rule_logic_type: str

    @abstractmethod
    def evaluate(self, inputs: RuleInput) -> RuleResult:
        """Ejecuta la evaluación determinística contra los inputs provistos."""
        pass

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "category": self.category,
            "discipline": self.discipline,
            "severity_default": self.severity_default,
            "version": self.version,
            "description": self.description,
            "rule_logic_type": self.rule_logic_type,
            "is_active": True
        }
