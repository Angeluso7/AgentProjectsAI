import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import SessionLocal
from app.db.models.core import User, Organization, OrganizationMembership, Project
from app.db.models.document_memory import Document
from app.core.security import create_access_token

import uuid

@pytest.fixture
def client_with_auth():
    db: Session = SessionLocal()
    unique_suffix = str(uuid.uuid4())[:8]
    org_id = f"test-org-proj-{unique_suffix}"
    user_id = f"test-user-proj-{unique_suffix}"
    
    org = Organization(id=org_id, name="Org Proyectos Test", slug=f"org-proj-{unique_suffix}")
    user = User(id=user_id, email=f"admin-{unique_suffix}@test.com", display_name="Admin Test", password_hash="fake", is_active=True)
    db.add(org)
    db.add(user)
    db.commit()

    mem = OrganizationMembership(organization_id=org.id, user_id=user.id, role="admin", status="active")
    db.add(mem)
    db.commit()

    token = create_access_token(user.id, email=user.email, extra_claims={"role": "admin"})
    db.close()

    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}
    return client, headers, org_id

def test_project_crud_and_lifecycle_flow(client_with_auth):
    client, headers, org_id = client_with_auth

    # 1. Crear Proyecto con Etapa y Disciplina
    create_payload = {
        "code": "PRJ-TEST-LIFECYCLE-01",
        "name": "Edificio Titanium Norte",
        "description": "Torre corporativa de oficinas de 22 pisos",
        "client_name": "Inversiones Inmobiliarias SA",
        "discipline": "architecture",
        "stage": "Ingeniería Básica",
        "project_type": "edificacion",
        "status": "active"
    }
    res_create = client.post("/api/v1/projects/", json=create_payload, headers=headers)
    assert res_create.status_code == 201, res_create.text
    project = res_create.json()
    project_id = project["id"]
    assert project["code"] == "PRJ-TEST-LIFECYCLE-01"
    assert project["stage"] == "Ingeniería Básica"
    assert project["status"] == "active"
    assert project["is_active"] is True

    # 2. Intentar duplicar código en la misma organización (debe dar 400)
    res_dup = client.post("/api/v1/projects/", json=create_payload, headers=headers)
    assert res_dup.status_code == 400

    # 3. Obtener detalle de proyecto
    res_get = client.get(f"/api/v1/projects/{project_id}", headers=headers)
    assert res_get.status_code == 200
    assert res_get.json()["id"] == project_id

    # 4. Actualizar Proyecto (cambiar etapa a Ingeniería de Detalle y cliente)
    update_payload = {
        "name": "Edificio Titanium Norte - Fase 1",
        "stage": "Ingeniería de Detalle",
        "client_name": "Titanium Corp SpA"
    }
    res_update = client.put(f"/api/v1/projects/{project_id}", json=update_payload, headers=headers)
    assert res_update.status_code == 200
    updated = res_update.json()
    assert updated["name"] == "Edificio Titanium Norte - Fase 1"
    assert updated["stage"] == "Ingeniería de Detalle"
    assert updated["client_name"] == "Titanium Corp SpA"

    # 5. Listar proyectos
    res_list = client.get("/api/v1/projects/", headers=headers)
    assert res_list.status_code == 200
    p_list = res_list.json()
    assert any(p["id"] == project_id for p in p_list)

    # 6. Exportar proyecto (verificar trazabilidad)
    res_export = client.get(f"/api/v1/projects/{project_id}/export", headers=headers)
    assert res_export.status_code == 200
    export_data = res_export.json()
    assert export_data["schema_version"] == "1.0"
    assert export_data["project_id"] == project_id
    assert export_data["stage"] == "Ingeniería de Detalle"
    assert "summary" in export_data
    assert "entities" in export_data

    # 7. Archivar proyecto
    res_archive = client.put(f"/api/v1/projects/{project_id}/archive", headers=headers)
    assert res_archive.status_code == 200
    archived = res_archive.json()
    assert archived["status"] == "archived"
    assert archived["is_active"] is False

    # 8. Listar con include_archived=False (no debe aparecer)
    res_no_archived = client.get("/api/v1/projects/?include_archived=false", headers=headers)
    assert res_no_archived.status_code == 200
    assert not any(p["id"] == project_id for p in res_no_archived.json())

    # 9. Desarchivar proyecto
    res_unarchive = client.put(f"/api/v1/projects/{project_id}/unarchive", headers=headers)
    assert res_unarchive.status_code == 200
    unarchived = res_unarchive.json()
    assert unarchived["status"] == "active"
    assert unarchived["is_active"] is True

    # 10. Soft Delete
    res_delete = client.delete(f"/api/v1/projects/{project_id}", headers=headers)
    assert res_delete.status_code == 200
    
    # Verificar que ya no aparece en listado normal
    res_list_after = client.get("/api/v1/projects/", headers=headers)
    assert not any(p["id"] == project_id for p in res_list_after.json())

def test_multi_project_document_isolation(client_with_auth):
    client, headers, org_id = client_with_auth

    # Crear Proyecto A
    res_a = client.post("/api/v1/projects/", json={
        "code": "PRJ-ISO-A",
        "name": "Proyecto A - Minería",
        "discipline": "mechanical",
        "stage": "Factibilidad",
        "project_type": "mineria"
    }, headers=headers)
    assert res_a.status_code == 201
    proj_a = res_a.json()

    # Crear Proyecto B
    res_b = client.post("/api/v1/projects/", json={
        "code": "PRJ-ISO-B",
        "name": "Proyecto B - Subestación",
        "discipline": "electrical",
        "stage": "Ingeniería de Detalle",
        "project_type": "energia"
    }, headers=headers)
    assert res_b.status_code == 201
    proj_b = res_b.json()

    # Consultar documentos filtrados por project_id
    docs_a = client.get(f"/api/v1/documents/?project_id={proj_a['id']}", headers=headers).json()
    docs_b = client.get(f"/api/v1/documents/?project_id={proj_b['id']}", headers=headers).json()
    assert isinstance(docs_a, list)
    assert isinstance(docs_b, list)
