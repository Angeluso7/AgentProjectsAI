import time
from rules.shared.base_rule import BaseRule, RuleContext, RuleResult, FindingDraft

class ScaleConsistencyRule(BaseRule):
    """Verifica que la escala declarada sea un formato estándar de ingeniería/arquitectura."""
    
    rule_code = "QAQC-SCALE-002"
    name = "Formato Válido de Escala Nominal"
    category = "qa_qc"
    discipline = "general"
    severity = "medium"
    description = "Valida que la escala declarada en viñeta pertenezca al catálogo estándar (ej: 1:50, 1:100, 1:200, INDICADA)."

    ALLOWED_SCALES = ["1:1", "1:5", "1:10", "1:20", "1:25", "1:50", "1:75", "1:100", "1:125", "1:200", "1:250", "1:500", "1:1000", "INDICADAS", "S/E", "SIN ESCALA"]

    def evaluate(self, context: RuleContext) -> RuleResult:
        start_time = time.time()
        findings = []
        scale_raw = context.sheet_metadata.get("scale", "").strip().upper()
        
        if scale_raw and scale_raw not in self.ALLOWED_SCALES:
            findings.append(
                FindingDraft(
                    rule_code=self.rule_code,
                    rule_name=self.name,
                    severity=self.severity,
                    confidence=1.0,
                    title=f"Formato no estándar de escala '{scale_raw}'",
                    description=f"La escala '{scale_raw}' indicada en la viñeta no coincide con las escalas normalizadas estándar.",
                    recommendation="Normalizar la escala indicada en el rótulo técnico (ej: 1:50 o INDICADAS)."
                )
            )

        exec_time = (time.time() - start_time) * 1000
        return RuleResult(
            rule_code=self.rule_code,
            passed=len(findings) == 0,
            findings=findings,
            execution_time_ms=exec_time
        )
