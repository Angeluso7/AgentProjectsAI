from typing import Dict, Any, List

DEFAULT_QUALITY_GATES = [
    {
        "gate_id": "ocr_cer_baseline",
        "component": "ocr",
        "metric_name": "cer",
        "operator": "<=",
        "threshold": 0.15,
        "warning_threshold": 0.25,
        "min_sample_size": 3,
        "description": "CER de OCR no debe superar 15% en muestras técnicas"
    },
    {
        "gate_id": "layout_miou_baseline",
        "component": "layout",
        "metric_name": "mean_iou",
        "operator": ">=",
        "threshold": 0.70,
        "warning_threshold": 0.55,
        "min_sample_size": 3,
        "description": "Mean IoU macro-regional debe ser al menos 70%"
    },
    {
        "gate_id": "title_block_required_completeness",
        "component": "title_block",
        "metric_name": "required_completeness",
        "operator": ">=",
        "threshold": 0.85,
        "warning_threshold": 0.70,
        "min_sample_size": 3,
        "description": "Completitud de campos requeridos de viñeta >= 85%"
    },
    {
        "gate_id": "table_cell_accuracy",
        "component": "table",
        "metric_name": "cell_accuracy",
        "operator": ">=",
        "threshold": 0.75,
        "warning_threshold": 0.60,
        "min_sample_size": 2,
        "description": "Exactitud de celdas tabulares extraídas >= 75%"
    },
    {
        "gate_id": "rules_precision_baseline",
        "component": "rules",
        "metric_name": "precision",
        "operator": ">=",
        "threshold": 0.80,
        "warning_threshold": 0.65,
        "min_sample_size": 3,
        "description": "Precisión en hallazgos de reglas QA/QC >= 80%"
    }
]

class QualityGateEvaluator:
    """Evaluador de Quality Gates configurables y baselines de calidad."""

    @staticmethod
    def evaluate(
        metrics_by_component: Dict[str, Dict[str, Any]],
        custom_gates: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        gates = custom_gates or DEFAULT_QUALITY_GATES
        gate_results = []
        overall_status = "pass"

        for g in gates:
            comp = g.get("component")
            m_name = g.get("metric_name")
            min_n = g.get("min_sample_size", 1)
            op = g.get("operator", ">=")
            thresh = g.get("threshold", 0.8)
            warn_thresh = g.get("warning_threshold", thresh * 0.8)

            comp_metrics = metrics_by_component.get(comp, {})
            observed_val = comp_metrics.get(m_name)
            sample_count = comp_metrics.get("sample_count", 0)

            if observed_val is None or sample_count < min_n:
                status = "insufficient_sample"
                reason = f"Muestra insuficiente (N={sample_count}, requerido N>={min_n})"
            else:
                if op == "<=":
                    if observed_val <= thresh:
                        status = "pass"
                        reason = f"Valor {observed_val} cumple umbral <= {thresh}"
                    elif observed_val <= warn_thresh:
                        status = "warning"
                        reason = f"Valor {observed_val} excede umbral pero dentro de alerta <= {warn_thresh}"
                    else:
                        status = "fail"
                        reason = f"Valor {observed_val} excede umbral máximo permitido {warn_thresh}"
                else: # ">="
                    if observed_val >= thresh:
                        status = "pass"
                        reason = f"Valor {observed_val} cumple umbral >= {thresh}"
                    elif observed_val >= warn_thresh:
                        status = "warning"
                        reason = f"Valor {observed_val} bajo umbral objetivo pero sobre alerta >= {warn_thresh}"
                    else:
                        status = "fail"
                        reason = f"Valor {observed_val} bajo umbral mínimo crítico {warn_thresh}"

            if status == "fail":
                overall_status = "fail"
            elif status == "warning" and overall_status != "fail":
                overall_status = "warning"
            elif status == "insufficient_sample" and overall_status == "pass":
                overall_status = "insufficient_sample"

            gate_results.append({
                "gate_id": g.get("gate_id"),
                "component": comp,
                "metric_name": m_name,
                "status": status,
                "observed_value": observed_val,
                "threshold": thresh,
                "sample_count": sample_count,
                "reason": reason,
                "description": g.get("description")
            })

        return {
            "overall_status": overall_status,
            "gates_evaluated_count": len(gate_results),
            "gate_results": gate_results
        }
