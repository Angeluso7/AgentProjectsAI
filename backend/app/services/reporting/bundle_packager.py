import os
import json
import hashlib
import zipfile
import shutil
from typing import Dict, Any, Tuple
from app.services.reporting.contracts import AuditReportData

class TechnicalAuditBundlePackager:
    """Empaquetador de evidencias y artefactos de auditoría con manifiesto de integridad SHA-256."""

    @staticmethod
    def compute_sha256(file_path: str) -> str:
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                sha256.update(chunk)
        return sha256.hexdigest()

    @classmethod
    def package_bundle(
        cls,
        data: AuditReportData,
        pdf_path: str,
        json_path: str,
        bundle_dir: str
    ) -> Tuple[str, str, Dict[str, Any]]:
        """
        Crea la estructura del paquete de evidencia, calcula los hashes de cada archivo,
        genera manifest.json y empaqueta todo en un archivo ZIP reproducible.
        
        Retorna: (zip_path, manifest_hash, manifest_dict)
        """
        os.makedirs(bundle_dir, exist_ok=True)
        report_dir = os.path.join(bundle_dir, "report")
        evidence_dir = os.path.join(bundle_dir, "evidence")
        os.makedirs(report_dir, exist_ok=True)
        os.makedirs(evidence_dir, exist_ok=True)

        # 1. Copiar reporte PDF y JSON
        dst_pdf = os.path.join(report_dir, "audit-report.pdf")
        dst_json = os.path.join(report_dir, "audit-report.json")
        shutil.copyfile(pdf_path, dst_pdf)
        shutil.copyfile(json_path, dst_json)

        # 2. Generar evidencias aisladas en /evidence/
        findings_path = os.path.join(evidence_dir, "findings.json")
        traces_path = os.path.join(evidence_dir, "traces.json")
        
        with open(findings_path, "w", encoding="utf-8") as f:
            json.dump([
                {
                    "id": f.id,
                    "rule_code": f.rule_code,
                    "severity": f.severity,
                    "status": f.status,
                    "title": f.title,
                    "evidence_refs": f.evidence_refs,
                    "expected": f.expected_value,
                    "observed": f.observed_value,
                    "delta": f.delta
                } for f in data.findings
            ], f, indent=2, ensure_ascii=False)

        with open(traces_path, "w", encoding="utf-8") as f:
            json.dump(data.traces, f, indent=2, ensure_ascii=False)

        # 3. Generar README.md explicativo
        readme_path = os.path.join(report_dir, "README.md")
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(
                f"# Paquete de Evidencia de Auditoría Técnica\n\n"
                f"- **ID Reporte:** `{data.report_id}`\n"
                f"- **Fecha UTC:** {data.generated_at_utc}\n"
                f"- **Documento Origen:** {data.document_filename}\n"
                f"- **Lámina:** {data.sheet_code or 'N/A'}\n"
                f"- **Total Hallazgos:** {data.total_findings}\n\n"
                f"Consulte `manifest.json` para verificar la integridad basada en hashes SHA-256 de cada archivo.\n"
            )

        # 4. Calcular hashes de cada archivo en el paquete
        files_to_hash = [
            ("report/audit-report.pdf", dst_pdf),
            ("report/audit-report.json", dst_json),
            ("report/README.md", readme_path),
            ("evidence/findings.json", findings_path),
            ("evidence/traces.json", traces_path),
        ]

        manifest_files = []
        for rel_path, abs_path in files_to_hash:
            if os.path.exists(abs_path):
                manifest_files.append({
                    "path": rel_path,
                    "sha256": cls.compute_sha256(abs_path),
                    "size_bytes": os.path.getsize(abs_path)
                })

        manifest_dict = {
            "manifest_version": "1.0",
            "report_id": data.report_id,
            "report_type": data.report_type,
            "timestamp_utc": data.generated_at_utc,
            "engine_version": data.engine_version,
            "integrity_algorithm": "SHA-256",
            "files_count": len(manifest_files),
            "files": manifest_files
        }

        # Guardar manifest.json
        manifest_path = os.path.join(report_dir, "manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_dict, f, indent=2, ensure_ascii=False)

        manifest_hash = cls.compute_sha256(manifest_path)

        # 5. Generar archivo ZIP reproducible
        zip_path = os.path.join(bundle_dir, "evidence-bundle.zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(bundle_dir):
                for file in files:
                    if file == "evidence-bundle.zip":
                        continue
                    full_file_path = os.path.join(root, file)
                    rel_zip_path = os.path.relpath(full_file_path, bundle_dir)
                    zipf.write(full_file_path, arcname=rel_zip_path)

        return zip_path, manifest_hash, manifest_dict
