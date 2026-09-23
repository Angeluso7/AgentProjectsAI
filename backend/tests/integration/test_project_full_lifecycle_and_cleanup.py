import os
import uuid
import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import SessionLocal
from app.db.models.core import User, Organization, OrganizationMembership, Project, AuditLog
from app.db.models.document_memory import Document, DocumentSheet
from app.db.models.decision_memory import ReviewRun, RuleFinding
from app.db.models.operations import ProcessingJob
from app.core.security import create_access_token

@pytest.fixture
def test_setup():
    db: Session = SessionLocal()
    suffix = str(uuid.uuid4())[:8]
    org_id = f"test-org-life-{suffix}"
    admin_id = f"admin-user-{suffix}"
    viewer_id = f"viewer-user-{suffix}"

    org = Organization(id=org_id, name=f"Org Lifecycle {suffix}", slug=f"org-life-{suffix}")
    admin_user = User(id=admin_id, email=f"admin-{suffix}@lifecycle.com", display_name="Admin Lifecycle", password_hash="fake", is_active=True)
    viewer_user = User(id=viewer_id, email=f"viewer-{suffix}@lifecycle.com", display_name="Viewer Lifecycle", password_hash="fake", is_active=True)
    db.add(org)
    db.add(admin_user)
    db.add(viewer_user)
    db.commit()

    mem_admin = OrganizationMembership(organization_id=org.id, user_id=admin_user.id, role="admin", status="active")
    mem_viewer = OrganizationMembership(organization_id=org.id, user_id=viewer_user.id, role="viewer", status="active")
    db.add(mem_admin)
    db.add(mem_viewer)
    db.commit()

    admin_token = create_access_token(admin_user.id, email=admin_user.email, extra_claims={"role": "admin"})
    viewer_token = create_access_token(viewer_user.id, email=viewer_user.email, extra_claims={"role": "viewer"})
    db.close()

    client = TestClient(app)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}
    return client, admin_headers, viewer_headers, org_id

def test_project_archive_and_restore_cycle(test_setup):
    client, admin_headers, _, org_id = test_setup

    # 1. Crear proyecto
    code = f"PRJ-ARCH-{str(uuid.uuid4())[:6].upper()}"
    res = client.post("/api/v1/projects/", json={
        "code": code,
        "name": "Proyecto Archivo Test",
        "discipline": "architecture",
        "stage": "Ingeniería Conceptual"
    }, headers=admin_headers)
    assert res.status_code == 201
    prj = res.json()
    prj_id = prj["id"]

    # 2. Archivar proyecto vía PATCH /archive
    res_arch = client.patch(f"/api/v1/projects/{prj_id}/archive", headers=admin_headers)
    assert res_arch.status_code == 200
    arch_data = res_arch.json()
    assert arch_data["status"] == "archived"
    assert arch_data["is_active"] is False

    # 3. Verificar listado filtrado
    res_active_only = client.get("/api/v1/projects/?include_archived=false", headers=admin_headers)
    assert res_active_only.status_code == 200
    active_ids = [p["id"] for p in res_active_only.json()]
    assert prj_id not in active_ids

    res_all = client.get("/api/v1/projects/?include_archived=true", headers=admin_headers)
    assert res_all.status_code == 200
    all_ids = [p["id"] for p in res_all.json()]
    assert prj_id in all_ids

    # 4. Restaurar proyecto vía PATCH /restore
    res_rest = client.patch(f"/api/v1/projects/{prj_id}/restore", headers=admin_headers)
    assert res_rest.status_code == 200
    rest_data = res_rest.json()
    assert rest_data["status"] == "active"
    assert rest_data["is_active"] is True

    # 5. Verificar auditoría
    db: Session = SessionLocal()
    audits = db.query(AuditLog).filter(AuditLog.entity_id == prj_id).all()
    actions = [a.action for a in audits]
    assert "archive_project" in actions
    assert "restore_project" in actions
    db.close()

def test_deletion_impact_and_clear_content_flow(test_setup):
    client, admin_headers, _, org_id = test_setup
    db: Session = SessionLocal()

    code = f"PRJ-CLR-{str(uuid.uuid4())[:6].upper()}"
    res = client.post("/api/v1/projects/", json={
        "code": code,
        "name": "Proyecto Vaciado Test",
        "discipline": "architecture"
    }, headers=admin_headers)
    assert res.status_code == 201
    prj_id = res.json()["id"]

    # Crear archivos físicos de prueba
    test_dir = os.path.join("./data", "test_fixtures", prj_id)
    os.makedirs(test_dir, exist_ok=True)
    doc_path = os.path.join(test_dir, "sample_drawing.pdf")
    raster_path = os.path.join(test_dir, "sample_sheet_1.png")
    with open(doc_path, "wb") as f:
        f.write(b"%PDF-1.4 test dummy drawing content")
    with open(raster_path, "wb") as f:
        f.write(b"\x89PNG test dummy raster sheet")

    assert os.path.exists(doc_path)
    assert os.path.exists(raster_path)

    # Insertar Documento y Lámina en BD
    doc_id = str(uuid.uuid4())
    doc = Document(
        id=doc_id,
        organization_id=org_id,
        project_id=prj_id,
        filename="sample_drawing.pdf",
        file_path=doc_path,
        file_hash_sha256=f"hash_{prj_id}",
        file_size_bytes=34,
        mime_type="application/pdf",
        status="ready"
    )
    db.add(doc)
    db.commit()

    sheet = DocumentSheet(
        id=str(uuid.uuid4()),
        document_id=doc_id,
        sheet_number=1,
        title="Planta Nivel 1",
        width_px=1000,
        height_px=800,
        dpi=150,
        raster_image_path=raster_path
    )
    db.add(sheet)

    # Insertar corrida de revisión y hallazgo
    run_id = str(uuid.uuid4())
    run = ReviewRun(
        id=run_id,
        organization_id=org_id,
        project_id=prj_id,
        run_name="Auditoría Preliminar",
        status="completed"
    )
    db.add(run)
    db.commit()

    finding = RuleFinding(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        review_run_id=run_id,
        document_id=doc_id,
        rule_id="RULE_TEST",
        rule_code="R01",
        rule_name="Regla de Prueba",
        category="cross_reconciliation",
        title="Discrepancia detectada",
        description="Descripción de discrepancia detectada en prueba",
        severity="medium",
        status="open"
    )
    db.add(finding)
    db.commit()
    db.close()

    # 1. Consultar GET /deletion-impact
    res_impact = client.get(f"/api/v1/projects/{prj_id}/deletion-impact", headers=admin_headers)
    assert res_impact.status_code == 200
    impact = res_impact.json()
    assert impact["documents"] == 1
    assert impact["stored_files"] >= 2
    assert impact["evaluation_runs"] == 1
    assert impact["findings"] == 1
    assert impact["can_hard_delete"] is True

    # 2. Intentar vaciar con código incorrecto (debe rechazar con 400)
    res_bad_code = client.post(f"/api/v1/projects/{prj_id}/clear-content", json={
        "confirmation_code": "WRONG-CODE",
        "reason": "Test vaciado",
        "acknowledge_data_loss": True
    }, headers=admin_headers)
    assert res_bad_code.status_code == 400

    # 3. Vaciar contenido con confirmación exacta
    res_clear = client.post(f"/api/v1/projects/{prj_id}/clear-content", json={
        "confirmation_code": code,
        "reason": "Vaciado integral para nueva versión",
        "acknowledge_data_loss": True
    }, headers=admin_headers)
    assert res_clear.status_code == 200
    clear_data = res_clear.json()
    assert clear_data["success"] is True
    assert clear_data["files_deleted"] >= 2
    assert clear_data["cleanup_status"] == "completed"

    # Verificar que los archivos físicos en disco fueron eliminados
    assert not os.path.exists(doc_path)
    assert not os.path.exists(raster_path)

    # Verificar que los documentos y hallazgos fueron purgados en BD
    db = SessionLocal()
    docs_remaining = db.query(Document).filter(Document.project_id == prj_id).count()
    findings_remaining = db.query(RuleFinding).join(ReviewRun).filter(ReviewRun.project_id == prj_id).count()
    assert docs_remaining == 0
    assert findings_remaining == 0

    # Verificar que la ficha del proyecto se conserva intacta
    prj_db = db.query(Project).filter(Project.id == prj_id).first()
    assert prj_db is not None
    assert prj_db.code == code
    assert prj_db.cleanup_status == "completed"
    db.close()

def test_delete_confirmed_hard_delete_flow(test_setup):
    client, admin_headers, _, org_id = test_setup
    db: Session = SessionLocal()

    code = f"PRJ-DEL-{str(uuid.uuid4())[:6].upper()}"
    res = client.post("/api/v1/projects/", json={
        "code": code,
        "name": "Proyecto Para Eliminar Definitivo",
        "discipline": "architecture"
    }, headers=admin_headers)
    assert res.status_code == 201
    prj_id = res.json()["id"]

    # Crear archivo físico de prueba
    test_dir = os.path.join("./data", "test_fixtures", prj_id)
    os.makedirs(test_dir, exist_ok=True)
    doc_path = os.path.join(test_dir, "blueprint_to_purge.pdf")
    with open(doc_path, "wb") as f:
        f.write(b"%PDF-1.4 sample file to permanently purge")

    doc = Document(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        project_id=prj_id,
        filename="blueprint_to_purge.pdf",
        file_path=doc_path,
        file_hash_sha256=f"hash_del_{prj_id}",
        file_size_bytes=42,
        mime_type="application/pdf",
        status="ready"
    )
    db.add(doc)

    # Crear ProcessingJob huérfano simulado vinculado al proyecto
    job = ProcessingJob(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        project_id=prj_id,
        job_type="document_ingest",
        target_type="project",
        target_id=prj_id,
        status="completed"
    )
    db.add(job)
    db.commit()
    db.close()

    assert os.path.exists(doc_path)

    # 1. Intentar eliminar con código incorrecto -> 400
    res_fail = client.post(f"/api/v1/projects/{prj_id}/delete-confirmed", json={
        "confirmation_code": "INCORRECT-CODE",
        "mode": "hard_delete",
        "reason": "Test fail",
        "acknowledge_data_loss": True
    }, headers=admin_headers)
    assert res_fail.status_code == 400

    # 2. Ejecutar hard delete confirmado con código exacto
    res_del = client.post(f"/api/v1/projects/{prj_id}/delete-confirmed", json={
        "confirmation_code": code,
        "mode": "hard_delete",
        "reason": "Eliminación permanente aprobada por auditor líder",
        "acknowledge_data_loss": True
    }, headers=admin_headers)
    assert res_del.status_code == 200
    del_data = res_del.json()
    assert del_data["success"] is True
    assert del_data["status"] == "hard_deleted"
    assert del_data["files_deleted"] >= 1

    # 3. Archivo físico purgado
    assert not os.path.exists(doc_path)

    # 4. Verificar que el proyecto no existe más en BD
    db = SessionLocal()
    prj_in_db = db.query(Project).filter(Project.id == prj_id).first()
    assert prj_in_db is None

    # 5. Verificar CERO registros huérfanos en ProcessingJob y Document
    jobs_in_db = db.query(ProcessingJob).filter(ProcessingJob.project_id == prj_id).count()
    docs_in_db = db.query(Document).filter(Document.project_id == prj_id).count()
    assert jobs_in_db == 0
    assert docs_in_db == 0

    # 6. GET /projects/{id} debe dar 404
    res_get_del = client.get(f"/api/v1/projects/{prj_id}", headers=admin_headers)
    assert res_get_del.status_code == 404
    db.close()

def test_delete_confirmed_anonymize_mode(test_setup):
    client, admin_headers, _, org_id = test_setup

    code = f"PRJ-ANON-{str(uuid.uuid4())[:6].upper()}"
    res = client.post("/api/v1/projects/", json={
        "code": code,
        "name": "Proyecto Confidencial Banco",
        "client_name": "Banco Santander Chile",
        "description": "Datos sensibles de sucursales",
        "discipline": "architecture"
    }, headers=admin_headers)
    assert res.status_code == 201
    prj_id = res.json()["id"]

    # Ejecutar anonimización confirmada
    res_anon = client.post(f"/api/v1/projects/{prj_id}/delete-confirmed", json={
        "confirmation_code": code,
        "mode": "anonymize",
        "reason": "Retención legal obligatoria pero datos anonimizados",
        "acknowledge_data_loss": True
    }, headers=admin_headers)
    assert res_anon.status_code == 200
    assert res_anon.json()["status"] == "deleted"

    # Verificar que el registro en BD está anonimizado y marcado como deleted
    db: Session = SessionLocal()
    prj = db.query(Project).filter(Project.id == prj_id).first()
    assert prj is not None
    assert prj.status == "deleted"
    assert prj.client_name == "[ANONYMIZED]"
    assert prj.description == "[ANONYMIZED]"
    assert prj.name.startswith("[ANONYMIZED")
    db.close()

def test_role_authorization_and_tenant_isolation(test_setup):
    client, admin_headers, viewer_headers, org_id = test_setup

    # Crear proyecto como admin
    code = f"PRJ-AUTH-{str(uuid.uuid4())[:6].upper()}"
    res = client.post("/api/v1/projects/", json={
        "code": code,
        "name": "Proyecto Permisos Test",
        "discipline": "architecture"
    }, headers=admin_headers)
    assert res.status_code == 201
    prj_id = res.json()["id"]

    # Viewer intenta archivar -> 403 Forbidden
    res_view_arch = client.patch(f"/api/v1/projects/{prj_id}/archive", headers=viewer_headers)
    assert res_view_arch.status_code == 403

    # Viewer intenta vaciar -> 403 Forbidden
    res_view_clear = client.post(f"/api/v1/projects/{prj_id}/clear-content", json={
        "confirmation_code": code,
        "acknowledge_data_loss": True
    }, headers=viewer_headers)
    assert res_view_clear.status_code == 403

    # Viewer intenta eliminar -> 403 Forbidden
    res_view_del = client.post(f"/api/v1/projects/{prj_id}/delete-confirmed", json={
        "confirmation_code": code,
        "acknowledge_data_loss": True
    }, headers=viewer_headers)
    assert res_view_del.status_code == 403

    # Crear otra organización
    db: Session = SessionLocal()
    other_org_id = f"other-org-{str(uuid.uuid4())[:8]}"
    other_user_id = f"other-user-{str(uuid.uuid4())[:8]}"
    other_org = Organization(id=other_org_id, name="Other Tenant", slug=f"other-{other_org_id}")
    other_user = User(id=other_user_id, email=f"other-{other_org_id}@test.com", display_name="Other User", password_hash="fake", is_active=True)
    db.add(other_org)
    db.add(other_user)
    db.commit()
    db.add(OrganizationMembership(organization_id=other_org.id, user_id=other_user.id, role="admin", status="active"))
    db.commit()
    other_token = create_access_token(other_user.id, email=other_user.email, extra_claims={"role": "admin"})
    db.close()

    other_headers = {"Authorization": f"Bearer {other_token}"}

    # Admin de otra organización intenta consultar/eliminar proyecto de org 1 -> 404
    res_cross_get = client.get(f"/api/v1/projects/{prj_id}", headers=other_headers)
    assert res_cross_get.status_code == 404

    res_cross_del = client.post(f"/api/v1/projects/{prj_id}/delete-confirmed", json={
        "confirmation_code": code,
        "acknowledge_data_loss": True
    }, headers=other_headers)
    assert res_cross_del.status_code == 404

def test_storage_failure_and_retry(test_setup, monkeypatch):
    client, admin_headers, _, org_id = test_setup
    db: Session = SessionLocal()

    code = f"PRJ-FAIL-{str(uuid.uuid4())[:6].upper()}"
    res = client.post("/api/v1/projects/", json={
        "code": code,
        "name": "Proyecto Storage Fail Test",
        "discipline": "architecture"
    }, headers=admin_headers)
    assert res.status_code == 201
    prj_id = res.json()["id"]

    test_dir = os.path.join("./data", "test_fixtures", prj_id)
    os.makedirs(test_dir, exist_ok=True)
    doc_path = os.path.join(test_dir, "locked_file.pdf")
    with open(doc_path, "wb") as f:
        f.write(b"%PDF-1.4 dummy locked file")

    doc = Document(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        project_id=prj_id,
        filename="locked_file.pdf",
        file_path=doc_path,
        file_hash_sha256=f"hash_lock_{prj_id}",
        file_size_bytes=26,
        mime_type="application/pdf",
        status="ready"
    )
    db.add(doc)
    db.commit()
    db.close()

    def mock_remove(path):
        raise PermissionError(f"EACCES: permission denied on {path}")

    monkeypatch.setattr(os, "remove", mock_remove)

    res_fail = client.post(f"/api/v1/projects/{prj_id}/clear-content", json={
        "confirmation_code": code,
        "acknowledge_data_loss": True
    }, headers=admin_headers)
    assert res_fail.status_code == 500

    db = SessionLocal()
    prj_db = db.query(Project).filter(Project.id == prj_id).first()
    assert prj_db is not None
    assert prj_db.cleanup_status == "failed_cleanup"
    assert prj_db.cleanup_error is not None
    db.close()

    monkeypatch.undo()
    res_retry = client.post(f"/api/v1/projects/{prj_id}/clear-content", json={
        "confirmation_code": code,
        "acknowledge_data_loss": True
    }, headers=admin_headers)
    assert res_retry.status_code == 200
    assert res_retry.json()["cleanup_status"] == "completed"
    assert not os.path.exists(doc_path)

