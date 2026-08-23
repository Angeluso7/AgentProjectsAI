import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.db.models.core import Project
from app.db.models.document_memory import Document, DocumentSheet
from app.db.models.decision_memory import RuleFinding, RuleDefinition, ReviewRun
from app.db.models.observations import AuditObservation, ObservationResponse
from app.db.models.completeness import DocumentDeliverable
from app.services.rules.engine import RuleEngine, RuleRegistry
from app.services.rules.contracts import RuleInput
from app.schemas.common import ObservationTypeEnum, ObservationStatusEnum
from app.core.logging import logger

DISCIPLINE_CODE_MAP = {
    "architecture": "ARQ",
    "structural": "EST",
    "electrical": "ELE",
    "plumbing": "SAN",
    "hvac": "CLI",
    "mechanical": "MEC",
    "fire_safety": "SEG",
    "fire_protection": "PCI",
    "general": "GEN"
}

PREFIX_TYPE_MAP = {
    "technical_observation": "OBS",
    "information_request": "RFI",
    "document_blocker": "BLK",
    "minor_missing": "MIN"
}

class ObservationService:
    """Motor de Gestión Formal de Observaciones Técnicas, RFIs y Re-ejecución Delta."""

    def __init__(self, db: Session):
        self.db = db

    def _generate_code(self, project_id: str, item_type: str, discipline: str) -> str:
        prefix = PREFIX_TYPE_MAP.get(item_type, "OBS")
        disc_code = DISCIPLINE_CODE_MAP.get(discipline.lower() if discipline else "general", "GEN")
        
        # Contar cuántos ítems existen para este proyecto y prefijo
        count = self.db.query(AuditObservation).filter(
            AuditObservation.project_id == project_id,
            AuditObservation.item_type == item_type
        ).count()
        
        return f"{prefix}-{disc_code}-{count + 1:03d}"

    def list_observations(
        self,
        project_id: Optional[str] = None,
        item_type: Optional[str] = None,
        discipline: Optional[str] = None,
        stage: Optional[str] = None,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[AuditObservation]:
        q = self.db.query(AuditObservation)
        if project_id:
            q = q.filter(AuditObservation.project_id == project_id)
        if item_type and item_type != "all":
            q = q.filter(AuditObservation.item_type == item_type)
        if discipline and discipline != "all":
            q = q.filter(AuditObservation.discipline == discipline)
        if stage and stage != "all":
            q = q.filter(AuditObservation.stage == stage)
        if status and status != "all":
            q = q.filter(AuditObservation.status == status)
        if severity and severity != "all":
            q = q.filter(AuditObservation.severity == severity)
        if search:
            pattern = f"%{search}%"
            q = q.filter(
                (AuditObservation.code.ilike(pattern)) |
                (AuditObservation.title.ilike(pattern)) |
                (AuditObservation.description.ilike(pattern))
            )
        return q.order_by(AuditObservation.created_at.desc()).all()

    def get_by_id(self, obs_id: str) -> Optional[AuditObservation]:
        return self.db.query(AuditObservation).filter(AuditObservation.id == obs_id).first()

    def generate_observations_from_findings(
        self,
        project_id: str,
        review_run_id: Optional[str] = None,
        stage_override: Optional[str] = None,
        author: str = "auditor_lead"
    ) -> List[AuditObservation]:
        """
        Genera objetos formales OBS / RFI / BLK / MIN aplicando las reglas de negocio
        diferenciadas a partir de los hallazgos de auditoría.
        """
        project = self.db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise ValueError(f"Proyecto '{project_id}' no encontrado.")

        stage = stage_override or (project.settings or {}).get("stage", "Ingeniería de Detalle")

        q = self.db.query(RuleFinding).join(Document, RuleFinding.document_id == Document.id).filter(
            Document.project_id == project_id
        )
        if review_run_id:
            q = q.filter(RuleFinding.review_run_id == review_run_id)

        findings = q.all()
        created_observations: List[AuditObservation] = []
        now = datetime.utcnow()

        for f in findings:
            # Verificar si ya existe una observación vinculada a este finding
            existing = self.db.query(AuditObservation).filter(AuditObservation.rule_finding_id == f.id).first()
            if existing:
                continue

            evidence_refs = f.evidence_refs or {}
            verdict = evidence_refs.get("verdict", "no_cumple")
            unverifiable_reason = evidence_refs.get("unverifiable_reason")
            deliverable_type = evidence_refs.get("deliverable_type")

            # Reglas de negocio para clasificación de ítems formales
            if verdict == "no_cumple":
                item_type = "technical_observation"
                obs_status = "issued" if f.severity in ["critical", "high"] else "draft"
                title = f"[OBS] {f.title}"
            elif verdict == "no_verificable":
                if unverifiable_reason == "blocked_by_missing_doc":
                    item_type = "document_blocker"
                    obs_status = "issued"
                    title = f"[BLK] Bloqueo Documental: Falta {evidence_refs.get('blocked_by', 'Entregable Obligatorio')}"
                elif unverifiable_reason == "insufficient_evidence":
                    item_type = "information_request"
                    obs_status = "issued"
                    title = f"[RFI] Solicitud de Aclaración: {f.title}"
                else: # minor_missing
                    item_type = "minor_missing"
                    obs_status = "draft"
                    title = f"[MIN] Advertencia: {f.title}"
            else:
                continue # CUMPLE o NO_APLICA no generan observaciones

            disc = (f.sheet.discipline if f.sheet and hasattr(f.sheet, "discipline") and f.sheet.discipline else None) or (project.discipline or "general")
            code = self._generate_code(project_id, item_type, disc)

            obs = AuditObservation(
                organization_id=f.organization_id or project.organization_id,
                project_id=project_id,
                stage=stage,
                code=code,
                item_type=item_type,
                title=title,
                description=f.description,
                recommendation=f.recommendation,
                discipline=disc,
                severity=f.severity or "medium",
                status=obs_status,
                rule_finding_id=f.id,
                rule_id=f.rule_id,
                rule_code=f.rule_code,
                document_id=f.document_id,
                sheet_id=f.sheet_id,
                review_run_id=f.review_run_id,
                required_deliverable_type=deliverable_type,
                issued_by=author,
                issued_at=now if obs_status == "issued" else None,
                history_trace=[{
                    "from_status": None,
                    "to_status": obs_status,
                    "action": "generated_from_finding",
                    "author": author,
                    "notes": f"Generado automáticamente desde regla {f.rule_code} con veredicto {verdict.upper()}",
                    "timestamp": now.isoformat()
                }]
            )
            self.db.add(obs)
            self.db.commit()
            self.db.refresh(obs)
            created_observations.append(obs)

        return created_observations

    def issue_observation(self, obs_id: str, assigned_to: Optional[str] = None, author: str = "auditor_lead", notes: Optional[str] = None) -> AuditObservation:
        obs = self.get_by_id(obs_id)
        if not obs:
            raise ValueError(f"Observación '{obs_id}' no encontrada.")

        now = datetime.utcnow()
        prev_status = obs.status
        obs.status = "issued"
        obs.issued_at = now
        if assigned_to:
            obs.assigned_to = assigned_to

        trace_list = list(obs.history_trace or [])
        trace_list.append({
            "from_status": prev_status,
            "to_status": "issued",
            "action": "issue_formal",
            "author": author,
            "notes": notes or f"Emitido formalmente a {assigned_to or 'contratista/proyectista'}",
            "timestamp": now.isoformat()
        })
        obs.history_trace = trace_list

        self.db.commit()
        self.db.refresh(obs)
        return obs

    def submit_response(
        self,
        obs_id: str,
        response_text: str,
        author: str = "contractor",
        author_role: str = "contractor",
        attached_document_id: Optional[str] = None
    ) -> AuditObservation:
        obs = self.get_by_id(obs_id)
        if not obs:
            raise ValueError(f"Observación '{obs_id}' no encontrada.")

        now = datetime.utcnow()
        resp = ObservationResponse(
            observation_id=obs.id,
            author=author,
            author_role=author_role,
            response_text=response_text,
            attached_document_id=attached_document_id,
            created_at=now
        )
        self.db.add(resp)

        prev_status = obs.status
        obs.status = "answered"
        obs.answered_at = now

        trace_list = list(obs.history_trace or [])
        trace_list.append({
            "from_status": prev_status,
            "to_status": "answered",
            "action": "contractor_response",
            "author": author,
            "notes": response_text[:120] + ("..." if len(response_text) > 120 else ""),
            "timestamp": now.isoformat()
        })
        obs.history_trace = trace_list

        self.db.commit()
        self.db.refresh(obs)
        return obs

    def provision_evidence(
        self,
        obs_id: str,
        document_id: str,
        author: str = "auditor_lead",
        notes: Optional[str] = None
    ) -> AuditObservation:
        """
        Vincula un documento nuevo o nueva versión como evidencia provisionada
        y promueve su idoneidad a 'eligible_as_evidence'.
        """
        obs = self.get_by_id(obs_id)
        if not obs:
            raise ValueError(f"Observación '{obs_id}' no encontrada.")

        doc = self.db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            raise ValueError(f"Documento '{document_id}' no encontrado.")

        now = datetime.utcnow()
        prev_status = obs.status
        obs.provisioned_document_id = document_id
        obs.status = "provisioned"
        obs.provisioned_at = now

        # Promover el entregable de ese documento si aplica
        deliv = self.db.query(DocumentDeliverable).filter(DocumentDeliverable.document_id == document_id).first()
        if not deliv and obs.required_deliverable_type:
            deliv = DocumentDeliverable(
                project_id=obs.project_id,
                document_id=document_id,
                deliverable_type=obs.required_deliverable_type,
                readiness_status="eligible_as_evidence",
                validation_notes=f"Provisionado para subsanar {obs.code}",
                classified_by=author,
                validated_at=now
            )
            self.db.add(deliv)
        elif deliv:
            deliv.readiness_status = "eligible_as_evidence"
            deliv.validated_at = now

        trace_list = list(obs.history_trace or [])
        trace_list.append({
            "from_status": prev_status,
            "to_status": "provisioned",
            "action": "provision_evidence",
            "author": author,
            "notes": notes or f"Evidencia provisionada: {doc.filename}",
            "provisioned_document_id": document_id,
            "provisioned_filename": doc.filename,
            "timestamp": now.isoformat()
        })
        obs.history_trace = trace_list

        self.db.commit()
        self.db.refresh(obs)
        return obs

    def execute_delta_reevaluation(self, obs_id: str, author: str = "auditor_lead") -> Dict[str, Any]:
        """
        Ejecuta la revisión incremental focalizada:
        Re-evalúa exclusivamente la regla y láminas afectadas por la evidencia provisionada.
        """
        obs = self.get_by_id(obs_id)
        if not obs:
            raise ValueError(f"Observación '{obs_id}' no encontrada.")

        rule_code = obs.rule_code
        if not rule_code:
            raise ValueError(f"La observación '{obs.code}' no tiene regla asociada para re-evaluación delta.")

        # Determinar lámina objetivo para la re-evaluación delta
        target_sheet_id = obs.sheet_id
        if not target_sheet_id:
            # Buscar primera lámina del documento original o provisionado
            doc_id = obs.document_id or obs.provisioned_document_id
            if doc_id:
                sheet = self.db.query(DocumentSheet).filter(DocumentSheet.document_id == doc_id).first()
                if sheet:
                    target_sheet_id = sheet.id

        if not target_sheet_id:
            raise ValueError("No se encontró lámina técnica para ejecutar la re-evaluación delta.")

        # Instanciar RuleEngine y buscar la regla específica
        RuleRegistry.seed_database_definitions(self.db)
        rule_instance = RuleRegistry.get_rule(rule_code)
        if not rule_instance:
            raise ValueError(f"Regla '{rule_code}' no encontrada en el registro de reglas.")

        sheet = self.db.query(DocumentSheet).filter(DocumentSheet.id == target_sheet_id).first()
        from app.db.models.document_memory import ExtractedTable, ExtractedTableCell, DetectedSymbol, ExtractedText, SheetRegion, TitleBlockExtraction
        from app.db.models.normative_memory import NormativeCriterion

        tables = self.db.query(ExtractedTable).filter(ExtractedTable.sheet_id == target_sheet_id).all()
        cells_by_table: Dict[str, List[Any]] = {}
        for t in tables:
            cells_by_table[t.id] = self.db.query(ExtractedTableCell).filter(ExtractedTableCell.table_id == t.id).all()

        symbols = self.db.query(DetectedSymbol).filter(DetectedSymbol.sheet_id == target_sheet_id).all()
        texts = self.db.query(ExtractedText).filter(ExtractedText.sheet_id == target_sheet_id).all()
        regions = self.db.query(SheetRegion).filter(SheetRegion.sheet_id == target_sheet_id).all()
        tb = self.db.query(TitleBlockExtraction).filter(TitleBlockExtraction.sheet_id == target_sheet_id).first()
        normative_criteria = self.db.query(NormativeCriterion).all()

        inputs = RuleInput(
            document_id=sheet.document_id,
            sheet_id=sheet.id,
            document=sheet.document,
            sheet=sheet,
            title_block=tb,
            tables=tables,
            cells_by_table=cells_by_table,
            symbols=symbols,
            texts=texts,
            regions=regions,
            normative_criteria=normative_criteria
        )

        rule_result = rule_instance.evaluate(inputs)
        now = datetime.utcnow()
        prev_status = obs.status

        # Determinar si el delta resuelve la observación
        is_resolved = rule_result.status == "passed"
        if is_resolved:
            status_after = "closed"
            obs.status = "closed"
            obs.closed_at = now
            obs.resolution_notes = f"Resuelto satisfactoriamente tras re-evaluación delta de regla {rule_code}."

            # Actualizar finding origen a resolved
            if obs.rule_finding_id:
                finding = self.db.query(RuleFinding).filter(RuleFinding.id == obs.rule_finding_id).first()
                if finding:
                    finding.status = "resolved"
        else:
            status_after = "answered" if obs.responses else "issued"
            obs.status = status_after
            obs.resolution_notes = f"Re-evaluación delta persistió discrepancia: {rule_result.description}"

        trace_entry = {
            "from_status": prev_status,
            "to_status": status_after,
            "action": "delta_reevaluation",
            "author": author,
            "is_resolved": is_resolved,
            "rule_code": rule_code,
            "rule_status": rule_result.status,
            "verdict_after": "cumple" if is_resolved else ("no_cumple" if rule_result.status == "failed" else "no_verificable"),
            "notes": f"Re-ejecución delta sobre lámina {sheet.sheet_code or sheet.sheet_number}. Resultado: {rule_result.title}.",
            "timestamp": now.isoformat()
        }

        trace_list = list(obs.history_trace or [])
        trace_list.append(trace_entry)
        obs.history_trace = trace_list

        self.db.commit()
        self.db.refresh(obs)

        return {
            "observation_id": obs.id,
            "code": obs.code,
            "status_before": prev_status,
            "status_after": status_after,
            "verdict_after": "cumple" if is_resolved else ("no_cumple" if rule_result.status == "failed" else "no_verificable"),
            "is_resolved": is_resolved,
            "affected_rules_evaluated": [rule_code],
            "affected_sheets_evaluated": [sheet.sheet_code or f"Lámina {sheet.sheet_number}"],
            "message": f"Re-evaluación delta ejecutada exitosamente. Veredicto: {'CUMPLE' if is_resolved else 'NO_CUMPLE / NO_VERIFICABLE'}.",
            "trace_entry": trace_entry
        }

    def reopen_observation(self, obs_id: str, author: str = "auditor_lead", reason: Optional[str] = None) -> AuditObservation:
        """
        Reabre formalmente una observación cerrada o validada ante nueva evidencia contradictoria
        o requerimiento de auditoría.
        """
        obs = self.get_by_id(obs_id)
        if not obs:
            raise ValueError(f"Observación '{obs_id}' no encontrada.")

        prev_status = obs.status
        now = datetime.utcnow()
        obs.status = "issued"
        obs.closed_at = None
        obs.resolution_notes = None

        if obs.rule_finding_id:
            finding = self.db.query(RuleFinding).filter(RuleFinding.id == obs.rule_finding_id).first()
            if finding:
                finding.status = "open"

        trace_list = list(obs.history_trace or [])
        trace_list.append({
            "from_status": prev_status,
            "to_status": "issued",
            "action": "reopen_observation",
            "author": author,
            "notes": reason or "Reapertura formal por nueva evidencia contradictoria o revisión de auditoría.",
            "timestamp": now.isoformat()
        })
        obs.history_trace = trace_list

        self.db.commit()
        self.db.refresh(obs)
        return obs
