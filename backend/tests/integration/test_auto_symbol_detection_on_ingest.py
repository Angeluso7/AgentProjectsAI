"""
Test de integración para verificar el disparo automático y asíncrono de detección
de símbolos y matching de catálogo al ingestar documentos en un proyecto.
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
from app.services.ingest.service import IngestService
from app.services.symbols.canonical_catalog_service import CanonicalPipingCatalogService


def generate_simple_pdf_bytes() -> bytes:
    return (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000052 00000 n\n0000000101 00000 n\n"
        b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n178\n%%EOF\n"
    )


def test_auto_symbol_detection_and_matching_on_ingest():
    """
    Verifica que al subir un documento técnico en IngestService:
    1. Se encola un job asíncrono 'document_symbol_detect'.
    2. El worker ejecuta el job y puebla detected_symbols automáticamente.
    3. Cada símbolo detectado tiene project_id, project_document_id y recortes generados.
    4. Se dispara el auto-matching contra el catálogo canónico:
       - Si no hay catálogo activo para la disciplina, queda explícito con
         matching_status='unknown_symbol' y catalog_status='no_active_catalog'.
    """
    db: Session = SessionLocal()
    suffix = str(uuid.uuid4())[:8]

    try:
        org = Organization(id=f"org-auto-{suffix}", name=f"Org Auto {suffix}", slug=f"org-auto-{suffix}")
        user = User(
            id=f"user-auto-{suffix}",
            email=f"user-auto-{suffix}@test.com",
            display_name=f"User Auto {suffix}",
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
            id=f"prj-auto-{suffix}",
            organization_id=org.id,
            code=f"PRJ-A{suffix[:3].upper()}",
            name="Proyecto Ingesta Auto Test",
            discipline="piping",
            status="active"
        )
        db.add_all([membership, project])
        db.commit()

        # Ingestar documento al proyecto (auto_process=True rasteriza y dispara el job asíncrono)
        pdf_bytes = generate_simple_pdf_bytes()
        ingest_svc = IngestService(db)
        doc = ingest_svc.ingest_pdf(
            project_id=project.id,
            filename=f"PID-Auto-{suffix}.pdf",
            file_bytes=pdf_bytes,
            auto_process=True,
            metadata_extra={"discipline": "piping", "document_type": "P&ID"}
        )

        assert doc.id is not None
        assert doc.status == "ready"
        assert doc.page_count >= 1

        # Verificar que se creó el job en ProcessingJob
        jobs = (
            db.query(ProcessingJob)
            .filter(
                ProcessingJob.target_id == doc.id,
                ProcessingJob.job_type == "document_symbol_detect"
            )
            .all()
        )
        assert len(jobs) >= 1, "No se encontró el job asíncrono document_symbol_detect"

        # Esperar brevemente a que el worker en thread pool complete el job (hasta 15 seg)
        max_wait = 15
        start_time = time.time()
        job_completed = False
        while time.time() - start_time < max_wait:
            db.expire_all()
            job = db.query(ProcessingJob).filter(ProcessingJob.id == jobs[0].id).first()
            if job and job.status in ["completed", "failed"]:
                job_completed = True
                assert job.status == "completed", f"Job falló con error: {job.error_message}"
                break
            time.sleep(0.5)

        assert job_completed, "El job asíncrono document_symbol_detect no finalizó en el tiempo esperado"

        # Verificar detected_symbols creados automáticamente
        symbols = db.query(DetectedSymbol).filter(DetectedSymbol.document_id == doc.id).all()
        assert len(symbols) > 0, "No se poblaron símbolos detectados automáticamente"

        for sym in symbols:
            # Validaciones de vinculación al proyecto
            assert sym.project_id == project.id
            assert sym.project_document_id == doc.id
            assert sym.discipline == "piping"
            assert sym.record_kind == "occurrence"

            # Validación de recortes físicos generados
            assert sym.symbol_crop_bbox is not None
            assert len(sym.symbol_crop_bbox) == 4
            assert sym.crop_image_path is not None
            assert os.path.exists(sym.crop_image_path), f"El archivo de recorte {sym.crop_image_path} no existe en disco"

            # Validación de auto-matching (Punto 5)
            # El símbolo no debe quedar en silencio en 'unmatched'
            assert sym.matching_status in ["matched", "unknown_symbol", "ambiguous"]
            if sym.matching_status == "unknown_symbol" and sym.match_evidence:
                # Si no había catálogo activo, debe estar explícito
                cat_status = sym.match_evidence.get("catalog_status")
                rej_reason = sym.match_evidence.get("rejection_reason")
                if cat_status == "no_active_catalog":
                    assert "No existe catálogo canónico activo" in rej_reason

    finally:
        try:
            db.query(DetectedSymbol).filter(DetectedSymbol.project_id == f"prj-auto-{suffix}").delete()
            db.query(ProcessingJob).filter(ProcessingJob.project_id == f"prj-auto-{suffix}").delete()
            db.query(DocumentSheet).filter(DocumentSheet.document_id == doc.id).delete()
            db.query(Document).filter(Document.id == doc.id).delete()
            db.query(Project).filter(Project.id == f"prj-auto-{suffix}").delete()
            db.query(OrganizationMembership).filter(OrganizationMembership.organization_id == f"org-auto-{suffix}").delete()
            db.query(User).filter(User.id == f"user-auto-{suffix}").delete()
            db.query(Organization).filter(Organization.id == f"org-auto-{suffix}").delete()
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
