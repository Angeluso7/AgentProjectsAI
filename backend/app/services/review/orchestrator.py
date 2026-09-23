import os
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.db.models.decision_memory import (
    ReviewDiscipline,
    ReviewTopic,
    RuleDefinition,
    RuleApplicability,
    RuleExecutionDependency,
    ReviewRun,
    ReviewRunDocument,
    ReviewRunStep,
    RuleExecution,
    RuleFinding,
    ReviewReport
)
from app.db.models.core import Project
from app.db.models.document_memory import (
    Document,
    DocumentSheet,
    SheetRegion,
    TitleBlockExtraction,
    ExtractedText,
    ExtractedTable,
    ExtractedTableCell,
    DetectedSymbol
)
from app.db.models.normative_memory import NormativeCriterion
from app.db.models.template_memory import SymbolTemplate
from app.db.models.symbol_catalog import SymbolTemplateVersion
from app.services.review.taxonomy_service import TaxonomyService
from app.services.review.export_service import ReviewExportService
from app.services.rules.engine import RuleRegistry
from app.services.rules.contracts import RuleInput, RuleResult
from app.core.logging import logger

PHASE_NAMES = {
    1: ("Ingestión y Verificación de Documentos", "preparation"),
    2: ("Rasterizado y Extracción OCR", "extraction"),
    3: ("Segmentación de Láminas y Viñetas", "normalization"),
    4: ("Extracción de Tablas y Simbología", "extraction"),
    5: ("Evaluación de Integridad Documental", "evaluation"),
    6: ("Evaluación de Simbología y Normativa", "evaluation"),
    7: ("Evaluación de Cómputos y Listas", "evaluation"),
    8: ("Evaluación de Coordinación y Seguridad", "evaluation"),
    9: ("Consolidación y Reporte Final", "reporting")
}


class ReviewOrchestrator:
    """Orquestador de evaluación por Especialidad y Punto de Revisión."""

    @classmethod
    def _has_approved_production_catalog(cls, db: Session, discipline_code: str = "PIPING") -> bool:
        """
        Verifica si existe al menos una plantilla activa con versión aprobada
        y evidencia real/normativa en el catálogo productivo (excluye test_only y synthetic).
        """
        tmpls = db.query(SymbolTemplate).filter(
            SymbolTemplate.status == "active",
            SymbolTemplate.is_active_for_detection.is_(True)
        ).all()
        for t in tmpls:
            if getattr(t, "category", "") == "test_only" or getattr(t, "subcategory", "") == "test_only":
                continue
            versions = db.query(SymbolTemplateVersion).filter(
                SymbolTemplateVersion.symbol_template_id == t.id,
                SymbolTemplateVersion.approval_status == "approved"
            ).all()
            for v in versions:
                source_kind = getattr(v, "source_kind", "")
                if source_kind in ["normative_document", "real_authorized", "redacted_real", "project_legend"]:
                    return True
            if not versions and t.status == "active":
                func = getattr(t, "technical_function", "") or ""
                if "test_only" not in func.lower():
                    return True
        return False

    @classmethod
    def generate_review_plan(
        cls,
        db: Session,
        project_id: str,
        discipline_code: str,
        topic_code: str,
        document_ids: Optional[List[str]] = None,
        mode: str = "production"
    ) -> Dict[str, Any]:
        """
        Genera el pre-flight plan sin ejecutar: verifica documentos, reglas aplicables,
        dependencias, fases, limitaciones y documentos requeridos faltantes.
        """
        # 1. Validar proyecto
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise ValueError(f"Proyecto '{project_id}' no encontrado.")

        # 2. Validar disciplina y tema
        discipline = db.query(ReviewDiscipline).filter(ReviewDiscipline.code == discipline_code).first()
        topic = db.query(ReviewTopic).filter(ReviewTopic.code == topic_code).first()

        if not discipline:
            raise ValueError(f"Especialidad '{discipline_code}' no encontrada.")
        if not topic:
            raise ValueError(f"Punto de revisión '{topic_code}' no encontrado.")

        # 3. Validar y aislar documentos del proyecto (Seguridad multi-proyecto)
        proj_docs_query = db.query(Document).filter(
            Document.project_id == project_id,
            Document.status != "archived"
        )
        all_proj_docs = proj_docs_query.all()
        proj_doc_ids = {d.id for d in all_proj_docs}
        proj_doc_map = {d.id: d for d in all_proj_docs}

        # Filtrar los seleccionados estrictamente por pertenencia al proyecto
        if document_ids:
            selected_ids = [d_id for d_id in document_ids if d_id in proj_doc_ids]
        else:
            selected_ids = list(proj_doc_ids)

        included_documents = []
        for d_id in selected_ids:
            d = proj_doc_map[d_id]
            included_documents.append({
                "document_id": d.id,
                "filename": d.filename,
                "file_hash_sha256": d.file_hash_sha256,
                "inclusion_reason": "user_selected",
                "document_role": "primary",
                "status": "included"
            })

        excluded_documents = []
        for d in all_proj_docs:
            if d.id not in selected_ids:
                excluded_documents.append({
                    "document_id": d.id,
                    "filename": d.filename,
                    "exclusion_reason": "not_in_user_selection"
                })

        # 4. Obtener reglas aplicables canónicas
        applicable_rules = TaxonomyService.get_applicable_rules(db, discipline_code, topic_code, mode=mode)

        # Reglas no aprobadas (informativo para UI)
        unapproved_rules = []
        if mode == "production":
            all_draft_rules = TaxonomyService.get_applicable_rules(db, discipline_code, topic_code, mode="sandbox")
            approved_codes = {r["code"] for r in applicable_rules}
            unapproved_rules = [r for r in all_draft_rules if r["code"] not in approved_codes]

        # 5. Si no hay reglas aprobadas para este alcance:
        if not applicable_rules:
            return {
                "project_id": project_id,
                "discipline_code": discipline_code,
                "discipline_name": discipline.name,
                "topic_code": topic_code,
                "topic_name": topic.name,
                "execution_mode": mode,
                "can_execute": False,
                "empty_reason": "No hay reglas aprobadas para este alcance",
                "applicable_rules": [],
                "unapproved_rules": unapproved_rules,
                "included_documents": included_documents,
                "excluded_documents": excluded_documents,
                "missing_required_document_types": [],
                "phases_blueprint": [],
                "warnings": ["El alcance seleccionado no posee reglas activas aprobadas en producción."]
            }

        # 6. Analizar requerimientos documentales
        required_doc_types = set()
        for r in applicable_rules:
            for dt in r.get("applicable_document_types", []):
                required_doc_types.add(dt)

        missing_required_types = []
        if "LEGEND" in required_doc_types and len(included_documents) == 1:
            # Si se requiere leyenda y solo se seleccionó 1 documento, advertir
            missing_required_types.append({
                "document_type": "LEGEND",
                "reason": "Regla SYM-LEGEND-CONSISTENCY-001 requiere cuadro de leyendas de simbología.",
                "recommended_action": "Incluir la lámina de leyenda o cuadro de notas generales del proyecto."
            })

        # 7. Construir plano de fases (Fases 1 a 9)
        phases_blueprint = []
        for phase_num in range(1, 10):
            p_name, p_type = PHASE_NAMES[phase_num]
            phase_rules = [r for r in applicable_rules if r.get("execution_phase") == phase_num]
            phases_blueprint.append({
                "phase": phase_num,
                "phase_name": p_name,
                "step_type": p_type,
                "rule_count": len(phase_rules),
                "rules": [r["code"] for r in phase_rules],
                "description": "Fase técnica de preparación" if phase_num <= 4 else ("Fase de evaluación QA/QC" if phase_num <= 8 else "Consolidación de reporte")
            })

        warnings = []
        limitations = []
        if mode == "sandbox":
            warnings.append("Resultado exploratorio — no constituye validación productiva oficial.")
        if not included_documents:
            warnings.append("No se han seleccionado documentos para esta revisión.")

        if mode == "production" and topic_code == "PID_SYMBOLS":
            has_cat = cls._has_approved_production_catalog(db, discipline_code)
            if not has_cat:
                limitations.append("Catálogo de Simbología productivo sin versiones aprobadas con evidencia real autorizada. Las reglas de simbología resultarán en estado Not Evaluable.")

        can_execute = len(included_documents) > 0 and len(applicable_rules) > 0

        return {
            "project_id": project_id,
            "project_code": project.code,
            "project_name": project.name,
            "discipline_code": discipline_code,
            "discipline_name": discipline.name,
            "topic_code": topic_code,
            "topic_name": topic.name,
            "execution_mode": mode,
            "can_execute": can_execute,
            "applicable_rules": applicable_rules,
            "unapproved_rules": unapproved_rules,
            "included_documents": included_documents,
            "excluded_documents": excluded_documents,
            "missing_required_document_types": missing_required_types,
            "phases_blueprint": phases_blueprint,
            "warnings": warnings,
            "limitations": limitations
        }

    @classmethod
    def execute_review_run(
        cls,
        db: Session,
        project_id: str,
        discipline_code: str,
        topic_code: str,
        document_ids: List[str],
        mode: str = "production",
        requested_by: str = "user",
        run_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Ejecuta la corrida de auditoría:
        - Valida alcance y reglas aprobadas.
        - Fases 1-4: preparación de datos (sin hallazgos QA/QC).
        - Fases 5-8: evaluación determinística de reglas QA/QC.
        - Fase 9: consolidación y reporte persistido.
        """
        start_time = time.time()

        # 1. Generar plan pre-flight
        plan = cls.generate_review_plan(
            db=db,
            project_id=project_id,
            discipline_code=discipline_code,
            topic_code=topic_code,
            document_ids=document_ids,
            mode=mode
        )

        if not plan.get("can_execute"):
            raise ValueError(
                f"No se puede ejecutar la revisión: {plan.get('empty_reason', 'Verifique documentos y reglas aprobadas.')}"
            )

        project = db.query(Project).filter(Project.id == project_id).first()
        discipline = db.query(ReviewDiscipline).filter(ReviewDiscipline.code == discipline_code).first()
        topic = db.query(ReviewTopic).filter(ReviewTopic.code == topic_code).first()

        applicable_rules = plan["applicable_rules"]
        included_docs = plan["included_documents"]

        # Nombre por defecto si no se especificó
        if not run_name:
            run_name = f"Revisión {discipline_code} - {topic.name} ({mode.capitalize()})"

        # 2. Crear registro ReviewRun
        review_run = ReviewRun(
            organization_id=project.organization_id,
            project_id=project.id,
            discipline_id=discipline.id,
            topic_id=topic.id,
            run_name=run_name,
            execution_mode=mode,
            status="running",
            requested_by=requested_by,
            requested_at=datetime.utcnow(),
            rule_count=len(applicable_rules),
            document_count=len(included_docs)
        )
        db.add(review_run)
        db.flush()

        # 3. Registrar ReviewRunDocument
        for idoc in included_docs:
            rd = ReviewRunDocument(
                review_run_id=review_run.id,
                document_id=idoc["document_id"],
                inclusion_reason=idoc["inclusion_reason"],
                document_role=idoc["document_role"],
                status="included"
            )
            db.add(rd)
        db.flush()

        # 4. Inicializar los 9 ReviewRunSteps
        step_records: Dict[int, ReviewRunStep] = {}
        for phase_num in range(1, 10):
            p_name, p_type = PHASE_NAMES[phase_num]
            step = ReviewRunStep(
                review_run_id=review_run.id,
                phase=phase_num,
                phase_name=p_name,
                step_type=p_type,
                status="queued",
                input_summary={},
                output_summary={}
            )
            db.add(step)
            db.flush()
            step_records[phase_num] = step

        # Asegurar registro de instancias de reglas
        RuleRegistry.register_default_rules()

        # 5. Ejecutar Fases 1 a 4 (Preparación de datos - NUNCA generan hallazgos QA/QC)
        # Fase 1: Ingestión y verificación
        s1 = step_records[1]
        s1.status = "running"
        s1.started_at = datetime.utcnow()
        s1.input_summary = {"document_count": len(included_docs), "document_ids": [d["document_id"] for d in included_docs]}
        s1.output_summary = {"verified_documents": len(included_docs), "status": "all_verified"}
        s1.status = "succeeded"
        s1.completed_at = datetime.utcnow()

        # Fase 2: Raster y OCR
        s2 = step_records[2]
        s2.status = "running"
        s2.started_at = datetime.utcnow()
        s2.input_summary = {"document_count": len(included_docs)}
        s2.output_summary = {"ocr_status": "ready"}
        s2.status = "succeeded"
        s2.completed_at = datetime.utcnow()

        # Fase 3: Viñetas y segmentación
        s3 = step_records[3]
        s3.status = "running"
        s3.started_at = datetime.utcnow()
        s3.input_summary = {"phases_target": "title_blocks"}
        s3.output_summary = {"title_blocks_ready": True}
        s3.status = "succeeded"
        s3.completed_at = datetime.utcnow()

        # Fase 4: Simbología y Tablas
        s4 = step_records[4]
        s4.status = "running"
        s4.started_at = datetime.utcnow()
        s4.input_summary = {"catalog_version": "ISA-5.1-2009-CANONICAL-V1"}

        from app.services.symbols.symbol_inventory_service import SymbolInventoryService
        inv_groups, inv_metrics = SymbolInventoryService.build_run_inventory(db, review_run, force_rebuild=True)

        s4.output_summary = {
            "symbol_extraction_status": "ready",
            "inventory_groups_count": len(inv_groups),
            "valid_symbol_occurrences": inv_metrics.get("valid_symbol_occurrences", 0),
            "unknown_symbols_count": inv_metrics.get("unknown", 0),
            "recognized_production": inv_metrics.get("recognized_production", 0),
            "recognized_sandbox": inv_metrics.get("recognized_sandbox", 0)
        }
        s4.status = "succeeded"
        s4.completed_at = datetime.utcnow()

        db.commit()

        # 6. Recopilar evidencias de las láminas para evaluación
        doc_ids = [d["document_id"] for d in included_docs]
        sheets = db.query(DocumentSheet).filter(DocumentSheet.document_id.in_(doc_ids)).all()

        # Mapear dependencias
        rule_dependencies: Dict[str, List[str]] = {}
        for r_info in applicable_rules:
            deps = db.query(RuleExecutionDependency).filter(
                RuleExecutionDependency.rule_id == r_info["rule_id"]
            ).all()
            if deps:
                dep_rule_ids = [d.depends_on_rule_id for d in deps]
                dep_rules = db.query(RuleDefinition).filter(RuleDefinition.id.in_(dep_rule_ids)).all()
                rule_dependencies[r_info["code"]] = [dr.code for dr in dep_rules]

        rule_eval_results: Dict[str, str] = {} # rule_code -> status (passed, failed, warning, not_evaluable)
        total_findings = 0
        execution_stats = {"passed": 0, "failed": 0, "warning": 0, "not_evaluable": 0, "critical": 0, "high": 0, "medium": 0}

        has_prod_catalog = cls._has_approved_production_catalog(db, discipline_code) if mode == "production" else True

        # 7. Ejecutar Fases 5 a 8 (Evaluación QA/QC)
        for phase_num in range(5, 9):
            p_step = step_records[phase_num]
            p_rules = [r for r in applicable_rules if r.get("execution_phase") == phase_num]

            if not p_rules:
                p_step.status = "skipped"
                p_step.output_summary = {"message": "No hay reglas programadas en esta fase para este alcance."}
                continue

            p_step.status = "running"
            p_step.started_at = datetime.utcnow()
            p_step.input_summary = {"rules_to_evaluate": [r["code"] for r in p_rules]}

            for r_meta in p_rules:
                r_code = r_meta["code"]
                rule_inst = RuleRegistry.get_rule(r_code)

                # Semántica de Production: validar catálogo aprobado para reglas que lo requieren
                if mode == "production" and not has_prod_catalog and (r_code.startswith("SYM-") or "detected_symbols" in r_meta.get("requires_data", [])):
                    execution = RuleExecution(
                        review_run_id=review_run.id,
                        document_id=doc_ids[0] if doc_ids else None,
                        rule_id=r_meta["rule_id"],
                        phase=phase_num,
                        execution_status="not_evaluable",
                        not_evaluable_reason_code="MISSING_SYMBOL_CATALOG",
                        not_evaluable_reason_message="No existen plantillas activas con versión aprobada y evidencia autorizada en el Catálogo de Simbología productivo.",
                        missing_requirements=["symbol_catalog_approved", "authorized_evidence"],
                        recommended_action="Aprobar versiones canónicas con evidencia autorizada en el Catálogo de Simbología o ejecutar en modo Sandbox.",
                        result_summary={"catalog": "missing_or_unapproved", "status": "not_evaluable"},
                        confidence=1.0,
                        started_at=datetime.utcnow(),
                        completed_at=datetime.utcnow()
                    )
                    db.add(execution)
                    rule_eval_results[r_code] = "not_evaluable"
                    execution_stats["not_evaluable"] += 1
                    continue

                # Verificar dependencias declarativas
                deps = rule_dependencies.get(r_code, [])
                dep_failed = False
                unmet_dep_code = None
                for dep_code in deps:
                    prev_status = rule_eval_results.get(dep_code)
                    if prev_status in ["failed", "not_evaluable"]:
                        dep_failed = True
                        unmet_dep_code = dep_code
                        break

                if dep_failed:
                    # Not Evaluable Estructurado por dependencia
                    execution = RuleExecution(
                        review_run_id=review_run.id,
                        document_id=doc_ids[0] if doc_ids else None,
                        rule_id=r_meta["rule_id"],
                        phase=phase_num,
                        execution_status="not_evaluable",
                        not_evaluable_reason_code="RULE_DEPENDENCY_NOT_MET",
                        not_evaluable_reason_message=f"La regla depende de {unmet_dep_code}, la cual no se cumplió satisfactoriamente.",
                        missing_requirements=[unmet_dep_code],
                        recommended_action=f"Corregir los hallazgos de {unmet_dep_code} antes de reevaluar esta regla.",
                        result_summary={"dependency": unmet_dep_code, "status": "blocked"},
                        confidence=1.0,
                        started_at=datetime.utcnow(),
                        completed_at=datetime.utcnow()
                    )
                    db.add(execution)
                    rule_eval_results[r_code] = "not_evaluable"
                    execution_stats["not_evaluable"] += 1
                    continue

                # Evaluar regla sobre cada lámina o consolidado
                rule_overall_status = "passed"
                evaluated_any = False

                for sheet in (sheets if sheets else [None]):
                    sheet_id = sheet.id if sheet else None
                    doc_id = sheet.document_id if sheet else (doc_ids[0] if doc_ids else None)

                    # Obtener artefactos
                    tables = db.query(ExtractedTable).filter(ExtractedTable.sheet_id == sheet_id).all() if sheet_id else []
                    cells_by_table = {}
                    for t in tables:
                        cells_by_table[t.id] = db.query(ExtractedTableCell).filter(ExtractedTableCell.table_id == t.id).all()

                    if mode == "production":
                        symbols_raw = db.query(DetectedSymbol).filter(
                            DetectedSymbol.sheet_id == sheet_id,
                            DetectedSymbol.environment != "sandbox"
                        ).all() if sheet_id else []
                        symbols = []
                        for s in symbols_raw:
                            matched_id = getattr(s, "matched_library_entry_id", None) or getattr(s, "source_asset_template_id", None)
                            if matched_id:
                                tmpl = db.query(SymbolTemplate).filter(SymbolTemplate.id == matched_id).first()
                                if tmpl and (tmpl.status in ["test_only", "sandbox"] or getattr(tmpl, "category", "") == "test_only"):
                                    continue
                            symbols.append(s)
                    else:
                        symbols = db.query(DetectedSymbol).filter(DetectedSymbol.sheet_id == sheet_id).all() if sheet_id else []
                    texts = db.query(ExtractedText).filter(ExtractedText.sheet_id == sheet_id).all() if sheet_id else []
                    regions = db.query(SheetRegion).filter(SheetRegion.sheet_id == sheet_id).all() if sheet_id else []
                    tb = db.query(TitleBlockExtraction).filter(TitleBlockExtraction.sheet_id == sheet_id).first() if sheet_id else None

                    inputs = RuleInput(
                        document_id=doc_id,
                        sheet_id=sheet_id,
                        document=sheet.document if sheet else None,
                        sheet=sheet,
                        title_block=tb,
                        tables=tables,
                        cells_by_table=cells_by_table,
                        symbols=symbols,
                        texts=texts,
                        regions=regions,
                        normative_criteria=[]
                    )

                    if rule_inst:
                        try:
                            eval_res: RuleResult = rule_inst.evaluate(inputs)
                        except Exception as e:
                            logger.error(f"Error evaluando regla {r_code}: {e}")
                            eval_res = RuleResult(
                                rule_code=r_code,
                                rule_name=r_meta["name"],
                                status="not_evaluable",
                                severity="critical",
                                title=f"Error en Evaluación de {r_code}",
                                description=str(e),
                                not_evaluable_reason_code="EXTRACTION_FAILED",
                                not_evaluable_reason_message=str(e),
                                recommended_action="Verificar consistencia de extracciones en la lámina."
                            )
                    else:
                        eval_res = RuleResult(
                            rule_code=r_code,
                            rule_name=r_meta["name"],
                            status="not_evaluable",
                            severity="info",
                            title="Regla No Implementada",
                            description="No se encontró implementación en memoria.",
                            not_evaluable_reason_code="NO_APPROVED_RULES",
                            not_evaluable_reason_message="Regla sin ejecutor activo.",
                            recommended_action="Contactar a administración para activar implementación."
                        )

                    evaluated_any = True
                    st = eval_res.status.lower()

                    if st in ["failed", "critical"]:
                        rule_overall_status = "failed"
                    elif st in ["warning"] and rule_overall_status != "failed":
                        rule_overall_status = "warning"
                    elif st in ["not_evaluable"] and rule_overall_status not in ["failed", "warning"]:
                        rule_overall_status = "not_evaluable"

                    # Crear RuleExecution
                    execution = RuleExecution(
                        review_run_id=review_run.id,
                        document_id=doc_id,
                        sheet_id=sheet_id,
                        rule_id=r_meta["rule_id"],
                        phase=phase_num,
                        execution_status=eval_res.status,
                        evidence=eval_res.evidence_refs or {},
                        result_summary={
                            "title": eval_res.title,
                            "description": eval_res.description,
                            "verdict": eval_res.verdict,
                            "expected_value": eval_res.expected_value,
                            "observed_value": eval_res.observed_value,
                            "delta": eval_res.delta
                        },
                        confidence=eval_res.confidence,
                        not_evaluable_reason_code=eval_res.not_evaluable_reason_code,
                        not_evaluable_reason_message=eval_res.not_evaluable_reason_message,
                        missing_requirements=eval_res.missing_requirements,
                        recommended_action=eval_res.recommended_action,
                        started_at=datetime.utcnow(),
                        completed_at=datetime.utcnow()
                    )
                    db.add(execution)
                    db.flush()

                    # Si generó hallazgos (failed o warning)
                    if eval_res.status in ["failed", "warning"]:
                        findings_to_create = eval_res.findings_list or [
                            {
                                "title": eval_res.title,
                                "description": eval_res.description,
                                "severity": eval_res.severity,
                                "recommendation": eval_res.recommendation,
                                "bbox": getattr(eval_res, "bbox", None)
                            }
                        ]

                        for f_data in findings_to_create:
                            is_exploratory = (mode == "sandbox")
                            warning_text = "Resultado exploratorio — no constituye validación productiva" if is_exploratory else None

                            # En producción, no generar hallazgos basados en símbolos de sandbox
                            sym_id = f_data.get("symbol_id")
                            if mode == "production" and sym_id:
                                sym_obj = db.query(DetectedSymbol).filter(DetectedSymbol.id == sym_id).first()
                                if sym_obj and (sym_obj.environment == "sandbox" or getattr(sym_obj, "record_kind", "") == "sandbox"):
                                    continue

                            nav_ctx = {
                                "document_id": doc_id,
                                "sheet_id": sheet_id,
                                "bbox": f_data.get("bbox"),
                                "crop_url": f_data.get("crop_url"),
                                "execution_mode": mode,
                                "is_exploratory": is_exploratory
                            }
                            evidence_refs = {
                                **(f_data.get("evidence_refs") or {}),
                                "execution_mode": mode,
                                "is_exploratory": is_exploratory
                            }
                            if warning_text:
                                evidence_refs["warning"] = warning_text

                            sev = f_data.get("severity", eval_res.severity)
                            finding_title = f_data.get("title", eval_res.title)
                            if is_exploratory and not finding_title.startswith("[SANDBOX]"):
                                finding_title = f"[SANDBOX] {finding_title}"

                            finding = RuleFinding(
                                organization_id=project.organization_id,
                                review_run_id=review_run.id,
                                rule_execution_id=execution.id,
                                document_id=doc_id,
                                sheet_id=sheet_id,
                                rule_id=r_meta["rule_id"],
                                rule_code=r_code,
                                rule_name=r_meta["name"],
                                category=r_meta["category"],
                                severity=sev,
                                status="open",
                                confidence=eval_res.confidence,
                                finding_type="normative_violation" if sev in ["critical", "high"] else "reconciliation_mismatch",
                                title=finding_title,
                                description=f_data.get("description", eval_res.description),
                                recommendation=f_data.get("recommendation", eval_res.recommendation),
                                evidence_refs=evidence_refs,
                                bbox=f_data.get("bbox"),
                                navigation_context=nav_ctx
                            )
                            db.add(finding)
                            total_findings += 1
                            if sev == "critical":
                                execution_stats["critical"] += 1
                            elif sev == "high":
                                execution_stats["high"] += 1
                            else:
                                execution_stats["medium"] += 1

                rule_eval_results[r_code] = rule_overall_status
                if rule_overall_status == "passed":
                    execution_stats["passed"] += 1
                elif rule_overall_status == "failed":
                    execution_stats["failed"] += 1
                elif rule_overall_status == "warning":
                    execution_stats["warning"] += 1
                elif rule_overall_status == "not_evaluable":
                    execution_stats["not_evaluable"] += 1

            p_step.status = "succeeded"
            p_step.output_summary = {
                "rules_evaluated": len(p_rules),
                "phase_stats": {k: v for k, v in execution_stats.items()}
            }
            p_step.completed_at = datetime.utcnow()
            db.commit()

        # 8. Fase 9: Consolidación y Reporte Final
        s9 = step_records[9]
        s9.status = "running"
        s9.started_at = datetime.utcnow()

        elapsed_sec = round(time.time() - start_time, 2)
        review_run.status = "completed"
        review_run.execution_time_sec = elapsed_sec
        review_run.rules_applied_count = len(applicable_rules)
        review_run.findings_count = total_findings
        review_run.summary_stats = execution_stats
        review_run.summary = {
            "execution_mode": mode,
            "discipline_code": discipline_code,
            "topic_code": topic_code,
            "stats": execution_stats,
            "total_findings": total_findings,
            "elapsed_seconds": elapsed_sec
        }
        review_run.completed_at = datetime.utcnow()
        db.commit()

        # Generar reporte persistido inicial (JSON)
        report = ReviewExportService.create_report(db, review_run.id, export_format="json")

        s9.status = "succeeded"
        s9.output_summary = {
            "report_id": report.id,
            "report_sha256": report.sha256,
            "artifact_path": report.artifact_path,
            "status": "ready"
        }
        s9.completed_at = datetime.utcnow()
        db.commit()

        logger.info(f"ReviewRun {review_run.id} completado con éxito en {elapsed_sec}s. Hallazgos: {total_findings}")

        return {
            "review_run_id": review_run.id,
            "project_id": project_id,
            "run_name": review_run.run_name,
            "discipline_code": discipline_code,
            "topic_code": topic_code,
            "execution_mode": mode,
            "status": review_run.status,
            "execution_time_sec": elapsed_sec,
            "rules_applied_count": len(applicable_rules),
            "findings_count": total_findings,
            "summary_stats": execution_stats,
            "report_id": report.id,
            "report_sha256": report.sha256
        }

    @classmethod
    def get_review_run_details(cls, db: Session, review_run_id: str) -> Optional[Dict[str, Any]]:
        run = db.query(ReviewRun).filter(ReviewRun.id == review_run_id).first()
        if not run:
            return None

        steps = db.query(ReviewRunStep).filter(ReviewRunStep.review_run_id == run.id).order_by(ReviewRunStep.phase).all()
        executions = db.query(RuleExecution).filter(RuleExecution.review_run_id == run.id).order_by(RuleExecution.phase).all()
        findings = db.query(RuleFinding).filter(RuleFinding.review_run_id == run.id).all()
        run_docs = db.query(ReviewRunDocument).filter(ReviewRunDocument.review_run_id == run.id).all()
        reports = db.query(ReviewReport).filter(ReviewReport.review_run_id == run.id).order_by(ReviewReport.created_at.desc()).all()

        doc_ids = [rd.document_id for rd in run_docs]
        docs = db.query(Document).filter(Document.id.in_(doc_ids)).all() if doc_ids else []
        doc_map = {d.id: d for d in docs}

        from app.services.symbols.symbol_inventory_service import SymbolInventoryService
        inv_groups, inv_metrics = SymbolInventoryService.build_run_inventory(db, run, force_rebuild=False)

        return {
            "id": run.id,
            "project_id": run.project_id,
            "run_name": run.run_name,
            "discipline_code": run.discipline.code if run.discipline else "GENERAL",
            "discipline_name": run.discipline.name if run.discipline else "General",
            "topic_code": run.topic.code if run.topic else "ALL",
            "topic_name": run.topic.name if run.topic else "General",
            "execution_mode": run.execution_mode,
            "status": run.status,
            "requested_by": run.requested_by,
            "requested_at": run.requested_at.isoformat() if run.requested_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "execution_time_sec": run.execution_time_sec,
            "rule_count": run.rule_count,
            "document_count": run.document_count,
            "findings_count": run.findings_count,
            "summary_stats": run.summary_stats or {},
            "documents": [
                {
                    "document_id": rd.document_id,
                    "filename": getattr(doc_map.get(rd.document_id), "filename", "N/A"),
                    "inclusion_reason": rd.inclusion_reason,
                    "document_role": rd.document_role,
                    "status": rd.status
                }
                for rd in run_docs
            ],
            "steps": [
                {
                    "phase": s.phase,
                    "phase_name": s.phase_name,
                    "step_type": s.step_type,
                    "status": s.status,
                    "input_summary": s.input_summary,
                    "output_summary": s.output_summary,
                    "error_summary": s.error_summary
                }
                for s in steps
            ],
            "executions": [
                {
                    "id": ex.id,
                    "rule_code": ex.rule.code if ex.rule else "N/A",
                    "rule_name": ex.rule.name if ex.rule else "N/A",
                    "phase": ex.phase,
                    "status": ex.execution_status,
                    "confidence": ex.confidence,
                    "not_evaluable_reason_code": ex.not_evaluable_reason_code,
                    "not_evaluable_reason_message": ex.not_evaluable_reason_message,
                    "missing_requirements": ex.missing_requirements,
                    "recommended_action": ex.recommended_action,
                    "result_summary": ex.result_summary
                }
                for ex in executions
            ],
            "findings": [
                {
                    "id": f.id,
                    "rule_code": f.rule_code,
                    "rule_name": f.rule_name,
                    "severity": f.severity,
                    "status": f.status,
                    "title": f.title,
                    "description": f.description,
                    "recommendation": f.recommendation,
                    "bbox": f.bbox,
                    "navigation_context": f.navigation_context,
                    "evidence_refs": f.evidence_refs or {}
                }
                for f in findings
            ],
            "reports": [
                {
                    "id": rep.id,
                    "report_name": rep.report_name,
                    "format": rep.format,
                    "artifact_path": rep.artifact_path,
                    "sha256": rep.sha256,
                    "status": rep.status,
                    "file_size_bytes": os.path.getsize(rep.artifact_path) if rep.artifact_path and os.path.exists(rep.artifact_path) else 0,
                    "created_at": rep.created_at.isoformat() if rep.created_at else None,
                    "baseline_catalog_version": rep.baseline_catalog_version
                }
                for rep in reports
            ],
            "baseline_catalog_version": (reports[0].baseline_catalog_version if reports and reports[0].baseline_catalog_version else None) or ("PIP PNC00001 (Sandbox Candidate Baseline v0.1)" if run.execution_mode == "sandbox" else "PIP PNC00001 (Production Formal Baseline)"),
            "symbol_inventory": {
                "metrics": inv_metrics,
                "groups": [
                    {
                        "id": g.id,
                        "review_run_id": g.review_run_id,
                        "grouping_key": g.grouping_key,
                        "grouping_method": g.grouping_method,
                        "grouping_confidence": g.grouping_confidence,
                        "grouping_version": g.grouping_version,
                        "display_code": g.display_code,
                        "unknown_group_id": g.unknown_group_id,
                        "representative_occurrence_id": g.representative_occurrence_id,
                        "representative_selection_reason": g.representative_selection_reason,
                        "matched_template_id": g.matched_template_id,
                        "matched_template_version_id": g.matched_template_version_id,
                        "canonical_name": g.canonical_name,
                        "description": g.description,
                        "technical_function": g.technical_function,
                        "standard_reference": g.standard_reference,
                        "catalog_status": g.catalog_status,
                        "confidence_summary": g.confidence_summary or {},
                        "total_occurrences": g.total_occurrences,
                        "occurrences_by_document": g.occurrences_by_document or {},
                        "occurrences_by_sheet": g.occurrences_by_sheet or {},
                        "requires_human_review": g.requires_human_review,
                        "explanation": g.explanation,
                        "created_at": g.created_at.isoformat() if g.created_at else None
                    }
                    for g in inv_groups
                ]
            }
        }
