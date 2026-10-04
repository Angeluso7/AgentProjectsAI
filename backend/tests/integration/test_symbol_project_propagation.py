"""
Test de integración para verificar la propagación de project_id y project_document_id
en DetectedSymbol durante la detección de símbolos en documentos de un proyecto.
"""

import os
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import SessionLocal
from app.db.models.core import User, Organization, OrganizationMembership, Project
from app.db.models.document_memory import Document, DocumentSheet, DetectedSymbol
from app.core.security import create_access_token
from app.services.ingest.service import IngestService
from app.services.symbols.service import SymbolService


def generate_simple_pdf_bytes() -> bytes:
    return (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000052 00000 n\n0000000101 00000 n\n"
        b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n178\n%%EOF\n"
    )


def test_symbol_project_fields_propagation():
    """
    Verifica que al detectar símbolos en un documento perteneciente a un proyecto:
    1. project_id quede poblado con el ID del proyecto.
    2. project_document_id quede poblado con el ID del documento.
    3. record_kind sea 'occurrence'.
    4. Con disciplina 'piping', se generen candidatos heurísticos de piping (gate_valve, piping_line).
    """
    db: Session = SessionLocal()
    suffix = str(uuid.uuid4())[:8]

    try:
        org = Organization(id=f"org-{suffix}", name=f"Org {suffix}", slug=f"org-{suffix}")
        user = User(
            id=f"user-{suffix}",
            email=f"user-{suffix}@test.com",
            display_name=f"User {suffix}",
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
            id=f"prj-{suffix}",
            organization_id=org.id,
            code=f"PRJ-{suffix[:4].upper()}",
            name="Proyecto Piping Test",
            discipline="piping",
            status="active"
        )
        db.add_all([membership, project])
        db.commit()

        # Ingestar documento al proyecto
        pdf_bytes = generate_simple_pdf_bytes()
        ingest_svc = IngestService(db)
        doc = ingest_svc.ingest_pdf(
            project_id=project.id,
            filename="PID-101-Test.pdf",
            file_bytes=pdf_bytes,
            auto_process=True,
            metadata_extra={"discipline": "piping", "document_type": "P&ID"}
        )

        assert doc.id is not None
        assert doc.project_id == project.id
        assert doc.status == "ready"

        # Verificar que se crearon láminas
        sheets = db.query(DocumentSheet).filter(DocumentSheet.document_id == doc.id).all()
        assert len(sheets) >= 1
        sheet = sheets[0]

        # Correr detección de símbolos
        sym_svc = SymbolService(db)
        detected_res = sym_svc.detect_document_symbols(document_id=doc.id, force_reprocess=True)
        assert len(detected_res) > 0
        assert detected_res[0]["symbols_count"] > 0

        # Consultar DetectedSymbol persistidos
        symbols = db.query(DetectedSymbol).filter(DetectedSymbol.document_id == doc.id).all()
        assert len(symbols) > 0

        for sym in symbols:
            # Validaciones críticas del Punto 3
            assert sym.project_id == project.id, f"sym.project_id ({sym.project_id}) != project.id ({project.id})"
            assert sym.project_document_id == doc.id, f"sym.project_document_id ({sym.project_document_id}) != doc.id ({doc.id})"
            assert sym.record_kind == "occurrence"
            assert sym.discipline == "piping"

        symbol_types = [s.symbol_type for s in symbols]
        assert "gate_valve" in symbol_types
        assert "piping_line" in symbol_types

    finally:
        # Cleanup
        try:
            db.query(DetectedSymbol).filter(DetectedSymbol.project_id == f"prj-{suffix}").delete()
            db.query(DocumentSheet).filter(DocumentSheet.document_id == doc.id).delete()
            db.query(Document).filter(Document.id == doc.id).delete()
            db.query(Project).filter(Project.id == f"prj-{suffix}").delete()
            db.query(OrganizationMembership).filter(OrganizationMembership.organization_id == f"org-{suffix}").delete()
            db.query(User).filter(User.id == f"user-{suffix}").delete()
            db.query(Organization).filter(Organization.id == f"org-{suffix}").delete()
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
