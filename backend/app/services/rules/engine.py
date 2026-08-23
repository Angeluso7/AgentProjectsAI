from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.db.models.document_memory import (
    Document, DocumentSheet, SheetRegion, TitleBlockExtraction,
    ExtractedText, ExtractedTable, ExtractedTableCell, DetectedSymbol
)
from app.db.models.normative_memory import NormativeCriterion
from app.db.models.decision_memory import (
    RuleDefinition, RuleExecution, RuleFinding, FindingResolution, FindingEvidence
)
from app.db.repositories.document_repository import DocumentRepository
from app.db.repositories.operations_repository import OperationsRepository
from app.services.rules.contracts import RuleInput, RuleResult
from app.services.rules.base import BaseRule
from app.services.rules.implementations import (
    DoorCountMatchRule,
    WindowCountMatchRule,
    TitleBlockRequiredFieldsRule,
    TitleBlockScaleValidRule,
    RequiredTablesRule,
    NormativeMinDoorWidthRule
)
from app.schemas.qa_rule import RuleEvaluationSummaryResponse
from app.core.logging import logger

class RuleRegistry:
    """Registro central de reglas determinísticas QA/QC."""
    _rules: Dict[str, BaseRule] = {}

    @classmethod
    def register_default_rules(cls) -> None:
        default_instances = [
            DoorCountMatchRule(),
            WindowCountMatchRule(),
            TitleBlockRequiredFieldsRule(),
            TitleBlockScaleValidRule(),
            RequiredTablesRule(),
            NormativeMinDoorWidthRule()
        ]
        for r in default_instances:
            cls._rules[r.code] = r

    @classmethod
    def get_rules(cls) -> List[BaseRule]:
        if not cls._rules:
            cls.register_default_rules()
        return list(cls._rules.values())

    @classmethod
    def get_rule(cls, code: str) -> Optional[BaseRule]:
        if not cls._rules:
            cls.register_default_rules()
        return cls._rules.get(code)

    @classmethod
    def seed_database_definitions(cls, db: Session) -> None:
        """Siembra y sincroniza las definiciones declarativas de reglas en la BD."""
        rules = cls.get_rules()
        for r in rules:
            existing = db.query(RuleDefinition).filter(RuleDefinition.code == r.code).first()
            if not existing:
                db_rule = RuleDefinition(
                    code=r.code,
                    name=r.name,
                    category=r.category,
                    discipline=r.discipline,
                    severity_default=r.severity_default,
                    description=r.description,
                    rule_logic_type=r.rule_logic_type,
                    version=r.version,
                    is_active=True
                )
                db.add(db_rule)
        db.commit()


class RuleEngine:
    """Motor de evaluación de reglas determinísticas y conciliación cruzada."""

    def __init__(self, db: Session):
        self.db = db
        self.doc_repo = DocumentRepository(db)
        self.ops_repo = OperationsRepository(db)
        RuleRegistry.register_default_rules()

    def evaluate_sheet(
        self,
        sheet_id: str,
        job_id: Optional[str] = None
    ) -> List[RuleFinding]:
        sheet = self.doc_repo.get_sheet_by_id(sheet_id)
        if not sheet:
            raise ValueError(f"Lámina '{sheet_id}' no encontrada.")

        # Recopilar todos los artefactos estructurados de la lámina
        tables = self.db.query(ExtractedTable).filter(ExtractedTable.sheet_id == sheet_id).all()
        cells_by_table: Dict[str, List[Any]] = {}
        for t in tables:
            cells_by_table[t.id] = self.db.query(ExtractedTableCell).filter(ExtractedTableCell.table_id == t.id).all()

        symbols = self.db.query(DetectedSymbol).filter(DetectedSymbol.sheet_id == sheet_id).all()
        texts = self.db.query(ExtractedText).filter(ExtractedText.sheet_id == sheet_id).all()
        regions = self.db.query(SheetRegion).filter(SheetRegion.sheet_id == sheet_id).all()
        tb = self.db.query(TitleBlockExtraction).filter(TitleBlockExtraction.sheet_id == sheet_id).first()
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

        RuleRegistry.seed_database_definitions(self.db)
        rules = RuleRegistry.get_rules()

        # Gatekeeper de Completitud Documental: Verificar si el proyecto tiene reglas bloqueadas
        blocked_rules_map: Dict[str, Dict[str, Any]] = {}
        if sheet.document and sheet.document.project_id:
            try:
                from app.services.completeness.service import CompletenessService
                comp_svc = CompletenessService(self.db)
                eval_data = comp_svc.evaluate_project_completeness(sheet.document.project_id)
                for br in eval_data.get("blocked_rules", []):
                    blocked_rules_map[br["rule_code"]] = br
            except Exception as e:
                logger.warning(f"No se pudo evaluar completitud previa en RuleEngine: {e}")

        generated_findings: List[RuleFinding] = []

        for rule in rules:
            rule_def = self.db.query(RuleDefinition).filter(RuleDefinition.code == rule.code).first()
            if not rule_def or not rule_def.is_active:
                continue

            # Si la regla está bloqueada preventivamente por el Gatekeeper de Completitud
            if rule.code in blocked_rules_map:
                block_info = blocked_rules_map[rule.code]
                verdict = "no_verificable"
                unverifiable_reason = "blocked_by_missing_doc"
                status = "insufficient_evidence"

                execution = RuleExecution(
                    job_id=job_id,
                    document_id=sheet.document_id,
                    sheet_id=sheet.id,
                    rule_id=rule_def.id,
                    rule_version=rule.version,
                    execution_status=status,
                    input_snapshot={"blocked": True, "deliverable_required": block_info.get("blocked_by_deliverable_title")},
                    result_summary={
                        "verdict": verdict,
                        "unverifiable_reason": unverifiable_reason,
                        "blocked_by": block_info.get("blocked_by_deliverable_title"),
                        "title": f"No Verificable: Falta {block_info.get('blocked_by_deliverable_title')}",
                        "severity": "medium",
                        "detail": block_info.get("detail")
                    },
                    confidence=1.0
                )
                self.db.add(execution)
                self.db.commit()

                doc = self.doc_repo.get_by_id(sheet.document_id)
                org_id = doc.organization_id if doc and doc.organization_id else "388d7837-9c5d-45fb-b3eb-69909a915e43"

                finding = RuleFinding(
                    organization_id=org_id,
                    document_id=sheet.document_id,
                    sheet_id=sheet.id,
                    rule_id=rule_def.id,
                    rule_code=rule.code,
                    rule_name=rule.name,
                    category=rule.category,
                    severity="medium",
                    status="open",
                    confidence=1.0,
                    finding_type="insufficient_evidence",
                    title=f"No Verificable: Bloqueado por falta de {block_info.get('blocked_by_deliverable_title')}",
                    description=block_info.get("detail", "Falta entregable requerido."),
                    recommendation=f"Cargar y validar el entregable «{block_info.get('blocked_by_deliverable_title')}» en estado 'Apto como Evidencia'.",
                    evidence_refs={
                        "verdict": verdict,
                        "unverifiable_reason": unverifiable_reason,
                        "blocked_by": block_info.get("blocked_by_deliverable_title"),
                        "deliverable_type": block_info.get("blocked_by_deliverable_type")
                    }
                )
                self.db.add(finding)
                self.db.commit()
                generated_findings.append(finding)
                continue

            result = rule.evaluate(inputs)

            # Mapeo a los 4 Veredictos Canónicos
            if result.status == "passed":
                verdict = "cumple"
                unverifiable_reason = None
            elif result.status == "failed":
                verdict = "no_cumple"
                unverifiable_reason = None
            elif result.status == "not_applicable":
                verdict = "no_aplica"
                unverifiable_reason = None
            else: # insufficient_evidence o warning
                verdict = "no_verificable"
                unverifiable_reason = "minor_missing" if result.status == "warning" else "insufficient_evidence"

            # Persistir ejecución de regla
            execution = RuleExecution(
                job_id=job_id,
                document_id=sheet.document_id,
                sheet_id=sheet.id,
                rule_id=rule_def.id,
                rule_version=rule.version,
                execution_status=result.status,
                input_snapshot={
                    "tables_count": len(tables),
                    "symbols_count": len(symbols),
                    "texts_count": len(texts),
                    "has_title_block": tb is not None
                },
                result_summary={
                    "verdict": verdict,
                    "unverifiable_reason": unverifiable_reason,
                    "title": result.title,
                    "severity": result.severity,
                    "delta": result.delta
                },
                confidence=result.confidence
            )
            self.db.add(execution)
            self.db.commit()

            # Registrar DecisionTrace
            trace_status = "auto_accepted" if result.status == "passed" else ("review_required" if result.requires_human_review else "flagged")
            trace = self.ops_repo.record_trace(
                trace_type="rule_evaluation",
                entity_type="RuleExecution",
                entity_id=execution.id,
                engine_name="RuleEngine",
                engine_version=rule.version,
                confidence=result.confidence,
                policy_id=rule_def.id if rule_def else None,
                policy_version=rule.version,
                decision_status=trace_status,
                explanation=f"{rule.code}: {result.title}. Status: {result.status}. {result.description}",
                document_id=sheet.document_id,
                sheet_id=sheet.id
            )

            # Si el resultado es failed, warning o insufficient_evidence relevante, generar Finding
            if result.status in ["failed", "warning", "insufficient_evidence"]:
                # Generar ReviewTask si aplica
                review_task_id = None
                if result.requires_human_review:
                    task = self.ops_repo.create_review_task(
                        task_type=result.review_task_type or "rule_finding_review",
                        reason_code=result.review_reason or f"RULE_{result.status.upper()}",
                        reason_message=f"{rule.name}: {result.description}",
                        confidence=result.confidence,
                        priority="high" if result.severity in ["critical", "high"] else "medium",
                        project_id=sheet.document.project_id if sheet.document else None,
                        document_id=sheet.document_id,
                        sheet_id=sheet.id,
                        evidence_refs=result.evidence_refs,
                        payload={
                            "rule_code": rule.code,
                            "rule_name": rule.name,
                            "severity": result.severity,
                            "expected_value": result.expected_value,
                            "observed_value": result.observed_value,
                            "delta": result.delta
                        }
                    )
                    review_task_id = task.id

                doc = self.doc_repo.get_by_id(sheet.document_id)
                org_id = doc.organization_id if doc and doc.organization_id else "388d7837-9c5d-45fb-b3eb-69909a915e43"

                finding = RuleFinding(
                    organization_id=org_id,
                    document_id=sheet.document_id,
                    sheet_id=sheet.id,
                    rule_id=rule_def.id,
                    rule_code=rule.code,
                    rule_name=rule.name,
                    category=rule.category,
                    severity=result.severity,
                    status="open",
                    confidence=result.confidence,
                    finding_type="normative_violation" if rule.category == "normative_compliance" else "reconciliation_mismatch",
                    title=result.title,
                    description=result.description,
                    recommendation=result.recommendation,
                    evidence_refs=result.evidence_refs,
                    expected_value=result.expected_value,
                    observed_value=result.observed_value,
                    delta=result.delta,
                    source_trace_ids=[trace.id],
                    review_task_id=review_task_id
                )
                self.db.add(finding)
                self.db.commit()
                self.db.refresh(finding)

                # Persistir enlaces de evidencia relacional
                for ev_type, ev_data in result.evidence_refs.items():
                    fe = FindingEvidence(
                        finding_id=finding.id,
                        evidence_type=ev_type,
                        description=f"Evidencia {ev_type} vinculada a la regla {rule.code}",
                        metadata_info=ev_data if isinstance(ev_data, dict) else {"value": ev_data}
                    )
                    self.db.add(fe)
                self.db.commit()

                generated_findings.append(finding)

        logger.info(f"Lámina {sheet_id}: {len(rules)} reglas evaluadas, {len(generated_findings)} hallazgos emitidos.")
        return generated_findings

    def evaluate_document(
        self,
        document_id: str,
        job_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        sheets = self.doc_repo.list_sheets_by_document(document_id)
        if not sheets:
            raise ValueError(f"El documento '{document_id}' no posee láminas.")

        results = []
        for s in sheets:
            findings = self.evaluate_sheet(sheet_id=s.id, job_id=job_id)
            results.append({
                "sheet_id": s.id,
                "sheet_number": s.sheet_number,
                "findings_count": len(findings),
                "findings": [f.id for f in findings]
            })
        return results

    def resolve_finding(self, finding_id: str, resolution_data: Dict[str, Any]) -> RuleFinding:
        finding = self.db.query(RuleFinding).filter(RuleFinding.id == finding_id).first()
        if not finding:
            raise ValueError(f"Hallazgo '{finding_id}' no encontrado.")

        res_type = resolution_data.get("resolution_type", "confirmed")
        finding.status = res_type

        res = FindingResolution(
            finding_id=finding.id,
            resolution_type=res_type,
            resolved_by=resolution_data.get("resolved_by", "auditor_qa"),
            notes=resolution_data.get("notes"),
            corrected_value=resolution_data.get("corrected_value")
        )
        self.db.add(res)
        self.db.commit()
        self.db.refresh(finding)

        # Si el finding tenía una ReviewTask asociada, resolverla también
        if finding.review_task_id:
            self.ops_repo.record_review_decision(
                task_id=finding.review_task_id,
                decision=res_type,
                original_value={"title": finding.title, "severity": finding.severity},
                corrected_value=resolution_data.get("corrected_value"),
                reviewer=resolution_data.get("resolved_by", "auditor_qa"),
                notes=resolution_data.get("notes")
            )

        return finding

    def get_finding(self, finding_id: str) -> Optional[RuleFinding]:
        return self.db.query(RuleFinding).filter(RuleFinding.id == finding_id).first()

    def list_findings(
        self,
        document_id: Optional[str] = None,
        sheet_id: Optional[str] = None,
        severity: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[RuleFinding]:
        query = self.db.query(RuleFinding)
        if document_id:
            query = query.filter(RuleFinding.document_id == document_id)
        if sheet_id:
            query = query.filter(RuleFinding.sheet_id == sheet_id)
        if severity:
            query = query.filter(RuleFinding.severity == severity)
        if status:
            query = query.filter(RuleFinding.status == status)
        return query.order_by(RuleFinding.created_at.desc()).all()

    def get_summary(
        self,
        document_id: Optional[str] = None,
        sheet_id: Optional[str] = None
    ) -> RuleEvaluationSummaryResponse:
        exec_query = self.db.query(RuleExecution)
        finding_query = self.db.query(RuleFinding)

        if document_id:
            exec_query = exec_query.filter(RuleExecution.document_id == document_id)
            finding_query = finding_query.filter(RuleFinding.document_id == document_id)
        if sheet_id:
            exec_query = exec_query.filter(RuleExecution.sheet_id == sheet_id)
            finding_query = finding_query.filter(RuleFinding.sheet_id == sheet_id)

        executions = exec_query.all()
        findings = finding_query.all()

        passed = len([e for e in executions if e.execution_status == "passed"])
        failed = len([e for e in executions if e.execution_status == "failed"])
        warning = len([e for e in executions if e.execution_status == "warning"])
        insufficient = len([e for e in executions if e.execution_status == "insufficient_evidence"])

        by_sev = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        for f in findings:
            if f.severity in by_sev:
                by_sev[f.severity] += 1

        return RuleEvaluationSummaryResponse(
            document_id=document_id,
            sheet_id=sheet_id,
            total_rules_evaluated=len(executions),
            passed_count=passed,
            failed_count=failed,
            warning_count=warning,
            insufficient_evidence_count=insufficient,
            findings_generated=len(findings),
            by_severity=by_sev
        )
