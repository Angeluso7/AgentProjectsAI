import pytest
import uuid
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import SessionLocal
from app.db.models.core import User, Organization, OrganizationMembership, Project
from app.db.models.document_memory import Document, DocumentSheet
from app.core.security import create_access_token

@pytest.fixture
def client_with_auth():
    db: Session = SessionLocal()
    unique_suffix = str(uuid.uuid4())[:8]
    org_id = f"test-org-comp-{unique_suffix}"
    user_id = f"test-user-comp-{unique_suffix}"
    
    org = Organization(id=org_id, name="Org Completeness Test", slug=f"org-comp-{unique_suffix}")
    user = User(id=user_id, email=f"lead-{unique_suffix}@test.com", display_name="Audit Lead", password_hash="fake", is_active=True)
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

def test_completeness_and_verdicts_lifecycle(client_with_auth):
    client, headers, org_id = client_with_auth

    # 1. Crear Proyecto en Ingeniería de Detalle
    res_proj = client.post("/api/v1/projects/", json={
        "code": "PRJ-COMP-01",
        "name": "Edificio Los Condores",
        "discipline": "architecture",
        "stage": "Ingeniería de Detalle",
        "project_type": "edificacion"
    }, headers=headers)
    assert res_proj.status_code == 201
    project = res_proj.json()
    project_id = project["id"]

    # 2. Consultar requisitos estándar de Ingeniería de Detalle
    res_reqs = client.get("/api/v1/completeness/requirements?stage=Ingeniería de Detalle", headers=headers)
    assert res_reqs.status_code == 200
    reqs = res_reqs.json()
    assert len(reqs) > 0
    assert any(r["deliverable_type"] == "plano_general" for r in reqs)
    assert any(r["deliverable_type"] == "especificaciones_tecnicas" for r in reqs)

    # 3. Evaluar completitud inicial (sin documentos) -> Gatekeeper Bloqueado
    res_comp_0 = client.get(f"/api/v1/completeness/projects/{project_id}", headers=headers)
    assert res_comp_0.status_code == 200
    comp_0 = res_comp_0.json()
    assert comp_0["completeness_percentage"] == 0.0
    assert comp_0["is_gate_passed"] is False
    assert comp_0["missing_mandatory_count"] > 0
    assert comp_0["blocked_rules_count"] > 0
    assert "RULE_DOOR_COUNT_MATCH_V1" in comp_0["blocked_rule_codes"]

    # 4. Crear un Documento (Plano de Planta) en el proyecto
    db = SessionLocal()
    doc_id = str(uuid.uuid4())
    doc = Document(
        id=doc_id,
        organization_id=org_id,
        project_id=project_id,
        filename="ARQ-01_Planta_General.pdf",
        file_path="/data/test/ARQ-01.pdf",
        file_hash_sha256=f"hash-{doc_id[:16]}",
        file_size_bytes=102400,
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
        title="Planta Nivel 1",
        width_px=1189,
        height_px=841,
        dpi=150
    )
    db.add(doc)
    db.add(sheet)
    db.commit()
    db.close()

    # 5. Clasificar el documento como 'plano_general' en estado 'uploaded'
    res_class_1 = client.post(f"/api/v1/completeness/documents/{doc_id}/classify", json={
        "deliverable_type": "plano_general",
        "readiness_status": "uploaded",
        "validation_notes": "Cargado sin validar"
    }, headers=headers)
    assert res_class_1.status_code == 200
    assert res_class_1.json()["readiness_status"] == "uploaded"

    # Chequeo: sigue sin ser 'eligible_as_evidence', por lo que no cumple el requisito
    res_comp_1 = client.get(f"/api/v1/completeness/projects/{project_id}", headers=headers)
    assert res_comp_1.json()["is_gate_passed"] is False

    # 6. Promover el documento a 'eligible_as_evidence' (Apto como Evidencia)
    res_readiness = client.put(f"/api/v1/completeness/documents/{doc_id}/readiness", json={
        "readiness_status": "eligible_as_evidence",
        "validation_notes": "Revisado y validado formalmente por Auditor Lead"
    }, headers=headers)
    assert res_readiness.status_code == 200
    assert res_readiness.json()["readiness_status"] == "eligible_as_evidence"

    # 7. Evaluar completitud post-promoción
    res_comp_2 = client.post(f"/api/v1/completeness/projects/{project_id}/evaluate", headers=headers)
    assert res_comp_2.status_code == 200
    comp_2 = res_comp_2.json()
    assert comp_2["eligible_count"] >= 1
    assert comp_2["completeness_percentage"] > 0.0

    # 8. Ejecutar RuleEngine sobre la lámina y verificar 4 veredictos canónicos
    # Dado que aún faltan EETT, las reglas que requieren EETT se bloquean con 'no_verificable' y reason 'blocked_by_missing_doc'
    res_rule_eval = client.post(f"/api/v1/rules/sheets/{sheet_id}", headers=headers)
    assert res_rule_eval.status_code == 200
    findings = res_rule_eval.json()
    assert isinstance(findings, list)

    # Verificar ejecuciones de reglas persistidas en base de datos
    db = SessionLocal()
    from app.db.models.decision_memory import RuleExecution
    executions = db.query(RuleExecution).filter(RuleExecution.sheet_id == sheet_id).all()
    assert len(executions) > 0
    verdicts = [ex.result_summary.get("verdict") for ex in executions if ex.result_summary]
    assert any(v in ["cumple", "no_cumple", "no_verificable", "no_aplica"] for v in verdicts)
    db.close()
