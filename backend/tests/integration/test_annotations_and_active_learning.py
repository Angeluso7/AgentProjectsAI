import pytest
import uuid
import base64
from fastapi.testclient import TestClient
from app.db.models.core import User, Organization, OrganizationMembership, Project
from app.db.models.document_memory import Document, DocumentSheet
from app.core.security import hash_password, create_access_token

def test_annotations_knowledge_and_active_learning(client: TestClient, db_session):
    # 1. Setup Tenant, User, Project, Doc, Sheet
    org_id = str(uuid.uuid4())
    org = Organization(id=org_id, name="Annotation Test Org", slug=f"ann-org-{uuid.uuid4().hex[:6]}")
    db_session.add(org)

    user = User(
        id=str(uuid.uuid4()),
        email=f"reviewer_{uuid.uuid4().hex[:6]}@planreview.ai",
        display_name="Auditor Anotador",
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
        name="Proyecto Hospital Central",
        code="PRJ-HOSP-001"
    )
    db_session.add(project)

    doc = Document(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        project_id=project.id,
        filename="PLANO-ELEC-01.pdf",
        file_path="storage/raw/PLANO-ELEC-01.pdf",
        file_hash_sha256="abc123hash",
        file_size_bytes=1048576,
        status="ingested"
    )


    db_session.add(doc)

    sheet = DocumentSheet(
        id=str(uuid.uuid4()),
        document_id=doc.id,
        sheet_number=1,
        sheet_code="E-101",
        width_px=2000,
        height_px=1400,
        raster_image_path="storage/rasters/test.png"
    )
    db_session.add(sheet)
    db_session.commit()

    token = create_access_token(user.id, email=user.email, extra_claims={"role": "reviewer"})
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

    # 2. Test Crop OCR Endpoint (POST /api/v1/annotations/crop-ocr)
    # 1x1 transparent png in base64
    fake_png_base64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
    ocr_res = client.post(
        "/api/v1/annotations/crop-ocr",
        headers=headers,
        json={"image_base64": fake_png_base64, "sheet_id": sheet.id}
    )
    assert ocr_res.status_code == 200
    assert "text" in ocr_res.json()
    assert ocr_res.json()["confidence"] > 0

    # 3. Test Manual Annotation Creation (POST /api/v1/annotations)
    ann_payload = {
        "project_id": project.id,
        "document_id": doc.id,
        "sheet_id": sheet.id,
        "bbox_normalized": [0.1, 0.2, 0.35, 0.45],
        "bbox_pixels": [200, 280, 700, 630],
        "crop_image_base64": fake_png_base64,
        "element_type": "symbol",
        "name": "Enchufe Doble Embutido 220V",
        "description": "Enchufe de fuerza en tabique seco",
        "discipline": "electrical",
        "tags": ["fuerza", "enchufe", "220v"],
        "status": "confirmed"
    }
    create_res = client.post("/api/v1/annotations", headers=headers, json=ann_payload)
    assert create_res.status_code == 200
    ann_data = create_res.json()
    assert ann_data["name"] == "Enchufe Doble Embutido 220V"
    assert ann_data["crop_image_path"] is not None
    annotation_id = ann_data["id"]

    # 4. Test List Manual Annotations (GET /api/v1/annotations)
    list_res = client.get(f"/api/v1/annotations?sheet_id={sheet.id}", headers=headers)
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1

    # 4.1. Test Update Manual Annotation (PUT /api/v1/annotations/{id})
    update_res = client.put(
        f"/api/v1/annotations/{annotation_id}",
        headers=headers,
        json={"name": "Enchufe Doble 220V - Actualizado", "discipline": "electrical", "tags": ["fuerza", "actualizado"]}
    )
    assert update_res.status_code == 200
    assert update_res.json()["name"] == "Enchufe Doble 220V - Actualizado"
    assert "actualizado" in update_res.json()["tags"]

    # 4.2. Test Annotation Disciplines Endpoint & Custom Discipline Persistence (GET /api/v1/annotations/disciplines)
    discs_res = client.get("/api/v1/annotations/disciplines", headers=headers)
    assert discs_res.status_code == 200
    disciplines_list = discs_res.json()
    assert "electrical" in disciplines_list
    assert "general" in disciplines_list

    # Create annotation with a new custom discipline
    custom_ann_payload = {
        "project_id": project.id,
        "document_id": doc.id,
        "sheet_id": sheet.id,
        "bbox_normalized": [0.5, 0.5, 0.7, 0.7],
        "element_type": "symbol",
        "name": "Router Rack Central",
        "description": "Gabinete de datos",
        "discipline": "telecomunicaciones",
        "status": "confirmed"
    }
    custom_ann_res = client.post("/api/v1/annotations", headers=headers, json=custom_ann_payload)
    assert custom_ann_res.status_code == 200

    discs_res2 = client.get("/api/v1/annotations/disciplines", headers=headers)
    assert discs_res2.status_code == 200
    assert "telecomunicaciones" in discs_res2.json()

    # 5. Test Nivel 1: Promote to Knowledge Library (POST /api/v1/annotations/knowledge-library)

    kl_payload = {
        "source_annotation_id": annotation_id,
        "entry_type": "symbol_template",
        "name": "Símbolo Estándar NCh - Enchufe 220V",
        "description": "Plantilla oficial de enchufe según NCh Elec 4/2003",
        "discipline": "electrical",
        "crop_image_path": ann_data["crop_image_path"],
        "tags": ["simbolo", "nch", "electrico"]
    }
    kl_res = client.post("/api/v1/annotations/knowledge-library", headers=headers, json=kl_payload)
    assert kl_res.status_code == 200
    kl_data = kl_res.json()
    assert kl_data["name"] == "Símbolo Estándar NCh - Enchufe 220V"
    knowledge_entry_id = kl_data["id"]

    # List Knowledge Library entries
    kl_list_res = client.get("/api/v1/annotations/knowledge-library?discipline=electrical", headers=headers)
    assert kl_list_res.status_code == 200
    assert len(kl_list_res.json()) >= 1

    # 6. Test Nivel 2: Promote to Active Learning (POST /api/v1/annotations/active-learning/promote)
    al_payload = {
        "knowledge_entry_id": knowledge_entry_id,
        "manual_annotation_id": annotation_id,
        "target_engine": "symbol_detector",
        "dataset_split": "train",
        "label": "outlet_double_220v",
        "ground_truth_bbox": [0.1, 0.2, 0.35, 0.45],
        "notes": "Muestra validada por auditor para dataset YOLOv8/SAHI"
    }
    al_res = client.post("/api/v1/annotations/active-learning/promote", headers=headers, json=al_payload)
    assert al_res.status_code == 200
    al_data = al_res.json()
    assert al_data["target_engine"] == "symbol_detector"
    assert al_data["status"] == "staged"

    # List Active Learning Promotions
    al_list_res = client.get("/api/v1/annotations/active-learning?target_engine=symbol_detector", headers=headers)
    assert al_list_res.status_code == 200
    assert len(al_list_res.json()) >= 1
