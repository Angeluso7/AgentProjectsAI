import os
import json
import hashlib
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.db.models.core import Project
from app.db.models.document_memory import Document
from app.db.models.decision_memory import RuleFinding, RuleDefinition
from app.db.models.observations import AuditObservation
from app.db.models.reporting import ProjectStageReportSnapshot
from app.services.completeness.service import CompletenessService
from app.services.reporting.consolidated_pdf_renderer import ConsolidatedStagePdfRenderer
from app.core.config import settings
from app.core.logging import logger

class ConsolidatedReportService:
    """Servicio orquestador del Reporte Consolidado Final por Etapa y Snapshots Inmutables."""

    def __init__(self, db: Session):
        self.db = db
        self.completeness_service = CompletenessService(db)
        self.reports_dir = os.path.join(settings.DATA_DIR, "reports")
        os.makedirs(self.reports_dir, exist_ok=True)

    def build_consolidated_data(self, project_id: str, stage_override: Optional[str] = None) -> Dict[str, Any]:
        """
        Calcula y unifica el estado completo del proyecto en la etapa activa:
        completitud, gatekeeper, 4 veredictos de auditoría, observaciones/RFIs y evolución delta.
        """
        project = self.db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise ValueError(f"Proyecto '{project_id}' no encontrado.")

        stage = stage_override or (project.settings or {}).get("stage", "Ingeniería de Detalle")

        # 1. Completitud Documental y Gatekeeper
        completeness_eval = self.completeness_service.evaluate_project_completeness(project_id, stage)
        comp_summary = {
            "completeness_percentage": completeness_eval["completeness_percentage"],
            "is_gate_passed": completeness_eval["is_gate_passed"],
            "total_required_count": completeness_eval["total_required_count"],
            "eligible_count": completeness_eval["eligible_count"],
            "missing_mandatory_count": completeness_eval["missing_mandatory_count"],
            "missing_optional_count": completeness_eval["missing_optional_count"],
            "blocked_rules_count": completeness_eval["blocked_rules_count"],
            "deliverables_matrix": [
                {
                    "requirement_id": m["requirement"]["id"],
                    "title": m["requirement"]["title"],
                    "deliverable_type": m["requirement"]["deliverable_type"],
                    "is_mandatory": m["requirement"]["is_mandatory"],
                    "readiness_status": m["status"],
                    "provided_files_count": len(m.get("provided_documents", [])),
                    "is_fulfilled": m["is_fulfilled"],
                    "blocked_rule_codes": m["requirement"].get("blocked_rule_codes", [])
                }
                for m in completeness_eval.get("deliverables_matrix", [])
            ],
            "missing_deliverables": completeness_eval.get("missing_deliverables", []),
            "blocked_rules": completeness_eval.get("blocked_rules", [])
        }

        # 2. Resultados de Auditoría Técnica & 4 Veredictos
        findings_query = self.db.query(RuleFinding).join(
            Document, RuleFinding.document_id == Document.id
        ).filter(Document.project_id == project_id).all()

        verdicts_breakdown = {
            "cumple_count": 0,
            "no_cumple_count": 0,
            "no_verificable_count": 0,
            "no_aplica_count": 0,
            "total_rules_evaluated": len(findings_query),
            "by_discipline": {},
            "verdicts_list": []
        }

        for f in findings_query:
            ev = f.evidence_refs or {}
            verdict = ev.get("verdict", "no_cumple")
            unverifiable_reason = ev.get("unverifiable_reason")

            if verdict == "cumple":
                verdicts_breakdown["cumple_count"] += 1
            elif verdict == "no_cumple":
                verdicts_breakdown["no_cumple_count"] += 1
            elif verdict == "no_verificable":
                verdicts_breakdown["no_verificable_count"] += 1
            elif verdict == "no_aplica":
                verdicts_breakdown["no_aplica_count"] += 1

            disc = (f.document.discipline if f.document and hasattr(f.document, "discipline") else None) or (project.discipline or "general")
            if disc not in verdicts_breakdown["by_discipline"]:
                verdicts_breakdown["by_discipline"][disc] = {"cumple": 0, "no_cumple": 0, "no_verificable": 0, "no_aplica": 0}
            if verdict in verdicts_breakdown["by_discipline"][disc]:
                verdicts_breakdown["by_discipline"][disc][verdict] += 1

            verdicts_breakdown["verdicts_list"].append({
                "rule_code": f.rule_code,
                "rule_name": f.rule_name,
                "category": f.category,
                "discipline": disc,
                "verdict": verdict,
                "unverifiable_reason": unverifiable_reason,
                "findings_count": 1,
                "sheet_code": f.sheet.sheet_code if f.sheet else None,
                "document_filename": f.document.filename if f.document else None
            })

        # 3. Observaciones Formales, RFIs, Bloqueos y Faltantes
        obs_query = self.db.query(AuditObservation).filter(
            AuditObservation.project_id == project_id,
            AuditObservation.stage == stage
        ).all()

        obs_summary = {
            "total_obs": 0,
            "open_obs": 0,
            "closed_obs": 0,
            "critical_obs": 0,
            "high_obs": 0,
            "medium_obs": 0,
            "low_obs": 0,
            "total_rfi": 0,
            "open_rfi": 0,
            "answered_rfi": 0,
            "closed_rfi": 0,
            "total_blk": 0,
            "active_blk": 0,
            "resolved_blk": 0,
            "total_min": 0,
            "items": []
        }

        for o in obs_query:
            is_closed = o.status in ["closed", "validated"]
            if o.item_type == "technical_observation":
                obs_summary["total_obs"] += 1
                if is_closed:
                    obs_summary["closed_obs"] += 1
                else:
                    obs_summary["open_obs"] += 1
                    if o.severity == "critical":
                        obs_summary["critical_obs"] += 1
                    elif o.severity == "high":
                        obs_summary["high_obs"] += 1
                    elif o.severity == "medium":
                        obs_summary["medium_obs"] += 1
                    else:
                        obs_summary["low_obs"] += 1
            elif o.item_type == "information_request":
                obs_summary["total_rfi"] += 1
                if is_closed:
                    obs_summary["closed_rfi"] += 1
                elif o.status == "answered":
                    obs_summary["answered_rfi"] += 1
                else:
                    obs_summary["open_rfi"] += 1
            elif o.item_type == "document_blocker":
                obs_summary["total_blk"] += 1
                if is_closed:
                    obs_summary["resolved_blk"] += 1
                else:
                    obs_summary["active_blk"] += 1
            elif o.item_type == "minor_missing":
                obs_summary["total_min"] += 1

            prov_fn = o.provisioned_document.filename if o.provisioned_document else None
            doc_fn = o.document.filename if o.document else None

            obs_summary["items"].append({
                "id": o.id,
                "code": o.code,
                "item_type": o.item_type,
                "title": o.title,
                "discipline": o.discipline,
                "severity": o.severity,
                "status": o.status,
                "rule_code": o.rule_code,
                "document_filename": doc_fn,
                "provisioned_filename": prov_fn,
                "responses_count": len(o.responses or [])
            })

        # 4. Derivación Determinística del Veredicto Global de la Etapa
        has_mandatory_missing = comp_summary["missing_mandatory_count"] > 0
        has_active_blockers = comp_summary["blocked_rules_count"] > 0 or obs_summary["active_blk"] > 0
        is_gate_open = comp_summary["is_gate_passed"]
        has_critical_or_high_obs = (obs_summary["critical_obs"] + obs_summary["high_obs"]) > 0

        if not is_gate_open or has_mandatory_missing or has_active_blockers or has_critical_or_high_obs:
            global_verdict = "no_aprobable_bloqueada"
            verdict_rationale = (
                f"La etapa NO ES APROBABLE porque presenta {comp_summary['blocked_rules_count']} reglas bloqueadas "
                f"preventivamente, {comp_summary['missing_mandatory_count']} entregables obligatorios faltantes "
                f"y {obs_summary['critical_obs'] + obs_summary['high_obs']} observaciones técnicas críticas/altas abiertas."
            )
        elif comp_summary["completeness_percentage"] < 100.0 or obs_summary["open_rfi"] > 0 or verdicts_breakdown["no_verificable_count"] > 0:
            global_verdict = "parcial_incompleta"
            verdict_rationale = (
                f"La etapa se encuentra en REVISIÓN PARCIAL con {comp_summary['completeness_percentage']:.1f}% de completitud. "
                f"Existen {obs_summary['open_rfi']} solicitudes de información (RFIs) o entregables opcionales pendientes de resolución."
            )
        elif verdicts_breakdown["no_cumple_count"] > 0 or obs_summary["total_min"] > 0 or obs_summary["open_obs"] > 0:
            global_verdict = "aprobable_con_observaciones"
            verdict_rationale = (
                f"La etapa es APROBABLE CON OBSERVACIONES: El Gatekeeper fue superado al 100% de completitud, "
                f"manteniendo {obs_summary['open_obs']} observaciones o discrepancias técnicas menores subsanables sin riesgo estructural."
            )
        else:
            global_verdict = "aprobable"
            verdict_rationale = (
                "La etapa es APROBABLE TOTALMENTE: Todos los entregables obligatorios y opcionales han sido verificados, "
                "el Gatekeeper documental está conforme y todas las reglas técnicas de auditoría se encuentran aprobadas (CUMPLE)."
            )

        # 5. Evolución Delta respecto a la última revisión emitida (Snapshot previo)
        prev_snapshot = self.db.query(ProjectStageReportSnapshot).filter(
            ProjectStageReportSnapshot.project_id == project_id,
            ProjectStageReportSnapshot.stage == stage
        ).order_by(ProjectStageReportSnapshot.revision_number.desc()).first()

        delta_summary = {
            "previous_snapshot_id": prev_snapshot.id if prev_snapshot else None,
            "previous_revision_number": prev_snapshot.revision_number if prev_snapshot else None,
            "resolved_since_last_rev": [],
            "new_since_last_rev": [],
            "unblocked_rules_since_last_rev": [],
            "status_changes": [],
            "summary_narrative": "Primera emisión de revisión técnica para esta etapa." if not prev_snapshot else ""
        }

        if prev_snapshot:
            prev_obs = prev_snapshot.observations_summary.get("items", [])
            prev_obs_map = {item["id"]: item for item in prev_obs}
            curr_obs_map = {item["id"]: item for item in obs_summary["items"]}

            # Detectar resueltos y cambios de estado
            for obs_id, curr_item in curr_obs_map.items():
                if obs_id in prev_obs_map:
                    prev_item = prev_obs_map[obs_id]
                    if prev_item["status"] != curr_item["status"]:
                        delta_summary["status_changes"].append({
                            "id": obs_id,
                            "code": curr_item["code"],
                            "from": prev_item["status"],
                            "to": curr_item["status"],
                            "notes": f"Cambio de estado: {prev_item['status']} → {curr_item['status']}"
                        })
                        if curr_item["status"] in ["closed", "validated"] and prev_item["status"] not in ["closed", "validated"]:
                            delta_summary["resolved_since_last_rev"].append(curr_item)
                else:
                    delta_summary["new_since_last_rev"].append(curr_item)

            # Detectar reglas desbloqueadas
            prev_blocked = {b.get("rule_code") if isinstance(b, dict) else str(b) for b in prev_snapshot.completeness_summary.get("blocked_rules", [])}
            curr_blocked = {b.get("rule_code") if isinstance(b, dict) else str(b) for b in comp_summary.get("blocked_rules", [])}
            unblocked = prev_blocked - curr_blocked
            delta_summary["unblocked_rules_since_last_rev"] = list(unblocked)

            resolved_count = len(delta_summary["resolved_since_last_rev"])
            new_count = len(delta_summary["new_since_last_rev"])
            delta_summary["summary_narrative"] = (
                f"Respecto a Rev {prev_snapshot.revision_number}: Se resolvieron {resolved_count} hallazgos, "
                f"se incorporaron {new_count} nuevas observaciones y se desbloquearon {len(unblocked)} reglas técnicas."
            )

        return {
            "project_id": project.id,
            "project_name": project.name,
            "project_code": project.code,
            "stage": stage,
            "revision_number": (prev_snapshot.revision_number + 1) if prev_snapshot else 1,
            "title": f"Reporte Consolidado de Auditoría — {stage} ({project.code})",
            "global_stage_verdict": global_verdict,
            "verdict_rationale": verdict_rationale,
            "issued_by": "auditor_lead",
            "issued_at": datetime.utcnow().isoformat(),
            "completeness": comp_summary,
            "audit_verdicts": verdicts_breakdown,
            "observations": obs_summary,
            "delta_evolution": delta_summary,
            "is_live_preview": True
        }

    def emit_stage_snapshot(
        self,
        project_id: str,
        stage_override: Optional[str] = None,
        title_override: Optional[str] = None,
        notes: Optional[str] = None,
        author: str = "auditor_lead"
    ) -> ProjectStageReportSnapshot:
        """
        Genera, exporta en JSON/PDF y persiste un Snapshot inmutable de cierre de etapa.
        """
        data = self.build_consolidated_data(project_id, stage_override)
        project = self.db.query(Project).filter(Project.id == project_id).first()

        rev_num = data["revision_number"]
        stage = data["stage"]
        report_title = title_override or f"Reporte Consolidado Final Rev {rev_num} — {stage}"

        snapshot_id = str(uuid.uuid4())
        safe_stage = stage.replace(" ", "_").lower()
        safe_code = project.code.replace(" ", "_")

        # 1. Exportar JSON estructurado
        json_filename = f"auditoria_consolidada_{safe_code}_{safe_stage}_rev{rev_num}_{snapshot_id[:8]}.json"
        json_path = os.path.join(self.reports_dir, json_filename)

        export_payload = dict(data)
        export_payload["snapshot_id"] = snapshot_id
        export_payload["is_live_preview"] = False
        export_payload["issued_by"] = author
        export_payload["emission_notes"] = notes

        json_bytes = json.dumps(export_payload, indent=2, ensure_ascii=False).encode("utf-8")
        with open(json_path, "wb") as f:
            f.write(json_bytes)

        manifest_hash = hashlib.sha256(json_bytes).hexdigest()
        export_payload["manifest_hash"] = manifest_hash

        # 2. Generar PDF Vectorial con SimplePdfCanvas
        pdf_filename = f"auditoria_consolidada_{safe_code}_{safe_stage}_rev{rev_num}_{snapshot_id[:8]}.pdf"
        pdf_path = os.path.join(self.reports_dir, pdf_filename)
        try:
            ConsolidatedStagePdfRenderer.render_report(export_payload, pdf_path)
        except Exception as e:
            logger.error(f"Error generando PDF de reporte consolidado: {e}")
            pdf_path = None

        # 3. Persistir Snapshot Inmutable en Base de Datos
        now = datetime.utcnow()
        snapshot = ProjectStageReportSnapshot(
            id=snapshot_id,
            organization_id=project.organization_id,
            project_id=project_id,
            stage=stage,
            revision_number=rev_num,
            title=report_title,
            global_stage_verdict=data["global_stage_verdict"],
            verdict_rationale=data["verdict_rationale"],
            completeness_summary=data["completeness"],
            audit_verdicts_summary=data["audit_verdicts"],
            observations_summary=data["observations"],
            delta_evolution_summary=data["delta_evolution"],
            artifact_pdf_path=pdf_path,
            artifact_json_path=json_path,
            manifest_hash=manifest_hash,
            issued_by=author,
            created_at=now,
            updated_at=now
        )
        self.db.add(snapshot)
        self.db.commit()
        self.db.refresh(snapshot)

        return snapshot

    def list_snapshots(self, project_id: str, stage: Optional[str] = None) -> List[ProjectStageReportSnapshot]:
        q = self.db.query(ProjectStageReportSnapshot).filter(ProjectStageReportSnapshot.project_id == project_id)
        if stage and stage != "all":
            q = q.filter(ProjectStageReportSnapshot.stage == stage)
        return q.order_by(ProjectStageReportSnapshot.revision_number.desc()).all()

    def get_snapshot_by_id(self, snapshot_id: str) -> Optional[ProjectStageReportSnapshot]:
        return self.db.query(ProjectStageReportSnapshot).filter(ProjectStageReportSnapshot.id == snapshot_id).first()
