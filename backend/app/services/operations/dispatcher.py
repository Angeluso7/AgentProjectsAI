import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

import app.db.session as session_module
from app.db.repositories.operations_repository import OperationsRepository
from app.services.ingest.service import IngestService
from app.services.ocr.service import OcrService
from app.services.layout.service import LayoutService
from app.services.intake.service import IntakeService
from app.core.logging import logger

# Executor en segundo plano para desarrollo y ejecución asíncrona local
_thread_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="job_worker")
_active_futures = set()

def wait_for_all_jobs(timeout: float = 3.0) -> None:
    """Espera que todos los jobs en segundo plano completen su ejecución (útil para pruebas)."""
    from concurrent.futures import wait
    current_futures = list(_active_futures)
    if current_futures:
        wait(current_futures, timeout=timeout)

class JobDispatcher:
    """Despachador y ejecutor de tareas asíncronas con reintentos acotados y registro de auditoría."""

    def __init__(self, db: Optional[Session] = None):
        self.db = db

    def dispatch(self, job_id: str, async_mode: bool = True) -> None:
        """Encola o ejecuta un job. Si async_mode=True, se despacha a un hilo en segundo plano."""
        if async_mode:
            fut = _thread_pool.submit(self._execute_job_in_isolated_session, job_id)
            _active_futures.add(fut)
            fut.add_done_callback(lambda f: _active_futures.discard(f))
        else:
            self._execute_job_in_isolated_session(job_id)

    def _execute_job_in_isolated_session(self, job_id: str) -> None:
        """Ejecuta el job en una sesión aislada de base de datos para prevenir interferencia de hilos."""
        db = session_module.SessionLocal()
        try:
            self._run_job_lifecycle(job_id, db)
        finally:
            db.close()

    def _run_job_lifecycle(self, job_id: str, db: Session) -> None:
        repo = OperationsRepository(db)
        job = repo.get_job(job_id)
        if not job:
            logger.error(f"Job '{job_id}' no encontrado en BD.")
            return

        if job.status in ["completed", "cancelled"]:
            logger.info(f"Job '{job_id}' ya finalizó con estado '{job.status}'. Ignorando.")
            return

        # Transición a running
        repo.update_job_status(
            job_id=job.id,
            status="running",
            stage="processing",
            progress_percent=10,
            actor_type="worker"
        )

        try:
            result = self._execute_handler(job, db, repo)
            
            # Evaluación de políticas de confianza y trazabilidad post-procesamiento
            self._evaluate_post_execution_policies(job, result, db, repo)

            # Transición a completed
            repo.update_job_status(
                job_id=job.id,
                status="completed",
                stage="finished",
                progress_percent=100,
                result_summary=result,
                actor_type="worker"
            )
            logger.info(f"Job '{job.id}' [{job.job_type}] completado exitosamente.")

        except Exception as e:
            err_msg = str(e)
            stack = traceback.format_exc()
            logger.error(f"Error en ejecución de Job '{job.id}': {err_msg}\n{stack}")

            is_retryable = not isinstance(e, (ValueError, PermissionError, FileNotFoundError))
            
            if is_retryable and job.retry_count < job.max_retries:
                # Programar reintento
                new_retry = job.retry_count + 1
                job.retry_count = new_retry
                db.commit()

                repo.record_event(
                    job_id=job.id,
                    event_type="retry_scheduled",
                    status_before="running",
                    status_after="retrying",
                    stage="retry_backoff",
                    message=f"Reintento {new_retry}/{job.max_retries} programado tras error: {err_msg}",
                    actor_type="worker"
                )
                repo.update_job_status(job_id=job.id, status="retrying", stage="retry_backoff")
                time.sleep(min(2 ** new_retry, 8)) # Backoff exponencial acotado
                self._run_job_lifecycle(job_id, db)
            else:
                # Fallo terminal
                repo.update_job_status(
                    job_id=job.id,
                    status="failed",
                    stage="aborted",
                    error_code=type(e).__name__,
                    error_message=f"{err_msg}\n{stack[:500]}",
                    actor_type="worker"
                )
                # Crear ReviewTask por fallo crítico de procesamiento
                repo.create_review_task(
                    task_type="failed_processing_job",
                    reason_code="JOB_FAILURE",
                    reason_message=f"El job '{job.job_type}' falló definitivamente: {err_msg}",
                    priority="high",
                    project_id=job.project_id,
                    job_id=job.id,
                    payload={"job_type": job.job_type, "target_id": job.target_id, "error": err_msg}
                )

    def _execute_handler(self, job: Any, db: Session, repo: OperationsRepository) -> Dict[str, Any]:
        """Ejecuta el servicio de dominio correspondiente envolviendo capacidades existentes."""
        jtype = job.job_type
        target_id = job.target_id
        payload = job.input_payload or {}
        force = payload.get("force_reprocess", False)

        if jtype == "sheet_ocr":
            repo.update_job_status(job.id, status="running", stage="running_ocr", progress_percent=30)
            ocr_svc = OcrService(db)
            texts = ocr_svc.process_sheet_ocr(sheet_id=target_id, force_reprocess=force, engine=payload.get("engine"))
            repo.update_job_status(job.id, status="running", stage="ocr_completed", progress_percent=85)
            return {"sheet_id": target_id, "texts_extracted_count": len(texts)}

        elif jtype == "document_ocr":
            repo.update_job_status(job.id, status="running", stage="running_document_ocr", progress_percent=25)
            ocr_svc = OcrService(db)
            res = ocr_svc.process_document_ocr(document_id=target_id, force_reprocess=force, engine=payload.get("engine"))
            return {"document_id": target_id, "sheets_processed": len(res)}

        elif jtype == "sheet_layout":
            repo.update_job_status(job.id, status="running", stage="segmenting_layout", progress_percent=40)
            layout_svc = LayoutService(db)
            res = layout_svc.process_sheet(sheet_id=target_id, force_reprocess=force)
            return res

        elif jtype == "document_layout":
            repo.update_job_status(job.id, status="running", stage="segmenting_document_layout", progress_percent=30)
            layout_svc = LayoutService(db)
            res = layout_svc.process_document(document_id=target_id, force_reprocess=force)
            return {"document_id": target_id, "sheets_processed": len(res)}

        elif jtype == "title_block_match":
            repo.update_job_status(job.id, status="running", stage="matching_title_block", progress_percent=50)
            layout_svc = LayoutService(db)
            extr = layout_svc.match_and_extract_title_block(
                sheet_id=target_id,
                force_reprocess=force,
                template_id=payload.get("template_id")
            )
            return {
                "sheet_id": target_id,
                "sheet_code": extr.sheet_code,
                "scale": extr.scale_text,
                "revision": extr.revision,
                "match_score": extr.match_score,
                "status": extr.extraction_status
            }

        elif jtype == "sheet_table_extract":
            repo.update_job_status(job.id, status="running", stage="extracting_tables", progress_percent=40)
            from app.services.tables.service import TableService
            table_svc = TableService(db)
            tables = table_svc.extract_tables_from_sheet(sheet_id=target_id, force_reprocess=force, region_id=payload.get("region_id"))
            repo.update_job_status(job.id, status="running", stage="tables_extracted", progress_percent=90)
            return {"sheet_id": target_id, "tables_count": len(tables), "tables": [t.id for t in tables]}

        elif jtype == "document_table_extract":
            repo.update_job_status(job.id, status="running", stage="extracting_document_tables", progress_percent=30)
            from app.services.tables.service import TableService
            table_svc = TableService(db)
            res = table_svc.extract_tables_from_document(document_id=target_id, force_reprocess=force)
            return {"document_id": target_id, "sheets_processed": len(res), "details": res}

        elif jtype == "sheet_symbol_detect":
            repo.update_job_status(job.id, status="running", stage="detecting_symbols", progress_percent=40)
            from app.services.symbols.service import SymbolService
            sym_svc = SymbolService(db)
            syms = sym_svc.detect_sheet_symbols(
                sheet_id=target_id,
                force_reprocess=force,
                engine=payload.get("engine", "yolo_sahi_hybrid"),
                confidence_threshold=payload.get("confidence_threshold", 0.50),
                discipline=payload.get("discipline")
            )
            repo.update_job_status(job.id, status="running", stage="symbols_detected", progress_percent=90)
            return {"sheet_id": target_id, "symbols_count": len(syms), "symbols": [s.id for s in syms]}

        elif jtype == "document_symbol_detect":
            repo.update_job_status(job.id, status="running", stage="detecting_document_symbols", progress_percent=30)
            from app.services.symbols.service import SymbolService
            sym_svc = SymbolService(db)
            res = sym_svc.detect_document_symbols(
                document_id=target_id,
                force_reprocess=force,
                engine=payload.get("engine", "yolo_sahi_hybrid"),
                discipline=payload.get("discipline")
            )
            return {"document_id": target_id, "sheets_processed": len(res), "details": res}

        elif jtype == "sheet_rules_eval":
            repo.update_job_status(job.id, status="running", stage="evaluating_rules", progress_percent=40)
            from app.services.rules.engine import RuleEngine
            engine = RuleEngine(db)
            findings = engine.evaluate_sheet(sheet_id=target_id, job_id=job.id)
            repo.update_job_status(job.id, status="running", stage="rules_evaluated", progress_percent=90)
            return {"sheet_id": target_id, "findings_count": len(findings), "findings": [f.id for f in findings]}

        elif jtype == "document_rules_eval":
            repo.update_job_status(job.id, status="running", stage="evaluating_document_rules", progress_percent=30)
            from app.services.rules.engine import RuleEngine
            engine = RuleEngine(db)
            res = engine.evaluate_document(document_id=target_id, job_id=job.id)
            return {"document_id": target_id, "sheets_processed": len(res), "details": res}

        elif jtype == "sheet_report_generate":
            repo.update_job_status(job.id, status="running", stage="generating_sheet_report", progress_percent=40)
            from app.services.reporting.service import ReportingService
            rep_svc = ReportingService(db)
            report = rep_svc.generate_sheet_report(
                sheet_id=target_id,
                report_type=payload.get("report_type", "technical_audit_qaqc"),
                generated_by=payload.get("generated_by", "auditor_qa"),
                job_id=job.id
            )
            repo.update_job_status(job.id, status="running", stage="report_generated", progress_percent=95)
            return {"report_id": report.id, "pdf_path": report.artifact_pdf_path, "json_path": report.artifact_json_path, "bundle_path": report.artifact_bundle_path}

        elif jtype == "document_report_generate":
            repo.update_job_status(job.id, status="running", stage="generating_document_report", progress_percent=40)
            from app.services.reporting.service import ReportingService
            rep_svc = ReportingService(db)
            report = rep_svc.generate_document_report(
                document_id=target_id,
                report_type=payload.get("report_type", "technical_audit_qaqc"),
                generated_by=payload.get("generated_by", "auditor_qa"),
                job_id=job.id
            )
            repo.update_job_status(job.id, status="running", stage="report_generated", progress_percent=95)
            return {"report_id": report.id, "pdf_path": report.artifact_pdf_path, "json_path": report.artifact_json_path, "bundle_path": report.artifact_bundle_path}

        elif jtype == "document_pipeline_run":
            repo.update_job_status(job.id, status="running", stage="running_document_pipeline", progress_percent=20)
            from app.services.operations.pipeline_service import ReviewPipelineService
            pipe_svc = ReviewPipelineService(db)
            pipeline_run_id = payload.get("pipeline_run_id")
            if not pipeline_run_id:
                p_run = pipe_svc.create_pipeline_run(scope_type="document", scope_id=target_id, requested_by=job.requested_by, force_reprocess=force)
                pipeline_run_id = p_run.id
            p_res = pipe_svc.execute_pipeline(pipeline_run_id=pipeline_run_id, force_reprocess=force)
            return {"pipeline_run_id": p_res.id, "status": p_res.status, "final_report_id": p_res.final_report_id, "summary": p_res.summary}

        elif jtype == "sheet_pipeline_run":
            repo.update_job_status(job.id, status="running", stage="running_sheet_pipeline", progress_percent=20)
            from app.services.operations.pipeline_service import ReviewPipelineService
            pipe_svc = ReviewPipelineService(db)
            pipeline_run_id = payload.get("pipeline_run_id")
            if not pipeline_run_id:
                p_run = pipe_svc.create_pipeline_run(scope_type="sheet", scope_id=target_id, requested_by=job.requested_by, force_reprocess=force)
                pipeline_run_id = p_run.id
            p_res = pipe_svc.execute_pipeline(pipeline_run_id=pipeline_run_id, force_reprocess=force)
            return {"pipeline_run_id": p_res.id, "status": p_res.status, "final_report_id": p_res.final_report_id, "summary": p_res.summary}

        elif jtype == "source_ingest":
            repo.update_job_status(job.id, status="running", stage="routing_intake_source", progress_percent=40)
            intake_svc = IntakeService(db)
            res = intake_svc.ingest_source(source_id=target_id, project_id=job.project_id)
            return res

        else:
            raise ValueError(f"Tipo de job '{jtype}' no soportado por el despachador.")

    def _evaluate_post_execution_policies(
        self,
        job: Any,
        result: Dict[str, Any],
        db: Session,
        repo: OperationsRepository
    ) -> None:
        """Aplica las políticas de confianza y genera ReviewTask o DecisionTrace según corresponda."""
        if job.job_type in ["sheet_layout", "title_block_match"]:
            tb_data = result.get("title_block", result)
            match_score = tb_data.get("match_score", 1.0)
            sheet_id = job.target_id

            policy = repo.get_active_policy(applies_to="title_block_match")
            auto_thresh = policy.auto_accept_threshold if policy else 0.85
            review_thresh = policy.review_threshold if policy else 0.65

            if match_score < auto_thresh:
                reason = "MATCH_BELOW_THRESHOLD" if match_score >= review_thresh else "LOW_CONFIDENCE"
                msg = f"Viñeta con score de matching ({match_score:.2f}) inferior al umbral automático ({auto_thresh:.2f})."
                
                # Crear tarea de revisión humana
                repo.create_review_task(
                    task_type="title_block_match_review",
                    reason_code=reason,
                    reason_message=msg,
                    confidence=match_score,
                    priority="medium" if match_score >= review_thresh else "high",
                    project_id=job.project_id,
                    sheet_id=sheet_id,
                    job_id=job.id,
                    evidence_refs={"match_score": match_score},
                    payload=tb_data
                )
                
                # Registrar traza de decisión
                repo.record_trace(
                    trace_type="title_block_match",
                    entity_type="TitleBlockExtraction",
                    entity_id=sheet_id,
                    engine_name="LayoutAnalyzer",
                    engine_version="v1.0",
                    confidence=match_score,
                    policy_id=policy.id if policy else None,
                    policy_version=policy.version if policy else "1.0",
                    decision_status="review_required" if match_score >= review_thresh else "exception_required",
                    explanation=f"Matching de viñeta score {match_score:.2f} < auto_accept {auto_thresh:.2f}. Tarea de revisión creada.",
                    sheet_id=sheet_id,
                    job_id=job.id
                )
            else:
                repo.record_trace(
                    trace_type="title_block_match",
                    entity_type="TitleBlockExtraction",
                    entity_id=sheet_id,
                    engine_name="LayoutAnalyzer",
                    engine_version="v1.0",
                    confidence=match_score,
                    policy_id=policy.id if policy else None,
                    policy_version=policy.version if policy else "1.0",
                    decision_status="auto_accepted",
                    explanation=f"Matching de viñeta score {match_score:.2f} >= auto_accept {auto_thresh:.2f}. Aprobado automáticamente.",
                    sheet_id=sheet_id,
                    job_id=job.id
                )
