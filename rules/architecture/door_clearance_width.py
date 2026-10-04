import time
from rules.shared.base_rule import BaseRule, RuleContext, RuleResult, FindingDraft

class DoorClearanceWidthRule(BaseRule):
    """Verifica que el ancho de vanos de puertas cumpla con el estándar mínimo normativo."""
    
    rule_code = "ARQ-DOOR-MIN-WIDTH"
    name = "Ancho Mínimo Normativo de Vano de Puerta"
    category = "normative"
    discipline = "architecture"
    severity = "high"
    description = "Comprueba que las puertas de recintos habitables tengan un ancho libre mayor o igual a 0.85 m."

    MIN_WIDTH_M = 0.85

    def evaluate(self, context: RuleContext) -> RuleResult:
        start_time = time.time()
        findings = []
        
        # En Fase 2 se alimenta de los datos del cuadro de vanos extraído en context.extracted_tables
        for table in context.extracted_tables:
            if table.get("table_type") == "door_schedule":
                for row in table.get("rows", []):
                    door_id = row.get("door_id", "Desconocido")
                    try:
                        width = float(row.get("width_m", 0))
                        if 0 < width < self.MIN_WIDTH_M:
                            findings.append(
                                FindingDraft(
                                    rule_code=self.rule_code,
                                    rule_name=self.name,
                                    severity=self.severity,
                                    confidence=1.0,
                                    title=f"Puerta {door_id} con ancho insuficiente ({width} m)",
                                    description=f"La puerta {door_id} tiene un ancho declarado de {width} m, inferior al mínimo exigido de {self.MIN_WIDTH_M} m.",
                                    recommendation=f"Aumentar el ancho del vano a un mínimo de {self.MIN_WIDTH_M} m o justificar excepción de recinto técnico.",
                                    evidence_data={"door_id": door_id, "width_m": width, "threshold_m": self.MIN_WIDTH_M}
                                )
                            )
                    except (ValueError, TypeError):
                        pass

        exec_time = (time.time() - start_time) * 1000
        return RuleResult(
            rule_code=self.rule_code,
            passed=len(findings) == 0,
            findings=findings,
            execution_time_ms=exec_time
        )
