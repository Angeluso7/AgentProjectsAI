import pytest
import uuid
import os
import json
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import SessionLocal
from app.db.models.core import User, Organization, OrganizationMembership, Project
from app.db.models.document_memory import Document, DocumentSheet, ExtractedTable, ExtractedTableCell
from app.core.security import create_access_token

@pytest.fixture
def client_with_auth():
    db: Session = SessionLocal()
    unique_suffix = str(uuid.uuid4())[:8]
    org_id = f"test-org-rep-{unique_suffix}"
    user_id = f"test-user-rep-{unique_suffix}"
    
    org = Organization(id=org_id, name="Org Reports Test", slug=f"org-rep-{unique_suffix}")
    user = User(id=user_id, email=f"lead-rep-{unique_suffix}@test.com", display_name="Auditor Principal", password_hash="fake", is_active=True)
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

def test_consolidated_stage_report_full_lifecycle(client_with_auth):
    client, headers, org_id = client_with_auth

    # 1. Crear Proyecto con Etapa Activa
    res_proj = client.post("/api/v1/projects/", json={
        "code": "PRJ-REP-01",
        "name": "Centro Logístico San Bernardo",
        "discipline": "architecture",
        "stage": "Ingeniería de Detalle",
        "project_type": "industrial"
    }, headers=headers)
    assert res_proj.status_code == 201
    project_id = res_proj.json()["id"]

    # 2. Cargar Documento inicial (Plano General sin EETT)
    db = SessionLocal()
    doc_id = str(uuid.uuid4())
    doc = Document(
        id=doc_id,
        organization_id=org_id,
        project_id=project_id,
        filename="ARQ-01_Planta_General.pdf",
        file_path="/data/test/ARQ-01.pdf",
        file_hash_sha256=f"hash-{doc_id[:16]}",
        file_size_bytes=300000,
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
        title="Planta Centro Logistico",
        width_px=1189,
        height_px=841,
        dpi=150
    )
    db.add(doc)
    db.add(sheet)
    db.commit()
    db.close()

    # Clasificar el plano como apto para evidencia
    res_class = client.post(f"/api/v1/completeness/documents/{doc_id}/classify", json={
        "deliverable_type": "plano_general",
        "readiness_status": "eligible_as_evidence"
    }, headers=headers)
    assert res_class.status_code == 200

    # 3. Evaluar reglas sobre la lámina -> Se generan veredictos preventivos por falta de EETT
    res_eval = client.post(f"/api/v1/rules/sheets/{sheet_id}", headers=headers)
    assert res_eval.status_code == 200

    # 4. Generar formalmente observaciones y RFIs
    res_gen_obs = client.post("/api/v1/observations/generate-from-run", json={
        "project_id": project_id
    }, headers=headers)
    assert res_gen_obs.status_code == 200
    observations_rev1 = res_gen_obs.json()
    assert len(observations_rev1) > 0

    # 5. Vista Previa en Vivo del Reporte Consolidado
    res_prev1 = client.get(f"/api/v1/reports/consolidated/preview?project_id={project_id}", headers=headers)
    assert res_prev1.status_code == 200
    prev1_data = res_prev1.json()
    assert prev1_data["global_stage_verdict"] == "no_aprobable_bloqueada"
    assert prev1_data["completeness"]["is_gate_passed"] is False
    assert prev1_data["revision_number"] == 1

    # 6. Emitir Snapshot Formal Rev 1
    res_emit1 = client.post("/api/v1/reports/consolidated/emit", json={
        "project_id": project_id,
        "title": "Corte de Auditoría Inicial Rev 1 — Ingeniería de Detalle",
        "notes": "Emisión inicial: Gatekeeper bloqueado por faltante de EETT y Cuadros Técnicos."
    }, headers=headers)
    assert res_emit1.status_code == 200
    snap1 = res_emit1.json()
    snap1_id = snap1["id"]
    assert snap1["revision_number"] == 1
    assert snap1["global_stage_verdict"] == "no_aprobable_bloqueada"
    assert snap1["manifest_hash"] is not None

    # Verificar descarga JSON y PDF de Rev 1
    res_dl_json = client.get(f"/api/v1/reports/consolidated/snapshots/{snap1_id}/download/json", headers=headers)
    assert res_dl_json.status_code == 200
    assert "application/json" in res_dl_json.headers["content-type"]

    res_dl_pdf = client.get(f"/api/v1/reports/consolidated/snapshots/{snap1_id}/download/pdf", headers=headers)
    assert res_dl_pdf.status_code == 200
    assert "application/pdf" in res_dl_pdf.headers["content-type"]

    # 7. Subsanar faltante: Reingesta, provisión de documento EETT y Cuadro de Revisiones
    target_obs = observations_rev1[0]
    obs_id = target_obs["id"]

    db = SessionLocal()
    new_doc_id = str(uuid.uuid4())
    new_doc = Document(
        id=new_doc_id,
        organization_id=org_id,
        project_id=project_id,
        filename="EETT-LOG-01_Especificaciones_Tecnicas.pdf",
        file_path="/data/test/EETT-LOG-01.pdf",
        file_hash_sha256=f"hash-{new_doc_id[:16]}",
        file_size_bytes=150000,
        mime_type="application/pdf",
        page_count=8,
        status="ready"
    )
    # Crear Cuadro Técnico en la lámina para resolver la regla
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

    # Clasificar EETT como aptas
    client.post(f"/api/v1/completeness/documents/{new_doc_id}/classify", json={
        "deliverable_type": "especificaciones_tecnicas",
        "readiness_status": "eligible_as_evidence"
    }, headers=headers)

    # Provisionar evidencia a la observación y ejecutar re-evaluación delta
    res_prov = client.post(f"/api/v1/observations/{obs_id}/provision", json={
        "document_id": new_doc_id,
        "notes": "EETT provisionadas para subsanar bloqueo"
    }, headers=headers)
    assert res_prov.status_code == 200

    res_delta = client.post(f"/api/v1/observations/{obs_id}/delta-reevaluation", headers=headers)
    assert res_delta.status_code == 200

    # 8. Emitir Snapshot Formal Rev 2 (Cierre de Etapa)
    res_emit2 = client.post("/api/v1/reports/consolidated/emit", json={
        "project_id": project_id,
        "title": "Corte de Auditoría Final Rev 2 — Ingeniería de Detalle",
        "notes": "Emisión final con EETT incorporadas y reglas re-evaluadas."
    }, headers=headers)
    assert res_emit2.status_code == 200
    snap2 = res_emit2.json()
    assert snap2["revision_number"] == 2

    # Verificar que el seguimiento delta de Rev 2 referencia a Rev 1
    delta_data = snap2["delta_evolution"]
    assert delta_data["previous_revision_number"] == 1
    assert "summary_narrative" in delta_data

    # 9. Listar snapshots del proyecto
    res_snaps = client.get(f"/api/v1/reports/consolidated/snapshots?project_id={project_id}", headers=headers)
    assert res_snaps.status_code == 200
    snapshots_list = res_snaps.json()
    assert len(snapshots_list) == 2
    assert snapshots_list[0]["revision_number"] == 2
    assert snapshots_list[1]["revision_number"] == 1
