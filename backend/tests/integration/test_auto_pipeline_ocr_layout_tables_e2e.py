"""
Test de integración End-to-End para el pipeline automático:
Ingesta -> OCR -> Layout -> Tablas -> Símbolos -> One-Click Review con datos reales.
"""

import os
import time
import uuid
import pytest
import fitz
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models.core import User, Organization, OrganizationMembership, Project
from app.db.models.decision_memory import ReviewDiscipline, ReviewTopic, RuleDefinition
from app.db.models.document_memory import (
    Document, DocumentSheet, ExtractedText, SheetRegion,
    TitleBlockExtraction, ExtractedTable, DetectedSymbol
)
from app.db.models.operations import ProcessingJob
from app.services.ingest.service import IngestService
from app.services.review.orchestrator import ReviewOrchestrator
from app.services.operations.dispatcher import wait_for_all_jobs


def create_pid_synthetic_pdf(filepath: str):
    """Genera un PDF técnico con viñeta completa, cuadro de válvulas y notas en drawing_area."""
    doc = fitz.open()
    page = doc.new_page(width=1000, height=800)

    # 1. Drawing area texts (zona izquierda/centro)
    page.insert_text(fitz.Point(100, 100), "SISTEMA DE DISTRIBUCION DE GAS")
    page.insert_text(fitz.Point(100, 150), "LINEA PRINCIPAL 6-CW-101-CS150")
    page.insert_text(fitz.Point(100, 200), "VALVULA DE CORTE HV-101 GATE VALVE")

    # 2. Cuadro de válvulas (zona superior derecha / tabla)
    page.insert_text(fitz.Point(600, 100), "CUADRO DE VALVULAS")
    page.insert_text(fitz.Point(600, 130), "TAG      TIPO        DIAMETRO")
    page.insert_text(fitz.Point(600, 160), "HV-101   COMPUERTA   2 INCH")
    page.insert_text(fitz.Point(600, 190), "CV-102   RETENCION   2 INCH")

    # 3. Viñeta técnica (esquina inferior derecha: x > 700, y > 600)
    page.insert_text(fitz.Point(720, 650), "PROYECTO: PLANTA GAS SUR")
    page.insert_text(fitz.Point(720, 680), "DISCIPLINA: PIPING")
    page.insert_text(fitz.Point(720, 710), "ESCALA: 1:50")
    page.insert_text(fitz.Point(720, 740), "REV: B")
    page.insert_text(fitz.Point(720, 770), "PLANO: PID-GAS-001")

    doc.save(filepath)
    doc.close()


def test_auto_pipeline_ocr_layout_tables_and_review(tmp_path):
    """
    Verifica end-to-end:
    1. Ingesta con auto_process=True ejecuta la cadena OCR -> Layout -> Tablas -> Símbolos.
    2. En BD se pueblan solos: texts, regions, title_block, tables, symbols.
    3. Símbolos quedan restringidos a drawing_area.
    4. One-Click Review evalúa Fase 2, 3, 4 reales (succeeded) y evalúa reglas de viñeta con datos reales.
    """
    db: Session = SessionLocal()
    suffix = str(uuid.uuid4())[:8]
    pdf_path = str(tmp_path / f"PID-GAS-{suffix}.pdf")
    create_pid_synthetic_pdf(pdf_path)

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    try:
        org = Organization(id=f"org-pipe-{suffix}", name=f"Org Pipe {suffix}", slug=f"org-pipe-{suffix}")
        user = User(
            id=f"user-pipe-{suffix}",
            email=f"user-pipe-{suffix}@test.com",
            display_name=f"User Pipe {suffix}",
            password_hash="fake",
            is_active=True
        )
        db.add_all([org, user])
        db.commit()

        membership = OrganizationMembership(
            organization_id=org.id,
            user_id=user.id,
            role="admin",
            status="active"
        )
        project = Project(
            id=f"prj-pipe-{suffix}",
            organization_id=org.id,
            code=f"PRJ-P{suffix[:3].upper()}",
            name="Proyecto Gas Pipeline Test",
            discipline="piping",
            status="active"
        )
        db.add_all([membership, project])
        db.commit()

        # Ingesta con auto_process=True
        ingest_svc = IngestService(db)
        doc = ingest_svc.ingest_pdf(
            project_id=project.id,
            filename=f"PID-GAS-{suffix}.pdf",
            file_bytes=pdf_bytes,
            auto_process=True,
            metadata_extra={"discipline": "piping", "document_type": "P&ID"}
        )

        assert doc.id is not None
        assert doc.status == "ready"

        # Esperar a que la cadena asíncrona completa termine
        max_wait = 60
        start_time = time.time()
        chain_completed = False

        while time.time() - start_time < max_wait:
            db.expire_all()
            all_jobs = db.query(ProcessingJob).filter(ProcessingJob.target_id == doc.id).all()
            job_states = [(j.job_type, j.status, j.current_stage, j.error_message) for j in all_jobs]
            print(f"[{time.time()-start_time:.1f}s] Document jobs: {job_states}")
            sym_job = next((j for j in all_jobs if j.job_type == "document_symbol_detect"), None)
            if sym_job and sym_job.status in ["completed", "failed"]:
                assert sym_job.status == "completed", f"Job simbología falló: {sym_job.error_message}"
                chain_completed = True
                break
            time.sleep(1.0)

        assert chain_completed, "La cadena asíncrona de intake no finalizó en el tiempo esperado"

        sheet = db.query(DocumentSheet).filter(DocumentSheet.document_id == doc.id).first()
        assert sheet is not None

        # 1. Verificar extracted_texts
        texts = db.query(ExtractedText).filter(ExtractedText.sheet_id == sheet.id).all()
        assert len(texts) >= 5, f"Se esperaban múltiples bloques de texto OCR, se encontraron {len(texts)}"
        all_text_content = " ".join(t.clean_text or t.text for t in texts)
        assert "PID-GAS-001" in all_text_content
        assert "CUADRO DE VALVULAS" in all_text_content

        # 2. Verificar sheet_regions
        regions = db.query(SheetRegion).filter(SheetRegion.sheet_id == sheet.id).all()
        assert len(regions) >= 2, f"Se esperaban al menos 2 regiones, se encontraron {len(regions)}"
        reg_types = [r.region_type for r in regions]
        assert "drawing_area" in reg_types
        assert "title_block" in reg_types

        # 3. Verificar title_block_extractions
        tb = db.query(TitleBlockExtraction).filter(TitleBlockExtraction.sheet_id == sheet.id).first()
        assert tb is not None, "No se extrajo la viñeta técnica"
        assert tb.sheet_code is not None and "PID-GAS-001" in tb.sheet_code.upper()
        assert tb.revision is not None and tb.revision.upper() == "B"
        assert tb.scale_text is not None and "1:50" in tb.scale_text

        # 4. Verificar extracted_tables
        tables = db.query(ExtractedTable).filter(ExtractedTable.sheet_id == sheet.id).all()
        assert len(tables) >= 1, "No se extrajo el cuadro de válvulas como tabla"
        assert tables[0].table_type in ["valve_schedule", "material_list", "unknown_schedule", "doors_windows"]

        # 5. Verificar detected_symbols
        symbols = db.query(DetectedSymbol).filter(DetectedSymbol.document_id == doc.id).all()
        assert len(symbols) > 0, "No se detectaron símbolos"
        drawing_region = next((r for r in regions if r.region_type == "drawing_area"), None)
        assert drawing_region is not None
        for sym in symbols:
            # Debe estar vinculado a drawing_area
            assert sym.region_id == drawing_region.id

        # 6. Ejecutar One-Click Review y verificar Fases 2-4 y evaluación con datos reales
        from app.services.review.taxonomy_service import TaxonomyService
        TaxonomyService.seed_taxonomy_and_rules(db)

        review_res = ReviewOrchestrator.execute_review_run(
            db=db,
            project_id=project.id,
            discipline_code="PIPING",
            topic_code="PID_SYMBOLS",
            document_ids=[doc.id],
            mode="sandbox",
            requested_by="tester"
        )

        assert review_res["status"] in ["completed", "running"]

        # Verificar ReviewRunSteps
        from app.db.models.decision_memory import ReviewRunStep, RuleExecution
        steps = db.query(ReviewRunStep).filter(ReviewRunStep.review_run_id == review_res["review_run_id"]).all()
        steps_by_phase = {s.phase: s for s in steps}

        assert steps_by_phase[2].status == "succeeded"
        assert steps_by_phase[2].output_summary.get("ocr_status") == "ready"

        assert steps_by_phase[3].status == "succeeded"
        assert steps_by_phase[3].output_summary.get("layout_status") == "ready"

        assert steps_by_phase[4].status == "succeeded"

        # Verificar que las reglas de viñeta se evaluaron con datos reales
        rule_execs = db.query(RuleExecution).filter(RuleExecution.review_run_id == review_res["review_run_id"]).all()
        for rx in rule_execs:
            # Ninguna regla debe fallar por MISSING_TITLE_BLOCK ni falta de artefactos
            assert rx.not_evaluable_reason_code != "MISSING_TITLE_BLOCK"

    finally:
        try:
            db.query(DetectedSymbol).filter(DetectedSymbol.project_id == f"prj-pipe-{suffix}").delete()
            db.query(ExtractedTable).filter(ExtractedTable.sheet_id == sheet.id).delete()
            db.query(TitleBlockExtraction).filter(TitleBlockExtraction.sheet_id == sheet.id).delete()
            db.query(SheetRegion).filter(SheetRegion.sheet_id == sheet.id).delete()
            db.query(ExtractedText).filter(ExtractedText.sheet_id == sheet.id).delete()
            db.query(ProcessingJob).filter(ProcessingJob.project_id == f"prj-pipe-{suffix}").delete()
            db.query(DocumentSheet).filter(DocumentSheet.document_id == doc.id).delete()
            db.query(Document).filter(Document.id == doc.id).delete()
            db.query(Project).filter(Project.id == f"prj-pipe-{suffix}").delete()
            db.query(OrganizationMembership).filter(OrganizationMembership.organization_id == f"org-pipe-{suffix}").delete()
            db.query(User).filter(User.id == f"user-pipe-{suffix}").delete()
            db.query(Organization).filter(Organization.id == f"org-pipe-{suffix}").delete()
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
