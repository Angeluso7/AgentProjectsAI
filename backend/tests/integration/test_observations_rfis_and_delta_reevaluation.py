import pytest
import uuid
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import SessionLocal
from app.db.models.core import User, Organization, OrganizationMembership, Project
from app.db.models.document_memory import Document, DocumentSheet, ExtractedTable, ExtractedTableCell
from app.db.models.observations import AuditObservation
from app.core.security import create_access_token

@pytest.fixture
def client_with_auth():
    db: Session = SessionLocal()
    unique_suffix = str(uuid.uuid4())[:8]
    org_id = f"test-org-obs-{unique_suffix}"
    user_id = f"test-user-obs-{unique_suffix}"
    
    org = Organization(id=org_id, name="Org Observations Test", slug=f"org-obs-{unique_suffix}")
    user = User(id=user_id, email=f"lead-obs-{unique_suffix}@test.com", display_name="Auditor Senior", password_hash="fake", is_active=True)
    db.add(org)
    db.add(user)
    db.commit()

    mem = OrganizationMembership(organization_id=org.id, user_id=user.id, role="audit_lead", status="active")
    db.add(mem)
    db.commit()

    token = create_access_token(user.id, email=user.email, extra_claims={"role": "audit_lead"})
    db.close()

    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}
    return client, headers, org_id

def test_observations_rfis_and_delta_reevaluation_lifecycle(client_with_auth):
    client, headers, org_id = client_with_auth

    # 1. Crear Proyecto en Ingeniería de Detalle
    res_proj = client.post("/api/v1/projects/", json={
        "code": "PRJ-OBS-01",
        "name": "Hospital Regional Norte",
        "discipline": "architecture",
        "stage": "Ingeniería de Detalle",
        "project_type": "hospitalario"
    }, headers=headers)
    assert res_proj.status_code == 201
    project_id = res_proj.json()["id"]

    # 2. Crear Documento y Lámina inicial en el proyecto
    db = SessionLocal()
    doc_id = str(uuid.uuid4())
    doc = Document(
        id=doc_id,
        organization_id=org_id,
        project_id=project_id,
        filename="ARQ-HOSP-01_Planta_General.pdf",
        file_path="/data/test/ARQ-HOSP-01.pdf",
        file_hash_sha256=f"hash-{doc_id[:16]}",
        file_size_bytes=204800,
        mime_type="application/pdf",
        page_count=1,
        status="ready"
    )
    sheet_id = str(uuid.uuid4())
    sheet = DocumentSheet(
        id=sheet_id,
        document_id=doc_id,
        sheet_number=1,
        sheet_code="ARQ-01",
        title="Planta Nivel 1 Hospital",
        width_px=1189,
        height_px=841,
        dpi=150
    )
    db.add(doc)
    db.add(sheet)
    db.commit()
    db.close()

    # 3. Clasificar el documento como plano_general y apto como evidencia para la planta
    res_class = client.post(f"/api/v1/completeness/documents/{doc_id}/classify", json={
        "deliverable_type": "plano_general",
        "readiness_status": "eligible_as_evidence"
    }, headers=headers)
    assert res_class.status_code == 200

    # 4. Evaluar la lámina -> Como faltan EETT obligatorias, RULE_REQUIRED_TABLES_V1 se bloquea preventivamente
    res_eval = client.post(f"/api/v1/rules/sheets/{sheet_id}", headers=headers)
    assert res_eval.status_code == 200
    findings = res_eval.json()
    assert len(findings) > 0

    # 5. Generar Formalmente Observaciones y RFIs desde los hallazgos
    res_gen = client.post("/api/v1/observations/generate-from-run", json={
        "project_id": project_id
    }, headers=headers)
    assert res_gen.status_code == 200
    observations = res_gen.json()
    assert len(observations) > 0

    # Verificar que existan códigos únicos diferenciados (BLK, RFI o OBS)
    codes = [o["code"] for o in observations]
    assert any(c.startswith("BLK-") or c.startswith("OBS-") or c.startswith("RFI-") for c in codes)

    target_obs = observations[0]
    obs_id = target_obs["id"]

    # 6. Emitir la observación formalmente si estaba en draft
    if target_obs["status"] == "draft":
        res_issue = client.post(f"/api/v1/observations/{obs_id}/issue", json={
            "assigned_to": "Consorcio Constructor Hospital",
            "notes": "Emitido para rectificación en entrega Rev 1"
        }, headers=headers)
        assert res_issue.status_code == 200
        assert res_issue.json()["status"] == "issued"

    # 7. Contratista ingresa respuesta técnica
    res_resp = client.post(f"/api/v1/observations/{obs_id}/response", json={
        "response_text": "Se adjunta nueva lámina con Cuadro de Puertas y EETT actualizadas.",
        "author_role": "contractor"
    }, headers=headers)
    assert res_resp.status_code == 200
    obs_after_resp = res_resp.json()
    assert obs_after_resp["status"] == "answered"
    assert len(obs_after_resp["responses"]) == 1

    # 8. Reingesta: Se carga un nuevo documento / versión provisionada
    db = SessionLocal()
    new_doc_id = str(uuid.uuid4())
    new_doc = Document(
        id=new_doc_id,
        organization_id=org_id,
        project_id=project_id,
        filename="EETT-HOSP-Rev1_Especificaciones.pdf",
        file_path="/data/test/EETT-HOSP-Rev1.pdf",
        file_hash_sha256=f"hash-{new_doc_id[:16]}",
        file_size_bytes=104800,
        mime_type="application/pdf",
        page_count=10,
        status="ready"
    )
    # Crear una tabla técnica requerida en la lámina
    table_id = str(uuid.uuid4())
    ext_table = ExtractedTable(
        id=table_id,
        document_id=doc_id,
        sheet_id=sheet_id,
        table_type="revision_table",
        title="CUADRO DE REVISIONES",
        bbox=[100, 100, 300, 150],
        bbox_normalized=[0.1, 0.1, 0.3, 0.15],
        row_count=2,
        column_count=2
    )
    c1 = ExtractedTableCell(id=str(uuid.uuid4()), table_id=table_id, row_index=0, column_index=0, is_header=True, text="REV", bbox=[100, 100, 200, 125], bbox_normalized=[0.1, 0.1, 0.2, 0.12])
    c2 = ExtractedTableCell(id=str(uuid.uuid4()), table_id=table_id, row_index=0, column_index=1, is_header=True, text="FECHA", bbox=[200, 100, 300, 125], bbox_normalized=[0.2, 0.1, 0.3, 0.12])
    db.add(new_doc)
    db.add(ext_table)
    db.add(c1)
    db.add(c2)
    db.commit()
    db.close()

    # 9. Provisionar evidencia vinculándola con la observación
    res_prov = client.post(f"/api/v1/observations/{obs_id}/provision", json={
        "document_id": new_doc_id,
        "notes": "EETT Rev 1 provisionadas para subsanar faltante"
    }, headers=headers)
    assert res_prov.status_code == 200
    assert res_prov.json()["status"] == "provisioned"
    assert res_prov.json()["provisioned_document_id"] == new_doc_id

    # 10. Re-ejecutar auditoría Delta focalizada
    res_delta = client.post(f"/api/v1/observations/{obs_id}/delta-reevaluation", headers=headers)
    assert res_delta.status_code == 200
    delta_data = res_delta.json()
    assert "affected_rules_evaluated" in delta_data
    assert "trace_entry" in delta_data

    # 11. Consultar detalle de la observación y verificar trazabilidad histórica antes/después
    res_final = client.get(f"/api/v1/observations/{obs_id}", headers=headers)
    assert res_final.status_code == 200
    final_obs = res_final.json()
    history = final_obs["history_trace"]
    assert len(history) >= 3
    actions = [h["action"] for h in history]
    assert "generated_from_finding" in actions
    assert "contractor_response" in actions
    assert "provision_evidence" in actions
    assert "delta_reevaluation" in actions
