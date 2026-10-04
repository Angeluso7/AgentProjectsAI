import pytest
import uuid
import os
import tempfile
from fastapi.testclient import TestClient
from app.db.models.core import User, Organization, OrganizationMembership, Project, AuditLog
from app.db.models.document_memory import Document, DocumentSheet, ExtractedText, SheetRegion
from app.db.models.decision_memory import RuleFinding
from app.core.security import hash_password, create_access_token

def test_document_impact_and_deletion(client: TestClient, db_session):
    # 1. Crear Organización, Proyecto y Usuarios (Admin y Reviewer)
    org_id = str(uuid.uuid4())
    org = Organization(id=org_id, name="Test Org", slug=f"test-org-{uuid.uuid4().hex[:6]}")
    db_session.add(org)

    admin_user = User(
        id=str(uuid.uuid4()),
        email="admin_del@test.com",
        display_name="Admin Del",
        password_hash=hash_password("admin123456"),
        is_active=True,
        is_superuser=True
    )
    db_session.add(admin_user)
    
    membership = OrganizationMembership(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        user_id=admin_user.id,
        role="admin",
        status="active"
    )
    db_session.add(membership)

    project = Project(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        code="PRJ-DEL-01",
        name="Proyecto Deletion Test",
        discipline="architecture"
    )
    db_session.add(project)

    # 2. Crear Documento con dependencias reales
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
        tmp_pdf.write(b"%PDF-1.4 test document content")
        pdf_path = tmp_pdf.name

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_png:
        tmp_png.write(b"PNG fake raster")
        png_path = tmp_png.name

    doc = Document(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        project_id=project.id,
        filename="plano_arquitectura_01.pdf",
        file_path=pdf_path,
        file_hash_sha256="fake_sha256_hash_12345",
        file_size_bytes=1024,
        mime_type="application/pdf",
        page_count=1,
        status="ready"
    )
    db_session.add(doc)

    sheet = DocumentSheet(
        id=str(uuid.uuid4()),
        document_id=doc.id,
        sheet_number=1,
        sheet_code="ARQ-01",
        title="Planta Baja",
        width_px=1000,
        height_px=800,
        dpi=150,
        raster_image_path=png_path
    )
    db_session.add(sheet)

    text_block = ExtractedText(
        id=str(uuid.uuid4()),
        sheet_id=sheet.id,
        text="PUERTA ACCESO P-1",
        bbox=[100, 100, 200, 150],
        bbox_normalized=[0.1, 0.1, 0.2, 0.15],
        confidence=0.98,
        source="vector_pdf"
    )
    db_session.add(text_block)

    region = SheetRegion(
        id=str(uuid.uuid4()),
        sheet_id=sheet.id,
        region_type="drawing_area",
        polygon_points=[[0,0], [1,0], [1,1], [0,1]],
        bbox=[0,0,1000,800],
        bbox_normalized=[0,0,1,1],
        confidence=1.0
    )
    db_session.add(region)

    finding = RuleFinding(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        document_id=doc.id,
        sheet_id=sheet.id,
        rule_code="ARQ_DOOR_WIDTH_MIN",
        rule_name="Ancho Mínimo de Puertas",
        category="cross_reconciliation",
        severity="high",
        status="open",
        confidence=0.95,
        title="Ancho de vano insuficiente",
        description="Puerta P-1 mide 0.70m (mínimo 0.85m)"
    )
    db_session.add(finding)
    db_session.commit()

    token = create_access_token(admin_user.id, email=admin_user.email, extra_claims={"role": "admin"})
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}


    # 3. Probar GET /api/v1/documents/{id}/impact
    res_impact = client.get(f"/api/v1/documents/{doc.id}/impact", headers=headers)
    assert res_impact.status_code == 200, res_impact.text
    impact_data = res_impact.json()
    assert impact_data["document_id"] == doc.id
    assert impact_data["sheets_count"] == 1
    assert impact_data["ocr_count"] == 1
    assert impact_data["region_count"] == 1
    assert impact_data["findings_count"] == 1
    assert impact_data["severity_breakdown"]["high"] == 1
    assert impact_data["raw_file_exists"] is True

    # 4. Probar Soft-Delete (Archivado)
    res_soft = client.delete(f"/api/v1/documents/{doc.id}?hard_delete=false", headers=headers)
    assert res_soft.status_code == 200
    assert res_soft.json()["delete_type"] == "soft_delete"

    # Verificar que no aparece en list_documents regular
    res_list = client.get(f"/api/v1/documents/?project_id={project.id}", headers=headers)
    assert res_list.status_code == 200
    docs_list = res_list.json()
    assert len(docs_list) == 0

    # Verificar que el finding asociado pasó a status 'dismissed'
    f_db = db_session.query(RuleFinding).filter(RuleFinding.id == finding.id).first()
    assert f_db.status == "dismissed"

    # Verificar registro en AuditLog
    audit_soft = db_session.query(AuditLog).filter(
        AuditLog.entity_id == doc.id,
        AuditLog.action == "soft_delete_archive"
    ).first()
    assert audit_soft is not None

    doc_id_str = doc.id
    sheet_id_str = sheet.id
    finding_id_str = finding.id

    # 5. Probar Hard-Delete (Definitivo)
    res_hard = client.delete(f"/api/v1/documents/{doc_id_str}?hard_delete=true", headers=headers)
    assert res_hard.status_code == 200
    hard_data = res_hard.json()
    assert hard_data["delete_type"] == "hard_delete"

    # Expire and query fresh
    db_session.expire_all()
    doc_after = db_session.query(Document).filter(Document.id == doc_id_str).first()
    assert doc_after is None
    sheet_after = db_session.query(DocumentSheet).filter(DocumentSheet.id == sheet_id_str).first()
    assert sheet_after is None
    finding_after = db_session.query(RuleFinding).filter(RuleFinding.id == finding_id_str).first()
    assert finding_after is None

    # Verificar borrado físico de archivos
    assert not os.path.exists(pdf_path)
    assert not os.path.exists(png_path)

    # Verificar audit log de hard delete
    audit_hard = db_session.query(AuditLog).filter(
        AuditLog.entity_id == doc_id_str,
        AuditLog.action == "hard_delete_permanent"
    ).first()
    assert audit_hard is not None

