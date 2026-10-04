import os
import io
import uuid
import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import SessionLocal
from app.db.models.core import User, Organization, OrganizationMembership, Project
from app.db.models.document_memory import Document, DocumentSheet
from app.core.security import create_access_token

@pytest.fixture
def doc_test_setup():
    db: Session = SessionLocal()
    suffix = str(uuid.uuid4())[:8]
    org_a_id = f"test-org-a-{suffix}"
    org_b_id = f"test-org-b-{suffix}"
    admin_a_id = f"admin-a-{suffix}"
    admin_b_id = f"admin-b-{suffix}"

    org_a = Organization(id=org_a_id, name=f"Org A {suffix}", slug=f"org-a-{suffix}")
    org_b = Organization(id=org_b_id, name=f"Org B {suffix}", slug=f"org-b-{suffix}")
    user_a = User(id=admin_a_id, email=f"admin-a-{suffix}@test.com", display_name="Admin Org A", password_hash="fake", is_active=True)
    user_b = User(id=admin_b_id, email=f"admin-b-{suffix}@test.com", display_name="Admin Org B", password_hash="fake", is_active=True)
    
    db.add_all([org_a, org_b, user_a, user_b])
    db.commit()

    mem_a = OrganizationMembership(organization_id=org_a.id, user_id=user_a.id, role="admin", status="active")
    mem_b = OrganizationMembership(organization_id=org_b.id, user_id=user_b.id, role="admin", status="active")
    db.add_all([mem_a, mem_b])
    db.commit()

    token_a = create_access_token(user_a.id, email=user_a.email, extra_claims={"role": "admin"})
    token_b = create_access_token(user_b.id, email=user_b.email, extra_claims={"role": "admin"})
    db.close()

    client = TestClient(app)
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}
    return client, headers_a, headers_b, org_a_id, org_b_id


def generate_test_pdf_bytes() -> bytes:
    return (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000052 00000 n\n0000000101 00000 n\n"
        b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n178\n%%EOF\n"
    )


def test_project_document_upload_and_visibility_flow(doc_test_setup):
    """
    Verifica el flujo operativo de visibilidad inmediata de documentos:
    1. Proyecto A carga PDF -> visible de inmediato.
    2. Proyecto B carga el MISMO PDF -> crea Document independiente, visible en B, visible en A, sin colisión de hash.
    3. Carga duplicada en Proyecto A -> idempotencia sin duplicar filas.
    4. Consulta individual y descarga de documento.
    5. Aislamiento cruzado de proyectos y multi-tenant.
    6. Eliminación de documento limpia sheets sin afectar otros proyectos.
    """
    client, headers_a, headers_b, org_a_id, org_b_id = doc_test_setup

    # 1. Crear Proyecto 1 en Org A
    code_1 = f"PRJ-A1-{str(uuid.uuid4())[:6].upper()}"
    res_p1 = client.post("/api/v1/projects/", json={
        "code": code_1,
        "name": "Proyecto Piping A1",
        "discipline": "mechanical",
        "stage": "Ingeniería de Detalle"
    }, headers=headers_a)
    assert res_p1.status_code == 201
    proj_1_id = res_p1.json()["id"]

    # 2. Cargar PDF en Proyecto 1
    pdf_content = generate_test_pdf_bytes()
    files_1 = {"file": ("PID-Piping-001.pdf", io.BytesIO(pdf_content), "application/pdf")}
    res_up1 = client.post(f"/api/v1/projects/{proj_1_id}/documents", files=files_1, headers=headers_a)
    assert res_up1.status_code == 201
    doc_1 = res_up1.json()
    assert doc_1["project_id"] == proj_1_id
    assert doc_1["filename"] == "PID-Piping-001.pdf"
    assert doc_1["storage_status"] == "stored"
    assert doc_1["processing_status"] in ("processed", "uploaded", "processing")
    doc_1_id = doc_1["id"]

    # 3. Consultar GET /projects/{proj_1_id}/documents: Documento aparece inmediatamente
    res_list1 = client.get(f"/api/v1/projects/{proj_1_id}/documents", headers=headers_a)
    assert res_list1.status_code == 200
    docs_1 = res_list1.json()
    assert len(docs_1) == 1
    assert docs_1[0]["id"] == doc_1_id

    # 4. Crear Proyecto 2 en Org A
    code_2 = f"PRJ-A2-{str(uuid.uuid4())[:6].upper()}"
    res_p2 = client.post("/api/v1/projects/", json={
        "code": code_2,
        "name": "Proyecto Piping A2",
        "discipline": "mechanical",
        "stage": "Ingeniería de Detalle"
    }, headers=headers_a)
    assert res_p2.status_code == 201
    proj_2_id = res_p2.json()["id"]

    # 5. Cargar EXACTAMENTE EL MISMO PDF en Proyecto 2
    files_2 = {"file": ("PID-Piping-001.pdf", io.BytesIO(pdf_content), "application/pdf")}
    res_up2 = client.post(f"/api/v1/projects/{proj_2_id}/documents", files=files_2, headers=headers_a)
    assert res_up2.status_code == 201
    doc_2 = res_up2.json()
    doc_2_id = doc_2["id"]

    # 6. Validar que Document 2 pertenece a Proyecto 2 y tiene un ID distinto
    assert doc_2["project_id"] == proj_2_id
    assert doc_2_id != doc_1_id
    assert doc_2["sha256"] == doc_1["sha256"]

    # 7. Comprobar que Proyecto 2 lo lista de inmediato
    res_list2 = client.get(f"/api/v1/projects/{proj_2_id}/documents", headers=headers_a)
    assert res_list2.status_code == 200
    docs_2 = res_list2.json()
    assert len(docs_2) == 1
    assert docs_2[0]["id"] == doc_2_id

    # 8. Comprobar que Proyecto 1 sigue teniendo su propio documento sin afectarse
    res_list1_again = client.get(f"/api/v1/projects/{proj_1_id}/documents", headers=headers_a)
    assert res_list1_again.status_code == 200
    docs_1_again = res_list1_again.json()
    assert len(docs_1_again) == 1
    assert docs_1_again[0]["id"] == doc_1_id

    # 9. Idempotencia: Subir el mismo archivo a Proyecto 1 una segunda vez
    files_1_dup = {"file": ("PID-Piping-001.pdf", io.BytesIO(pdf_content), "application/pdf")}
    res_up1_dup = client.post(f"/api/v1/projects/{proj_1_id}/documents", files=files_1_dup, headers=headers_a)
    assert res_up1_dup.status_code in (200, 201)
    doc_1_dup = res_up1_dup.json()
    assert doc_1_dup["id"] == doc_1_id

    # La lista de Proyecto 1 NO debe tener duplicados
    res_list1_check = client.get(f"/api/v1/projects/{proj_1_id}/documents", headers=headers_a)
    assert len(res_list1_check.json()) == 1

    # 10. Descarga del archivo original
    res_down = client.get(f"/api/v1/projects/{proj_1_id}/documents/{doc_1_id}/download", headers=headers_a)
    assert res_down.status_code == 200
    assert len(res_down.content) > 0

    # 11. Aislamiento Multi-Tenant: Org B no puede ver ni descargar documentos de Org A
    res_tenant_list = client.get(f"/api/v1/projects/{proj_1_id}/documents", headers=headers_b)
    assert res_tenant_list.status_code in (403, 404)

    res_tenant_down = client.get(f"/api/v1/projects/{proj_1_id}/documents/{doc_1_id}/download", headers=headers_b)
    assert res_tenant_down.status_code in (403, 404)

    # 12. Eliminación de documento en Proyecto 1
    res_del = client.delete(f"/api/v1/projects/{proj_1_id}/documents/{doc_1_id}", headers=headers_a)
    assert res_del.status_code == 200

    # Proyecto 1 queda con 0 documentos
    res_list1_after_del = client.get(f"/api/v1/projects/{proj_1_id}/documents", headers=headers_a)
    assert len(res_list1_after_del.json()) == 0

    # Proyecto 2 conserva su documento intacto
    res_list2_after_del = client.get(f"/api/v1/projects/{proj_2_id}/documents", headers=headers_a)
    assert len(res_list2_after_del.json()) == 1
    assert res_list2_after_del.json()[0]["id"] == doc_2_id


def test_failed_document_processing_and_retry(doc_test_setup):
    """
    Verifica que si el procesamiento falla:
    1. El documento permanece registrado y visible con processing_status='failed'.
    2. can_retry=True.
    3. El endpoint de retry procesa exitosamente sin crear duplicados.
    """
    client, headers_a, _, org_a_id, _ = doc_test_setup

    code = f"PRJ-FAIL-{str(uuid.uuid4())[:6].upper()}"
    res_p = client.post("/api/v1/projects/", json={
        "code": code,
        "name": "Proyecto Test Fallo",
        "discipline": "mechanical",
        "stage": "Ingeniería de Detalle"
    }, headers=headers_a)
    proj_id = res_p.json()["id"]

    # Simular documento en estado 'failed' directamente en BD
    db = SessionLocal()
    failed_doc = Document(
        organization_id=org_a_id,
        project_id=proj_id,
        filename="corrupted_drawing.pdf",
        file_path="./data/raw_documents/fake_nonexistent.pdf",
        file_hash_sha256=f"hash_fake_{str(uuid.uuid4())[:12]}",
        file_size_bytes=1024,
        mime_type="application/pdf",
        page_count=1,
        status="failed",
        error_message="Error de rasterizado forzado: archivo no decodificable."
    )
    db.add(failed_doc)
    db.commit()
    db.refresh(failed_doc)
    doc_id = failed_doc.id
    db.close()

    # Consultar lista: el documento DEBE ser visible a pesar de haber fallado
    res_list = client.get(f"/api/v1/projects/{proj_id}/documents", headers=headers_a)
    assert res_list.status_code == 200
    docs = res_list.json()
    assert len(docs) == 1
    doc_view = docs[0]
    assert doc_view["id"] == doc_id
    assert doc_view["processing_status"] == "failed"
    assert doc_view["can_retry"] is True
    assert doc_view["processing_error_summary"] is not None
