import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.db.models.document_memory import (
    Document, DocumentSheet, SheetRegion, TitleBlockExtraction,
    ExtractedText, ExtractedTable, DetectedSymbol
)
from app.db.models.operations import (
    ReviewPipelineRun, PipelineStageRun, ProcessingJob, ReviewTask, DecisionTrace
)
from app.db.models.reporting import AuditReport
from app.db.repositories.document_repository import DocumentRepository
from app.db.repositories.operations_repository import OperationsRepository
from app.services.ocr.service import OcrService
from app.services.layout.service import LayoutService
from app.services.tables.service import TableService
from app.services.symbols.service import SymbolService
from app.services.rules.engine import RuleEngine
from app.services.reporting.service import ReportingService
from app.core.logging import logger

PIPELINE_STAGES = [
    ("ingest", 1),
    ("ocr", 2),
    ("layout", 3),
    ("title_block", 4),
    ("tables", 5),
    ("symbols", 6),
    ("rules", 7),
    ("reports", 8)
]

class ReviewPipelineService:
    """Orquestador de auditoría integral One-Click End-to-End para láminas y documentos."""

    def __init__(self, db: Session):
        self.db = db
        self.doc_repo = DocumentRepository(db)
        self.ops_repo = OperationsRepository(db)

    def create_pipeline_run(
        self,
        scope_type: str,
        scope_id: str,
        requested_by: str = "auditor_qa",
        force_reprocess: bool = False,
        organization_id: Optional[str] = None
    ) -> ReviewPipelineRun:
        """Crea e inicializa el registro del pipeline run y sus 8 etapas con control de locks y aislamiento multi-tenant."""
        if scope_type == "document":
            doc = self.doc_repo.get_by_id(scope_id)
            if not doc:
                raise ValueError(f"Documento '{scope_id}' no encontrado.")
            if organization_id and doc.organization_id and doc.organization_id != organization_id:
                raise ValueError(f"Documento '{scope_id}' no pertenece a la organización autorizada.")
            resolved_org_id = organization_id or doc.organization_id or "default-org-uuid"
        elif scope_type == "sheet":
            sheet = self.doc_repo.get_sheet_by_id(scope_id)
            if not sheet:
                raise ValueError(f"Lámina '{scope_id}' no encontrada.")
            doc = sheet.document
            if organization_id and doc and doc.organization_id and doc.organization_id != organization_id:
                raise ValueError(f"Lámina '{scope_id}' no pertenece a la organización autorizada.")
            resolved_org_id = organization_id or (doc.organization_id if doc else "default-org-uuid")
        else:
            raise ValueError(f"Alcance de pipeline '{scope_type}' no soportado.")

        # Control de Concurrencia & Expiración de Locks Huérfanos (30 min)
        active_runs = self.db.query(ReviewPipelineRun).filter(
            ReviewPipelineRun.organization_id == resolved_org_id,
            ReviewPipelineRun.scope_type == scope_type,
            ReviewPipelineRun.scope_id == scope_id,
            ReviewPipelineRun.status.in_(["queued", "running"])
        ).all()

        now = datetime.utcnow()
        for ar in active_runs:
            updated = ar.updated_at or ar.created_at
            # Si el lock tiene más de 30 minutos sin actividad, se considera huérfano y se libera
            if (now - updated).total_seconds() > 1800:
                logger.warning(f"Liberando lock huérfano de pipeline {ar.id} (inactivo por >30 min)")
                ar.status = "failed"
                ar.failed_at = now
                ar.summary = {"error": "Timeout de ejecución / lock huérfano liberado"}
                self.db.commit()
            elif not force_reprocess:
                raise ValueError(
                    f"Existe un pipeline activo ({ar.status}) para este {scope_type}. ID: {ar.id}"
                )

        pipeline_run = ReviewPipelineRun(
            organization_id=resolved_org_id,
            scope_type=scope_type,
            scope_id=scope_id,
            pipeline_version="v1.0",
            requested_by=requested_by,
            status="queued",
            current_stage="ingest",
            progress_percent=0,
            summary={"force_reprocess": force_reprocess, "total_stages": len(PIPELINE_STAGES)}
        )
        self.db.add(pipeline_run)
        self.db.commit()
        self.db.refresh(pipeline_run)

        # Crear registros iniciales de cada etapa
        for stage_name, stage_order in PIPELINE_STAGES:
            stage_run = PipelineStageRun(
                pipeline_run_id=pipeline_run.id,
                stage_name=stage_name,
                stage_order=stage_order,
                status="pending"
            )
            self.db.add(stage_run)
        self.db.commit()
        self.db.refresh(pipeline_run)

        return pipeline_run

    def execute_pipeline(
        self,
        pipeline_run_id: str,
        force_reprocess: bool = False
    ) -> ReviewPipelineRun:
        """Ejecuta secuencialmente todas las etapas del pipeline con control de idempotencia y errores."""
        pipeline_run = self.db.query(ReviewPipelineRun).filter(ReviewPipelineRun.id == pipeline_run_id).first()
        if not pipeline_run:
            raise ValueError(f"Pipeline run '{pipeline_run_id}' no encontrado.")

        if pipeline_run.status == "cancelled":
            return pipeline_run

        pipeline_run.status = "running"
        pipeline_run.started_at = datetime.utcnow()
        self.db.commit()

        try:
            # =========================================================================
            # ETAPA 1: INGEST
            # =========================================================================
            self._execute_stage(pipeline_run, "ingest", 1, 10, self._run_ingest_stage, force_reprocess)

            # =========================================================================
            # ETAPA 2: OCR ESPACIAL
            # =========================================================================
            self._execute_stage(pipeline_run, "ocr", 2, 25, self._run_ocr_stage, force_reprocess)

            # =========================================================================
            # ETAPA 3: LAYOUT MACRO-REGIONAL
            # =========================================================================
            self._execute_stage(pipeline_run, "layout", 3, 40, self._run_layout_stage, force_reprocess)

            # =========================================================================
            # ETAPA 4: TITLE BLOCK MATCHING & EXTRACTION
            # =========================================================================
            self._execute_stage(pipeline_run, "title_block", 4, 55, self._run_title_block_stage, force_reprocess)

            # =========================================================================
            # ETAPA 5: EXTRACCIÓN TABULAR
            # =========================================================================
            self._execute_stage(pipeline_run, "tables", 5, 70, self._run_tables_stage, force_reprocess)

            # =========================================================================
            # ETAPA 6: DETECCIÓN DE SÍMBOLOS VISUALES
            # =========================================================================
            self._execute_stage(pipeline_run, "symbols", 6, 80, self._run_symbols_stage, force_reprocess)

            # =========================================================================
            # ETAPA 7: EVALUACIÓN DE REGLAS QA/QC
            # =========================================================================
            rules_res = self._execute_stage(pipeline_run, "rules", 7, 90, self._run_rules_stage, force_reprocess)

            # =========================================================================
            # ETAPA 8: GENERACIÓN DE REPORTE TÉCNICO & BUNDLE
            # =========================================================================
            rep_res = self._execute_stage(pipeline_run, "reports", 8, 100, self._run_reports_stage, force_reprocess)

            # Cierre Exitoso del Pipeline
            pipeline_run.final_report_id = rep_res.get("report_id") if isinstance(rep_res, dict) else None
            pipeline_run.status = "completed"
            pipeline_run.current_stage = "completed"
            pipeline_run.progress_percent = 100
            pipeline_run.completed_at = datetime.utcnow()
            
            # Si hay ReviewTasks abiertas derivadas de las reglas, marcar awaiting_review
            open_tasks = self.db.query(ReviewTask).filter(
                ReviewTask.document_id == (pipeline_run.scope_id if pipeline_run.scope_type == "document" else None),
                ReviewTask.status == "open"
            ).count()
            if open_tasks > 0:
                pipeline_run.status = "awaiting_review"

            pipeline_run.summary = {
                "final_report_id": pipeline_run.final_report_id,
                "findings_count": rules_res.get("findings_count", 0) if isinstance(rules_res, dict) else 0,
                "open_review_tasks": open_tasks,
                "status": pipeline_run.status
            }
            self.db.commit()

        except Exception as e:
            logger.error(f"Error crítico en pipeline {pipeline_run.id}: {str(e)}")
            pipeline_run.status = "failed"
            pipeline_run.failed_at = datetime.utcnow()
            pipeline_run.summary = {"error": str(e), "failed_stage": pipeline_run.current_stage}
            self.db.commit()

        return pipeline_run

    def _execute_stage(
        self,
        pipeline_run: ReviewPipelineRun,
        stage_name: str,
        stage_order: int,
        target_progress: int,
        stage_func: Any,
        force_reprocess: bool
    ) -> Any:
        stage_run = self.db.query(PipelineStageRun).filter(
            PipelineStageRun.pipeline_run_id == pipeline_run.id,
            PipelineStageRun.stage_name == stage_name
        ).first()

        pipeline_run.current_stage = stage_name
        if stage_run:
            stage_run.status = "running"
            stage_run.started_at = datetime.utcnow()
        self.db.commit()

        try:
            result = stage_func(pipeline_run.scope_type, pipeline_run.scope_id, force_reprocess)
            if stage_run:
                stage_run.status = "completed"
                stage_run.completed_at = datetime.utcnow()
                stage_run.result_summary = result if isinstance(result, dict) else {"result": str(result)}
            pipeline_run.progress_percent = target_progress
            self.db.commit()
            return result
        except Exception as e:
            if stage_run:
                stage_run.status = "failed"
                stage_run.completed_at = datetime.utcnow()
                stage_run.error_message = str(e)
            self.db.commit()
            raise e

    # =========================================================================
    # EJECUTORES DE ETAPAS CON IDEMPOTENCIA
    # =========================================================================
    def _run_ingest_stage(self, scope_type: str, scope_id: str, force: bool) -> Dict[str, Any]:
        if scope_type == "document":
            doc = self.doc_repo.get_by_id(scope_id)
            sheets = self.doc_repo.list_sheets_by_document(scope_id)
            if not sheets:
                raise ValueError("El documento no tiene láminas ingestadas.")
            return {"sheets_count": len(sheets), "status": "verified"}
        else:
            sheet = self.doc_repo.get_sheet_by_id(scope_id)
            if not sheet:
                raise ValueError(f"Lámina {scope_id} no encontrada.")
            return {"sheet_id": sheet.id, "status": "verified"}

    def _run_ocr_stage(self, scope_type: str, scope_id: str, force: bool) -> Dict[str, Any]:
        ocr_svc = OcrService(self.db)
        if scope_type == "document":
            return ocr_svc.process_document_ocr(document_id=scope_id, force_reprocess=force)
        else:
            texts = ocr_svc.process_sheet_ocr(sheet_id=scope_id, force_reprocess=force)
            return {"sheet_id": scope_id, "texts_count": len(texts)}

    def _run_layout_stage(self, scope_type: str, scope_id: str, force: bool) -> Dict[str, Any]:
        layout_svc = LayoutService(self.db)
        if scope_type == "document":
            res = layout_svc.segment_document_layout(document_id=scope_id, force_reprocess=force)
            return {"document_id": scope_id, "sheets_segmented": len(res)}
        else:
            regions = layout_svc.segment_sheet_layout(sheet_id=scope_id, force_reprocess=force)
            return {"sheet_id": scope_id, "regions_count": len(regions)}

    def _run_title_block_stage(self, scope_type: str, scope_id: str, force: bool) -> Dict[str, Any]:
        layout_svc = LayoutService(self.db)
        if scope_type == "document":
            sheets = self.doc_repo.list_sheets_by_document(scope_id)
            matched = 0
            for s in sheets:
                tb = layout_svc.match_and_extract_title_block(sheet_id=s.id, force_reprocess=force)
                if tb:
                    matched += 1
            return {"sheets_matched": matched}
        else:
            tb = layout_svc.match_and_extract_title_block(sheet_id=scope_id, force_reprocess=force)
            return {"title_block_id": tb.id if tb else None, "score": tb.match_score if tb else 0.0}

    def _run_tables_stage(self, scope_type: str, scope_id: str, force: bool) -> Dict[str, Any]:
        table_svc = TableService(self.db)
        if scope_type == "document":
            res = table_svc.extract_document_tables(document_id=scope_id, force_reprocess=force)
            return {"document_id": scope_id, "sheets_processed": len(res)}
        else:
            tables = table_svc.extract_sheet_tables(sheet_id=scope_id, force_reprocess=force)
            return {"sheet_id": scope_id, "tables_count": len(tables)}

    def _run_symbols_stage(self, scope_type: str, scope_id: str, force: bool) -> Dict[str, Any]:
        sym_svc = SymbolService(self.db)
        if scope_type == "document":
            res = sym_svc.detect_document_symbols(document_id=scope_id, force_reprocess=force)
            return {"document_id": scope_id, "sheets_processed": len(res)}
        else:
            syms = sym_svc.detect_sheet_symbols(sheet_id=scope_id, force_reprocess=force)
            return {"sheet_id": scope_id, "symbols_count": len(syms)}

    def _run_rules_stage(self, scope_type: str, scope_id: str, force: bool) -> Dict[str, Any]:
        rule_engine = RuleEngine(self.db)
        if scope_type == "document":
            res = rule_engine.evaluate_document(document_id=scope_id)
            total_findings = sum(r["findings_count"] for r in res)
            return {"document_id": scope_id, "findings_count": total_findings, "details": res}
        else:
            findings = rule_engine.evaluate_sheet(sheet_id=scope_id)
            return {"sheet_id": scope_id, "findings_count": len(findings)}

    def _run_reports_stage(self, scope_type: str, scope_id: str, force: bool) -> Dict[str, Any]:
        rep_svc = ReportingService(self.db)
        if scope_type == "document":
            rep = rep_svc.generate_document_report(document_id=scope_id, report_type="technical_audit_qaqc")
        else:
            rep = rep_svc.generate_sheet_report(sheet_id=scope_id, report_type="technical_audit_qaqc")
        
        return {
            "report_id": rep.id,
            "pdf_path": rep.artifact_pdf_path,
            "json_path": rep.artifact_json_path,
            "bundle_path": rep.artifact_bundle_path,
            "manifest_hash": rep.manifest_hash
        }

    def retry_pipeline(self, pipeline_run_id: str) -> ReviewPipelineRun:
        """Reinicia la ejecución de un pipeline fallido o cancelado."""
        pipeline_run = self.db.query(ReviewPipelineRun).filter(ReviewPipelineRun.id == pipeline_run_id).first()
        if not pipeline_run:
            raise ValueError(f"Pipeline run '{pipeline_run_id}' no encontrado.")
        
        return self.execute_pipeline(pipeline_run_id=pipeline_run.id, force_reprocess=True)

    def cancel_pipeline(self, pipeline_run_id: str) -> ReviewPipelineRun:
        """Cancela la ejecución de un pipeline activo."""
        pipeline_run = self.db.query(ReviewPipelineRun).filter(ReviewPipelineRun.id == pipeline_run_id).first()
        if not pipeline_run:
            raise ValueError(f"Pipeline run '{pipeline_run_id}' no encontrado.")
        
        pipeline_run.status = "cancelled"
        pipeline_run.cancelled_at = datetime.utcnow()
        self.db.commit()
        return pipeline_run

    def get_pipeline_run(self, pipeline_run_id: str) -> Optional[ReviewPipelineRun]:
        return self.db.query(ReviewPipelineRun).filter(ReviewPipelineRun.id == pipeline_run_id).first()

    def list_pipeline_runs(
        self,
        scope_type: Optional[str] = None,
        scope_id: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[ReviewPipelineRun]:
        query = self.db.query(ReviewPipelineRun)
        if scope_type:
            query = query.filter(ReviewPipelineRun.scope_type == scope_type)
        if scope_id:
            query = query.filter(ReviewPipelineRun.scope_id == scope_id)
        if status:
            query = query.filter(ReviewPipelineRun.status == status)
        return query.order_by(ReviewPipelineRun.created_at.desc()).all()
