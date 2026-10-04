import pytest
import uuid
from fastapi.testclient import TestClient
from app.db.models.core import User, Organization, OrganizationMembership, Project
from app.db.models.document_memory import Document, DocumentSheet
from app.core.security import hash_password, create_access_token

def test_plan_selections_incorporation_flow(client: TestClient, db_session):
    # 1. Setup Tenant, User, Project, Doc, Sheet en BD
    org_id = str(uuid.uuid4())
    org = Organization(id=org_id, name="Plan Selections Org", slug=f"sel-org-{uuid.uuid4().hex[:6]}")
    db_session.add(org)

    user = User(
        id=str(uuid.uuid4()),
        email=f"architect_{uuid.uuid4().hex[:6]}@planreview.ai",
        display_name="Arquitecto Auditor",
        password_hash=hash_password("Password123!"),
        is_active=True,
        is_superuser=False
    )
    db_session.add(user)

    membership = OrganizationMembership(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        user_id=user.id,
        role="reviewer",
        status="active"
    )
    db_session.add(membership)

    project = Project(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        name="Edificio Residencial Parque Central",
        code="PRJ-RES-01"
    )
    db_session.add(project)

    doc = Document(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        project_id=project.id,
        filename="Plano_Arquitectura_Piso1.pdf",
        file_path="storage/raw/Plano_Arquitectura_Piso1.pdf",
        file_hash_sha256="hash12345678",
        file_size_bytes=1048576,
        status="ingested"
    )
    db_session.add(doc)

    sheet = DocumentSheet(
        id=str(uuid.uuid4()),
        document_id=doc.id,
        sheet_number=1,
        sheet_code="ARQ-01",
        width_px=3508,
        height_px=2480
    )
    db_session.add(sheet)
    db_session.commit()

    token = create_access_token(user.id, email=user.email, extra_claims={"role": "reviewer"})
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Organization-Id": org_id,
        "x-user-id": user.id
    }

    # 2. Registrar Selección 1 (Símbolo de Tablero Eléctrico)
    s1_res = client.post(
        "/api/v1/annotations",
        headers=headers,
        json={
            "project_id": project.id,
            "document_id": doc.id,
            "sheet_id": sheet.id,
            "bbox_normalized": [0.12, 0.25, 0.18, 0.32],
            "element_type": "symbol",
            "name": "Tablero General de Fuerza (TGF)",
            "description": "Tablero eléctrico embutido con interruptor diferencial general de 40A.",
            "discipline": "electrical",
            "status": "draft"
        }
    )
    assert s1_res.status_code == 200
    sel1_id = s1_res.json()["id"]

    # 3. Registrar Selección 2 (Cuadro de Cargas Técnicas)
    s2_res = client.post(
        "/api/v1/annotations",
        headers=headers,
        json={
            "project_id": project.id,
            "document_id": doc.id,
            "sheet_id": sheet.id,
            "bbox_normalized": [0.70, 0.15, 0.95, 0.45],
            "element_type": "table",
            "name": "Cuadro de Superficies y Cargas",
            "description": "Tabla de resumen de superficies útiles, comunes y potencia total instalada.",
            "discipline": "architecture",
            "status": "draft"
        }
    )
    assert s2_res.status_code == 200
    sel2_id = s2_res.json()["id"]

    # 4. Simular Edición de Selección (Acción "Editar" o "Reseleccionar")
    edit_res = client.put(
        f"/api/v1/annotations/{sel1_id}",
        headers=headers,
        json={
            "name": "Tablero General de Fuerza (TGF-1) Actualizado",
            "description": "Tablero de fuerza con protección IP55 e interruptor de 63A.",
            "status": "editada"
        }
    )
    assert edit_res.status_code == 200
    assert "TGF-1" in edit_res.json()["name"]

    # 5. Simular Validación de Selecciones (Acción "Validar")
    val1_res = client.put(
        f"/api/v1/annotations/{sel1_id}",
        headers=headers,
        json={"status": "validada"}
    )
    assert val1_res.status_code == 200
    assert val1_res.json()["status"] == "validada"

    val2_res = client.put(
        f"/api/v1/annotations/{sel2_id}",
        headers=headers,
        json={"status": "validada"}
    )
    assert val2_res.status_code == 200
    assert val2_res.json()["status"] == "validada"

    # 6. Incorporar Selecciones Validadas al Circuito Documental del Proyecto
    inc_res = client.post(
        "/api/v1/annotations/incorporate-to-project-document",
        headers=headers,
        json={
            "project_id": project.id,
            "annotation_ids": [sel1_id, sel2_id]
        }
    )
    assert inc_res.status_code == 200
    inc_data = inc_res.json()
    assert inc_data["incorporated_count"] == 2
    assert "Información basada en proyecto" in inc_data["rule_document_title"]
    assert "Edificio Residencial Parque Central" in inc_data["rule_document_title"]
    rule_doc_id = inc_data["rule_document_id"]

    # 7. Verificar que el Documento aparece en "Documentos Nativos & Fuentes Incorporados"
    docs_res = client.get("/api/v1/rules/documents", headers=headers)
    assert docs_res.status_code == 200
    rule_docs = docs_res.json()
    project_doc = next((d for d in rule_docs if d["id"] == rule_doc_id), None)
    assert project_doc is not None
    assert project_doc["source_origin"] == "visor_de_planos"
    assert project_doc["document_type"] == "proyecto_evidencia"
    assert project_doc["project_id"] == project.id
    assert project_doc["items_count"] == 2

    # 8. Verificar que los ítems del documento están disponibles para el modal "Contenido"
    items_res = client.get(f"/api/v1/rules/documents/{rule_doc_id}/items", headers=headers)
    assert items_res.status_code == 200
    doc_items = items_res.json()
    assert len(doc_items) == 2
    titles = [i["title"] for i in doc_items]
    assert "Tablero General de Fuerza (TGF-1) Actualizado" in titles
    assert "Cuadro de Superficies y Cargas" in titles

    # 9. Simular Acción "Eliminar" de una Selección
    tmp_res = client.post(
        "/api/v1/annotations",
        headers=headers,
        json={
            "project_id": project.id,
            "document_id": doc.id,
            "sheet_id": sheet.id,
            "bbox_normalized": [0.5, 0.5, 0.6, 0.6],
            "element_type": "other",
            "name": "Elemento Temporal",
            "status": "draft"
        }
    )
    assert tmp_res.status_code == 200
    tmp_id = tmp_res.json()["id"]

    del_res = client.delete(f"/api/v1/annotations/{tmp_id}", headers=headers)
    assert del_res.status_code == 200

    list_res = client.get(f"/api/v1/annotations?project_id={project.id}", headers=headers)
    assert list_res.status_code == 200
    remaining_ids = [a["id"] for a in list_res.json()]
    assert tmp_id not in remaining_ids
