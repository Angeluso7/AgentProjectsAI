import os
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.db.models.document_memory import (
    Document, DocumentSheet, TitleBlockExtraction, DetectedSymbol, ExtractedTable
)
from app.db.models.decision_memory import (
    RuleDefinition, RuleExecution, RuleFinding, FindingResolution
)
from app.db.models.operations import DecisionTrace
from app.db.models.reporting import AuditReport, EvidenceManifest
from app.db.repositories.document_repository import DocumentRepository
from app.services.reporting.contracts import AuditReportData, ReportFindingDetail
from app.services.reporting.pdf_renderer import TechnicalAuditPdfRenderer
from app.services.reporting.json_exporter import TechnicalAuditJsonExporter
from app.services.reporting.bundle_packager import TechnicalAuditBundlePackager
from app.core.config import settings
from app.core.logging import logger

class ReportingService:
    """Servicio orquestador de reportes técnicos de auditoría, exportaciones y paquetes de evidencia."""

    def __init__(self, db: Session):
        self.db = db
        self.doc_repo = DocumentRepository(db)
        self.base_export_dir = os.path.join(settings.DATA_DIR, "reports")

    def generate_sheet_report(
        self,
        sheet_id: str,
        report_type: str = "technical_audit_qaqc",
        generated_by: str = "auditor_qa",
        job_id: Optional[str] = None
    ) -> AuditReport:
        sheet = self.doc_repo.get_sheet_by_id(sheet_id)
        if not sheet:
            raise ValueError(f"Lámina '{sheet_id}' no encontrada.")

        doc = sheet.document
        report_id = str(uuid.uuid4())
        timestamp_utc = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

        # Recopilar viñeta, ejecuciones y hallazgos
        tb = self.db.query(TitleBlockExtraction).filter(TitleBlockExtraction.sheet_id == sheet_id).first()
        executions = self.db.query(RuleExecution).filter(RuleExecution.sheet_id == sheet_id).all()
        findings = self.db.query(RuleFinding).filter(RuleFinding.sheet_id == sheet_id).all()
        rules = self.db.query(RuleDefinition).all()

        # Recopilar trazas
        traces = self.db.query(DecisionTrace).filter(DecisionTrace.sheet_id == sheet_id).all()
        traces_data = [
            {
                "id": t.id,
                "trace_type": t.trace_type,
                "entity_type": t.entity_type,
                "confidence": t.confidence,
                "decision_status": t.decision_status,
                "explanation": t.explanation,
                "created_at": t.created_at.isoformat() if t.created_at else None
            }
            for t in traces
        ]

        # Estructurar hallazgos
        finding_details: List[ReportFindingDetail] = []
        by_sev = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        by_stat = {"open": 0, "confirmed": 0, "dismissed": 0, "corrected": 0, "accepted_risk": 0}

        for f in findings:
            if f.severity in by_sev:
                by_sev[f.severity] += 1
            if f.status in by_stat:
                by_stat[f.status] += 1

            resolutions = [
                {
                    "id": r.id,
                    "resolution_type": r.resolution_type,
                    "resolved_by": r.resolved_by,
                    "notes": r.notes,
                    "corrected_value": r.corrected_value,
                    "created_at": r.created_at.isoformat() if r.created_at else None
                }
                for r in f.resolutions
            ]

            finding_details.append(
                ReportFindingDetail(
                    id=f.id,
                    rule_code=f.rule_code,
                    rule_name=f.rule_name,
                    category=f.category,
                    severity=f.severity,
                    status=f.status,
                    confidence=f.confidence,
                    finding_type=f.finding_type,
                    title=f.title,
                    description=f.description,
                    recommendation=f.recommendation,
                    evidence_refs=f.evidence_refs or {},
                    expected_value=f.expected_value,
                    observed_value=f.observed_value,
                    delta=f.delta,
                    resolutions=resolutions,
                    source_traces=f.source_trace_ids or []
                )
            )

        # Reglas evaluadas
        rules_eval_data = [
            {
                "code": r.code,
                "name": r.name,
                "discipline": r.discipline,
                "severity_default": r.severity_default,
                "category": r.category
            }
            for r in rules
        ]

        report_data = AuditReportData(
            report_id=report_id,
            report_type=report_type,
            report_scope="sheet",
            generated_at_utc=timestamp_utc,
            engine_version="1.0",
            generated_by=generated_by,
            document_id=doc.id,
            document_filename=doc.filename,
            sheet_id=sheet.id,
            sheet_code=sheet.sheet_code or (tb.sheet_code if tb else "N/A"),
            sheet_title=sheet.title or (tb.sheet_title if tb else "Lámina Técnica"),
            scale_text=tb.scale_text if tb else None,
            revision=tb.revision if tb else None,
            discipline=tb.discipline if tb else "general",
            total_findings=len(findings),
            by_severity=by_sev,
            by_status=by_stat,
            disciplines_involved=[tb.discipline if tb else "general"],
            rules_evaluated=rules_eval_data,
            findings=finding_details,
            traces=traces_data
        )

        # Crear rutas para artefactos
        report_folder = os.path.join(self.base_export_dir, report_id)
        os.makedirs(report_folder, exist_ok=True)

        pdf_path = os.path.join(report_folder, "audit-report.pdf")
        json_path = os.path.join(report_folder, "audit-report.json")

        # 1. Renderizar PDF
        TechnicalAuditPdfRenderer.render_pdf(report_data, pdf_path)

        # 2. Exportar JSON
        TechnicalAuditJsonExporter.export_json(report_data, json_path)

        # 3. Empaquetar Bundle ZIP y Manifest
        bundle_dir = os.path.join(report_folder, "bundle")
        zip_path, manifest_hash, manifest_dict = TechnicalAuditBundlePackager.package_bundle(
            report_data, pdf_path, json_path, bundle_dir
        )

        # 4. Persistir registro de AuditReport en BD
        try:
            from app.db.models.core import Organization
            first_org = self.db.query(Organization).first()
            org_id = doc.organization_id or (first_org.id if first_org else "388d7837-9c5d-45fb-b3eb-69909a915e43")
        except Exception:
            org_id = doc.organization_id or "388d7837-9c5d-45fb-b3eb-69909a915e43"
        db_report = AuditReport(
            id=report_id,
            organization_id=org_id,
            document_id=doc.id,
            sheet_id=sheet.id,
            report_type=report_type,
            report_scope="sheet",
            status="completed",
            generated_by=generated_by,
            source_rule_execution_ids=[e.id for e in executions],
            source_finding_ids=[f.id for f in findings],
            summary={
                "total_findings": len(findings),
                "by_severity": by_sev,
                "by_status": by_stat,
                "rules_evaluated_count": len(rules)
            },
            artifact_pdf_path=os.path.relpath(pdf_path, settings.BASE_DIR),
            artifact_json_path=os.path.relpath(json_path, settings.BASE_DIR),
            artifact_bundle_path=os.path.relpath(zip_path, settings.BASE_DIR),
            manifest_hash=manifest_hash
        )
        self.db.add(db_report)
        self.db.commit()

        # 5. Persistir EvidenceManifest
        db_manifest = EvidenceManifest(
            organization_id=org_id,
            report_id=db_report.id,
            manifest_json=manifest_dict,
            sha256_bundle=TechnicalAuditBundlePackager.compute_sha256(zip_path)
        )
        self.db.add(db_manifest)
        self.db.commit()
        self.db.refresh(db_report)

        logger.info(f"Reporte de lámina {sheet_id} generado exitosamente: ID {report_id} (PDF, JSON, Bundle).")
        return db_report

    def generate_document_report(
        self,
        document_id: str,
        report_type: str = "technical_audit_qaqc",
        generated_by: str = "auditor_qa",
        job_id: Optional[str] = None
    ) -> AuditReport:
        doc = self.doc_repo.get_by_id(document_id)
        if not doc:
            raise ValueError(f"Documento '{document_id}' no encontrado.")

        report_id = str(uuid.uuid4())
        timestamp_utc = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

        executions = self.db.query(RuleExecution).filter(RuleExecution.document_id == document_id).all()
        findings = self.db.query(RuleFinding).filter(RuleFinding.document_id == document_id).all()
        rules = self.db.query(RuleDefinition).all()
        traces = self.db.query(DecisionTrace).filter(DecisionTrace.document_id == document_id).all()

        traces_data = [
            {
                "id": t.id,
                "trace_type": t.trace_type,
                "entity_type": t.entity_type,
                "confidence": t.confidence,
                "decision_status": t.decision_status,
                "explanation": t.explanation,
                "created_at": t.created_at.isoformat() if t.created_at else None
            }
            for t in traces
        ]

        finding_details: List[ReportFindingDetail] = []
        by_sev = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        by_stat = {"open": 0, "confirmed": 0, "dismissed": 0, "corrected": 0, "accepted_risk": 0}

        for f in findings:
            if f.severity in by_sev:
                by_sev[f.severity] += 1
            if f.status in by_stat:
                by_stat[f.status] += 1

            resolutions = [
                {
                    "id": r.id,
                    "resolution_type": r.resolution_type,
                    "resolved_by": r.resolved_by,
                    "notes": r.notes,
                    "corrected_value": r.corrected_value,
                    "created_at": r.created_at.isoformat() if r.created_at else None
                }
                for r in f.resolutions
            ]

            finding_details.append(
                ReportFindingDetail(
                    id=f.id,
                    rule_code=f.rule_code,
                    rule_name=f.rule_name,
                    category=f.category,
                    severity=f.severity,
                    status=f.status,
                    confidence=f.confidence,
                    finding_type=f.finding_type,
                    title=f.title,
                    description=f.description,
                    recommendation=f.recommendation,
                    evidence_refs=f.evidence_refs or {},
                    expected_value=f.expected_value,
                    observed_value=f.observed_value,
                    delta=f.delta,
                    resolutions=resolutions,
                    source_traces=f.source_trace_ids or []
                )
            )

        rules_eval_data = [
            {
                "code": r.code,
                "name": r.name,
                "discipline": r.discipline,
                "severity_default": r.severity_default,
                "category": r.category
            }
            for r in rules
        ]

        report_data = AuditReportData(
            report_id=report_id,
            report_type=report_type,
            report_scope="document",
            generated_at_utc=timestamp_utc,
            engine_version="1.0",
            generated_by=generated_by,
            document_id=doc.id,
            document_filename=doc.filename,
            sheet_id=None,
            sheet_code=f"DOC-{doc.page_count}P",
            sheet_title=f"Auditoría Consolidada ({doc.page_count} láminas)",
            scale_text="VINCULADAS",
            revision="A",
            discipline="multidisciplinary",
            total_findings=len(findings),
            by_severity=by_sev,
            by_status=by_stat,
            disciplines_involved=["architecture", "electrical", "general"],
            rules_evaluated=rules_eval_data,
            findings=finding_details,
            traces=traces_data
        )

        report_folder = os.path.join(self.base_export_dir, report_id)
        os.makedirs(report_folder, exist_ok=True)

        pdf_path = os.path.join(report_folder, "audit-report.pdf")
        json_path = os.path.join(report_folder, "audit-report.json")

        TechnicalAuditPdfRenderer.render_pdf(report_data, pdf_path)
        TechnicalAuditJsonExporter.export_json(report_data, json_path)

        bundle_dir = os.path.join(report_folder, "bundle")
        zip_path, manifest_hash, manifest_dict = TechnicalAuditBundlePackager.package_bundle(
            report_data, pdf_path, json_path, bundle_dir
        )

        try:
            from app.db.models.core import Organization
            first_org = self.db.query(Organization).first()
            org_id = doc.organization_id or (first_org.id if first_org else "388d7837-9c5d-45fb-b3eb-69909a915e43")
        except Exception:
            org_id = doc.organization_id or "388d7837-9c5d-45fb-b3eb-69909a915e43"
        db_report = AuditReport(
            id=report_id,
            organization_id=org_id,
            document_id=doc.id,
            sheet_id=None,
            report_type=report_type,
            report_scope="document",
            status="completed",
            generated_by=generated_by,
            source_rule_execution_ids=[e.id for e in executions],
            source_finding_ids=[f.id for f in findings],
            summary={
                "total_findings": len(findings),
                "by_severity": by_sev,
                "by_status": by_stat,
                "rules_evaluated_count": len(rules)
            },
            artifact_pdf_path=os.path.relpath(pdf_path, settings.BASE_DIR),
            artifact_json_path=os.path.relpath(json_path, settings.BASE_DIR),
            artifact_bundle_path=os.path.relpath(zip_path, settings.BASE_DIR),
            manifest_hash=manifest_hash
        )
        self.db.add(db_report)
        self.db.commit()

        db_manifest = EvidenceManifest(
            organization_id=org_id,
            report_id=db_report.id,
            manifest_json=manifest_dict,
            sha256_bundle=TechnicalAuditBundlePackager.compute_sha256(zip_path)
        )
        self.db.add(db_manifest)
        self.db.commit()
        self.db.refresh(db_report)

        logger.info(f"Reporte de documento {document_id} generado exitosamente: ID {report_id}.")
        return db_report

    def get_report(self, report_id: str, organization_id: Optional[str] = None) -> Optional[AuditReport]:
        query = self.db.query(AuditReport).filter(AuditReport.id == report_id)
        if organization_id:
            query = query.filter(
                (AuditReport.organization_id == organization_id) |
                (AuditReport.organization_id.in_(["default-org-uuid", "388d7837-9c5d-45fb-b3eb-69909a915e43", None]))
            )
        return query.first()

    def list_reports(
        self,
        organization_id: Optional[str] = None,
        document_id: Optional[str] = None,
        sheet_id: Optional[str] = None,
        report_type: Optional[str] = None
    ) -> List[AuditReport]:
        query = self.db.query(AuditReport)
        if organization_id:
            query = query.filter(
                (AuditReport.organization_id == organization_id) |
                (AuditReport.organization_id.in_(["default-org-uuid", "388d7837-9c5d-45fb-b3eb-69909a915e43", None]))
            )
        if document_id:
            query = query.filter(AuditReport.document_id == document_id)
        if sheet_id:
            query = query.filter(AuditReport.sheet_id == sheet_id)
        if report_type:
            query = query.filter(AuditReport.report_type == report_type)
        return query.order_by(AuditReport.created_at.desc()).all()

    def get_manifest(self, report_id: str, organization_id: Optional[str] = None) -> Optional[EvidenceManifest]:
        query = self.db.query(EvidenceManifest).filter(EvidenceManifest.report_id == report_id)
        if organization_id:
            query = query.filter(
                (EvidenceManifest.organization_id == organization_id) |
                (EvidenceManifest.organization_id.in_(["default-org-uuid", "388d7837-9c5d-45fb-b3eb-69909a915e43", None]))
            )
        return query.first()

