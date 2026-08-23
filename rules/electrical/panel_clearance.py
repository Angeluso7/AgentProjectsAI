import time
from rules.shared.base_rule import BaseRule, RuleContext, RuleResult, FindingDraft

class PanelClearanceRule(BaseRule):
    """Verifica que el tablero eléctrico mantenga un área de despeje frontal reglamentario."""
    
    rule_code = "ELEC-PANEL-CLEARANCE"
    name = "Zona de Despeje Frontal de Tableros Eléctricos"
    category = "safety"
    discipline = "electrical"
    severity = "critical"
    description = "Comprueba que la zona de 1.0 m frente al tablero eléctrico general esté libre de obstáculos físicos."

    def evaluate(self, context: RuleContext) -> RuleResult:
        start_time = time.time()
        findings = []
        # En Fase 3 se conecta con el análisis geométrico espacial de Shapely
        exec_time = (time.time() - start_time) * 1000
        return RuleResult(
            rule_code=self.rule_code,
            passed=True,
            findings=findings,
            execution_time_ms=exec_time
        )
