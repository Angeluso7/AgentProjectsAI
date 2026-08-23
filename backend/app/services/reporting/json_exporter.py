import json
import os
from typing import Dict, Any
from app.services.reporting.contracts import AuditReportData

class TechnicalAuditJsonExporter:
    """Exportador de auditorías técnicas en JSON estructurado, normalizado y versionado."""

    @classmethod
    def export_json(cls, data: AuditReportData, output_file_path: str) -> str:
        os.makedirs(os.path.dirname(output_file_path), exist_ok=True)

        payload: Dict[str, Any] = {
            "schema_version": "1.0",
            "metadata": {
                "report_id": data.report_id,
                "report_type": data.report_type,
                "report_scope": data.report_scope,
                "generated_at_utc": data.generated_at_utc,
                "engine_version": data.engine_version,
                "generated_by": data.generated_by
            },
            "target": {
                "document_id": data.document_id,
                "document_filename": data.document_filename,
                "sheet_id": data.sheet_id,
                "sheet_code": data.sheet_code,
                "sheet_title": data.sheet_title,
                "scale_text": data.scale_text,
                "revision": data.revision,
                "discipline": data.discipline
            },
            "summary": {
                "total_findings": data.total_findings,
                "by_severity": data.by_severity,
                "by_status": data.by_status,
                "disciplines_involved": data.disciplines_involved,
                "rules_evaluated_count": len(data.rules_evaluated)
            },
            "rules_evaluated": data.rules_evaluated,
            "findings": [
                {
                    "id": f.id,
                    "rule_code": f.rule_code,
                    "rule_name": f.rule_name,
                    "category": f.category,
                    "severity": f.severity,
                    "status": f.status,
                    "confidence": f.confidence,
                    "finding_type": f.finding_type,
                    "title": f.title,
                    "description": f.description,
                    "recommendation": f.recommendation,
                    "expected_value": f.expected_value,
                    "observed_value": f.observed_value,
                    "delta": f.delta,
                    "evidence_refs": f.evidence_refs,
                    "resolutions": f.resolutions,
                    "source_traces": f.source_traces
                }
                for f in data.findings
            ],
            "decision_traces": data.traces
        }

        with open(output_file_path, "w", encoding="utf-8") as f_out:
            json.dump(payload, f_out, indent=2, ensure_ascii=False)

        return output_file_path
