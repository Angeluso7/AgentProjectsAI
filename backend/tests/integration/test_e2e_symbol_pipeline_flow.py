"""
Test End-to-End para el Punto 6:
Cierra el gap completo:
1. Sube un documento técnico PDF a un proyecto (P&ID).
2. Verifica que document_sheets se puebla de inmediato.
3. Verifica que detected_symbols se puebla solo de forma asíncrona, con project_id y project_document_id correctos.
4. Ejecuta el One-Click Review (PIPING / PID_SYMBOLS).
5. Confirma que la Fase 4 (Extracción de Tablas y Simbología) ya no está en 0, sin haber pasado por el Visor de Planos.
"""

import os
import time
import uuid
import pytest
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models.core import User, Organization, OrganizationMembership, Project
from app.db.models.document_memory import Document, DocumentSheet, DetectedSymbol
from app.db.models.operations import ProcessingJob
from app.db.models.decision_memory import ReviewRun, ReviewRunStep
from app.services.ingest.service import IngestService
from app.services.review.orchestrator import ReviewOrchestrator
from app.services.review.taxonomy_service import TaxonomyService


def generate_test_pid_bytes(unique_marker: str) -> bytes:
    header = f"%PDF-1.4\n%{unique_marker}\n".encode("latin1")
    body = (
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000052 00000 n\n0000000101 00000 n\n"
        b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n178\n%%EOF\n"
    )
    return header + body


def test_e2e_symbol_detection_and_phase4_review():
    db: Session = SessionLocal()
    suffix = str(uuid.uuid4())[:8]

    try:
        # 1. Crear organización, usuario y proyecto de piping
        org = Organization(id=f"org-e2e-{suffix}", name=f"Org E2E {suffix}", slug=f"org-e2e-{suffix}")
        user = User(
            id=f"user-e2e-{suffix}",
            email=f"user-e2e-{suffix}@test.com",
            display_name=f"User E2E {suffix}",
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
            id=f"prj-e2e-{suffix}",
            organization_id=org.id,
            code=f"PRJ-E{suffix[:3].upper()}",
            name="Proyecto E2E Piping",
            discipline="piping",
            status="active"
        )
        db.add_all([membership, project])
        db.commit()

        # 2. Ingestar documento P&ID al proyecto (sin tocar botones de visor)
        pdf_bytes = generate_test_pid_bytes(suffix)
        ingest_svc = IngestService(db)
        doc = ingest_svc.ingest_pdf(
            project_id=project.id,
            filename=f"PID-100-E2E-{suffix}.pdf",
            file_bytes=pdf_bytes,
            auto_process=True,
            metadata_extra={"discipline": "piping", "document_type": "P&ID"}
        )

        assert doc.id is not None
        assert doc.status == "ready"

        # Confirmación 1: document_sheets se pobló
        sheets = db.query(DocumentSheet).filter(DocumentSheet.document_id == doc.id).all()
        assert len(sheets) >= 1, "document_sheets debe estar poblado tras el upload"

        # Esperar a que el job asíncrono document_symbol_detect complete
        max_wait = 20
        start_time = time.time()
        job_done = False
        while time.time() - start_time < max_wait:
            time.sleep(0.5)
            # Consultar en sesión limpia
            poll_db = SessionLocal()
            try:
                job = (
                    poll_db.query(ProcessingJob)
                    .filter(ProcessingJob.target_id == doc.id, ProcessingJob.job_type == "document_symbol_detect")
                    .order_by(ProcessingJob.created_at.desc())
                    .first()
                )
                if job and job.status in ["completed", "failed"]:
                    job_done = True
                    assert job.status == "completed", f"Job falló: {job.error_message}"
                    break
            finally:
                poll_db.close()

        assert job_done, "El job asíncrono de detección de símbolos no finalizó a tiempo"

        # Confirmación 2: detected_symbols se pobló solo, con project_id y project_document_id
        symbols = db.query(DetectedSymbol).filter(DetectedSymbol.document_id == doc.id).all()
        assert len(symbols) > 0, "detected_symbols debe haberse poblado automáticamente"

        for sym in symbols:
            assert sym.project_id == project.id, "project_id debe coincidir con el proyecto"
            assert sym.project_document_id == doc.id, "project_document_id debe coincidir con el doc"
            assert sym.discipline == "piping"
            assert sym.record_kind == "occurrence"
            assert sym.crop_image_path is not None
            assert os.path.exists(sym.crop_image_path), f"El recorte {sym.crop_image_path} debe existir físicamente"

        # Asegurar que existan las taxonomías y reglas de PIPING / PID_SYMBOLS
        TaxonomyService.seed_taxonomy_and_rules(db)

        # Confirmación 3: Ejecutar One-Click Review y confirmar que Fase 4 ya no está en 0
        res = ReviewOrchestrator.execute_review_run(
            db=db,
            project_id=project.id,
            discipline_code="PIPING",
            topic_code="PID_SYMBOLS",
            document_ids=[doc.id],
            mode="sandbox",
            requested_by="e2e_tester",
            run_name="E2E Pipeline Test Run"
        )
        run_id = res["review_run_id"] if isinstance(res, dict) else res.review_run_id

        step4 = (
            db.query(ReviewRunStep)
            .filter(ReviewRunStep.review_run_id == run_id, ReviewRunStep.phase == 4)
            .first()
        )
        assert step4 is not None, "El paso 4 debe existir en la corrida"
        assert step4.status == "succeeded"

        out4 = step4.output_summary or {}
        valid_occurrences = out4.get("valid_symbol_occurrences", 0)
        groups_count = out4.get("inventory_groups_count", 0)

        # La Fase 4 ya no está en 0
        assert valid_occurrences > 0, f"Fase 4 valid_symbol_occurrences debe ser > 0, pero es {valid_occurrences}"
        assert groups_count > 0, f"Fase 4 inventory_groups_count debe ser > 0, pero es {groups_count}"

    finally:
        try:
            db.query(ReviewRunStep).filter(ReviewRunStep.review_run_id == run_id).delete() if 'run_id' in locals() else None
            db.query(ReviewRun).filter(ReviewRun.id == run_id).delete() if 'run_id' in locals() else None
            db.query(DetectedSymbol).filter(DetectedSymbol.project_id == f"prj-e2e-{suffix}").delete()
            db.query(ProcessingJob).filter(ProcessingJob.project_id == f"prj-e2e-{suffix}").delete()
            db.query(DocumentSheet).filter(DocumentSheet.document_id == doc.id).delete() if 'doc' in locals() else None
            db.query(Document).filter(Document.id == doc.id).delete() if 'doc' in locals() else None
            db.query(Project).filter(Project.id == f"prj-e2e-{suffix}").delete()
            db.query(OrganizationMembership).filter(OrganizationMembership.organization_id == f"org-e2e-{suffix}").delete()
            db.query(User).filter(User.id == f"user-e2e-{suffix}").delete()
            db.query(Organization).filter(Organization.id == f"org-e2e-{suffix}").delete()
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
