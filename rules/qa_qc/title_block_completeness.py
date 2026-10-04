import time
from rules.shared.base_rule import BaseRule, RuleContext, RuleResult, FindingDraft

class TitleBlockCompletenessRule(BaseRule):
    """Verifica que la viñeta contenga todos los campos obligatorios."""
    
    rule_code = "QAQC-TB-001"
    name = "Integridad de Campos Obligatorios en Viñeta"
    category = "qa_qc"
    discipline = "general"
    severity = "high"
    description = "Verifica que el plano contenga código de plano, escala, revisión y título."

    def evaluate(self, context: RuleContext) -> RuleResult:
        start_time = time.time()
        findings = []
        meta = context.sheet_metadata
        
        required_fields = {
            "sheet_code": "Código de Plano",
            "scale": "Escala",
            "revision": "Revisión",
            "title": "Título de Lámina"
        }
        
        missing = []
        for field, label in required_fields.items():
            if not meta.get(field):
                missing.append(label)
                
        if missing:
            findings.append(
                FindingDraft(
                    rule_code=self.rule_code,
                    rule_name=self.name,
                    severity=self.severity,
                    confidence=1.0,
                    title=f"Campos faltantes en viñeta: {', '.join(missing)}",
                    description=f"La viñeta del plano carece de los siguientes datos requeridos: {', '.join(missing)}.",
                    recommendation="Completar todos los campos del rótulo técnico según el estándar del proyecto.",
                    bbox=[0.72, 0.72, 0.99, 0.99] # Ubicación estándar de viñeta
                )
            )

        exec_time = (time.time() - start_time) * 1000
        return RuleResult(
            rule_code=self.rule_code,
            passed=len(findings) == 0,
            findings=findings,
            execution_time_ms=exec_time
        )
