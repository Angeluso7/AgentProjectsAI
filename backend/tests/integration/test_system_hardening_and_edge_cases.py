import os
import uuid
import pytest
from fastapi.testclient import TestClient
from app.db.models.core import User, Organization, OrganizationMembership, Project
from app.db.models.document_memory import Document, DocumentSheet
from app.db.models.decision_memory import RuleFinding, ReviewRun
from app.db.models.completeness import DocumentDeliverable
from app.core.security import hash_password, create_access_token

def test_system_hardening_and_edge_cases(client: TestClient, db_session):
    # 1. Setup Tenant y Usuarios
    org_id = str(uuid.uuid4())
    org = Organization(id=org_id, name="Hardening QA Org", slug=f"hard-{uuid.uuid4().hex[:6]}")
    db_session.add(org)

    user = User(
        id=str(uuid.uuid4()),
        email=f"lead_{uuid.uuid4().hex[:6]}@planreview.ai",
        display_name="Auditor Hardening",
        password_hash=hash_password("Password123!"),
        is_active=True,
        is_superuser=False
    )
    db_session.add(user)

    membership = OrganizationMembership(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        user_id=user.id,
        role="audit_lead",
        status="active"
    )
    db_session.add(membership)
    db_session.commit()

    token = create_access_token(subject=user.id, email=user.email, extra_claims={"org_id": org_id})
    headers = {"Authorization": f"Bearer {token}"}

    # =========================================================================
    # CASO BORDE 1: PROYECTO VACÍO (0 DOCUMENTOS, 0 HALLAZGOS)
    # =========================================================================
    empty_proj = Project(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        name="Proyecto Terreno Vacío",
        code="PRJ-EMPTY-01",
        discipline="architecture",
        settings={"stage": "Ingeniería de Detalle"}
    )
    db_session.add(empty_proj)
    db_session.commit()

    # Vista previa consolidada en proyecto vacío
    resp_empty = client.get(f"/api/v1/reports/consolidated/preview?project_id={empty_proj.id}", headers=headers)
    assert resp_empty.status_code == 200
    data_empty = resp_empty.json()
    assert data_empty["global_stage_verdict"] == "no_aprobable_bloqueada"
    assert data_empty["completeness"]["completeness_percentage"] == 0.0
    assert data_empty["completeness"]["eligible_count"] == 0
    assert data_empty["audit_verdicts"]["total_rules_evaluated"] == 0
    assert data_empty["observations"]["items"] == []

    # Emisión formal de snapshot para proyecto vacío y descarga de PDF/JSON
    emit_empty = client.post("/api/v1/reports/consolidated/emit", json={"project_id": empty_proj.id}, headers=headers)
    assert emit_empty.status_code == 200
    snap_empty = emit_empty.json()
    assert snap_empty["revision_number"] == 1
    assert snap_empty["global_stage_verdict"] == "no_aprobable_bloqueada"

    pdf_empty = client.get(f"/api/v1/reports/consolidated/snapshots/{snap_empty['id']}/download/pdf", headers=headers)
    assert pdf_empty.status_code == 200
    assert pdf_empty.content.startswith(b"%PDF-1.4")

    # =========================================================================
    # CASO BORDE 2: CAMBIO DINÁMICO DE ETAPA (Básica -> Detalle)
    # =========================================================================
    proj_stage = Project(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        name="Proyecto Evolución de Etapa",
        code="PRJ-STAGE-01",
        discipline="architecture",
        settings={"stage": "Ingeniería Básica"}
    )
    db_session.add(proj_stage)
    db_session.commit()

    # Evaluación en Ingeniería Básica
    comp_basica = client.get(f"/api/v1/completeness/projects/{proj_stage.id}", headers=headers)
    assert comp_basica.status_code == 200
    basica_data = comp_basica.json()
    assert basica_data["stage"] == "Ingeniería Básica"
    basica_req_count = len(basica_data["deliverables_matrix"])

    # Cambiar etapa a Ingeniería de Detalle
    update_resp = client.put(f"/api/v1/projects/{proj_stage.id}", json={"stage": "Ingeniería de Detalle"}, headers=headers)
    assert update_resp.status_code == 200
    assert update_resp.json()["stage"] == "Ingeniería de Detalle"

    # Re-evaluación automática en Ingeniería de Detalle
    comp_detalle = client.get(f"/api/v1/completeness/projects/{proj_stage.id}", headers=headers)
    assert comp_detalle.status_code == 200
    detalle_data = comp_detalle.json()
    assert detalle_data["stage"] == "Ingeniería de Detalle"
    detalle_req_count = len(detalle_data["deliverables_matrix"])
    # Detalle tiene más requisitos que Básica
    assert detalle_req_count > basica_req_count

    # =========================================================================
    # CASO BORDE 3: DOCUMENTO ARCHIVADO / SOFT-DELETE NO CUENTA COMO EVIDENCIA
    # =========================================================================
    doc = Document(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        project_id=proj_stage.id,
        filename="Plano_Arquitectura_Inicial.pdf",
        file_path="storage/raw/Plano_Arquitectura_Inicial.pdf",
        file_hash_sha256="dummy_sha256_hash_1111111111111111",
        file_size_bytes=102400,
        status="active"
    )
    db_session.add(doc)
    db_session.commit()

    # Clasificar documento como apto para evidencia
    client.post(f"/api/v1/completeness/documents/{doc.id}/classify", json={
        "deliverable_type": "plano_general",
        "readiness_status": "eligible_as_evidence"
    }, headers=headers)

    # Verificar que ahora el entregable plano_general está cumplido
    comp_with_doc = client.get(f"/api/v1/completeness/projects/{proj_stage.id}", headers=headers).json()
    assert comp_with_doc["eligible_count"] >= 1

    # Archivar el documento (soft delete)
    del_resp = client.delete(f"/api/v1/documents/{doc.id}?hard_delete=false", headers=headers)
    assert del_resp.status_code == 200

    # Re-evaluar completitud: el documento archivado NO debe ser considerado evidencia activa
    comp_after_archive = client.get(f"/api/v1/completeness/projects/{proj_stage.id}", headers=headers).json()
    assert comp_after_archive["eligible_count"] == 0

    # =========================================================================
    # CASO BORDE 4: OBSERVACIÓN CERRADA Y POSTERIOR REAPERTURA FORMAL
    # =========================================================================
    doc_active = Document(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        project_id=proj_stage.id,
        filename="Plano_Definitivo_Piso1.pdf",
        file_path="storage/raw/Plano_Definitivo_Piso1.pdf",
        file_hash_sha256="dummy_sha256_hash_2222222222222222",
        file_size_bytes=102400,
        status="active"
    )
    db_session.add(doc_active)
    db_session.commit()

    sheet = DocumentSheet(
        id=str(uuid.uuid4()),
        document_id=doc_active.id,
        sheet_number=1,
        sheet_code="A-01",
        title="Planta Arquitectura Primer Piso",
        width_px=3000,
        height_px=2000,
        width_mm=841.0,
        height_mm=594.0,
        dpi=150
    )
    db_session.add(sheet)
    db_session.commit()

    run = ReviewRun(
        id=str(uuid.uuid4()),
        project_id=proj_stage.id,
        organization_id=org_id,
        run_name="Auditoría QA Automatizada",
        status="completed"
    )
    db_session.add(run)
    db_session.commit()

    finding = RuleFinding(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        review_run_id=run.id,
        document_id=doc_active.id,
        sheet_id=sheet.id,
        rule_code="RULE_TITLE_BLOCK_REQUIRED_FIELDS_V1",
        rule_name="Verificación de Viñeta Técnica",
        category="formal",
        severity="medium",
        title="Falta indicar escala en viñeta",
        description="La viñeta no posee campo legible de escala.",
        status="open",
        evidence_refs={"verdict": "no_cumple"}
    )
    db_session.add(finding)
    db_session.commit()

    # Generar observación formal
    obs_list = client.post("/api/v1/observations/generate-from-run", json={"project_id": proj_stage.id}, headers=headers).json()
    assert len(obs_list) >= 1
    obs_id = obs_list[0]["id"]

    # Provisionar evidencia y ejecutar re-evaluación delta -> Cierre
    client.post(f"/api/v1/observations/{obs_id}/provision", json={"document_id": doc_active.id, "notes": "Viñeta actualizada"}, headers=headers)
    delta_resp = client.post(f"/api/v1/observations/{obs_id}/delta-reevaluation", headers=headers)
    assert delta_resp.status_code == 200

    obs_detail = client.get(f"/api/v1/observations/{obs_id}", headers=headers).json()
    # Si cerró o cambió de estado
    assert obs_detail["status"] in ["closed", "issued", "answered", "provisioned"]

    # Forzar reapertura formal
    reopen_resp = client.post(f"/api/v1/observations/{obs_id}/reopen", json={
        "reason": "Revisión posterior detectó que la escala indicada es errónea (1:50 en vez de 1:100)."
    }, headers=headers)
    assert reopen_resp.status_code == 200
    obs_reopened = reopen_resp.json()
    assert obs_reopened["status"] == "issued"
    assert any(t["action"] == "reopen_observation" for t in obs_reopened["history_trace"])

    # =========================================================================
    # CASO BORDE 5: INMUTABILIDAD DE SNAPSHOTS VS EVOLUCIÓN POSTERIOR
    # =========================================================================
    emit_rev1 = client.post("/api/v1/reports/consolidated/emit", json={
        "project_id": proj_stage.id,
        "title": "Corte de Revisión 1"
    }, headers=headers).json()
    rev1_id = emit_rev1["id"]
    assert emit_rev1["revision_number"] == 1

    # Modificar el proyecto (archivar observación, cambiar datos)
    client.post(f"/api/v1/observations/{obs_id}/response", json={
        "response_text": "Aclaración técnica final enviada por contratista",
        "author_role": "contractor"
    }, headers=headers)

    # El snapshot Rev 1 previo NO debe mutar
    snap1_again = client.get(f"/api/v1/reports/consolidated/snapshots/{rev1_id}", headers=headers).json()
    assert snap1_again["revision_number"] == 1
    assert snap1_again["title"] == "Corte de Revisión 1"

    # Emitir Snapshot Rev 2
    emit_rev2 = client.post("/api/v1/reports/consolidated/emit", json={
        "project_id": proj_stage.id,
        "title": "Corte de Revisión 2 Final"
    }, headers=headers).json()
    assert emit_rev2["revision_number"] == 2
    assert emit_rev2["delta_evolution"]["previous_revision_number"] == 1

    # Listar historial de snapshots
    snaps_list = client.get(f"/api/v1/reports/consolidated/snapshots?project_id={proj_stage.id}", headers=headers).json()
    assert len(snaps_list) == 2
    assert snaps_list[0]["revision_number"] == 2
    assert snaps_list[1]["revision_number"] == 1
