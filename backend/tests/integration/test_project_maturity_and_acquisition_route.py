import uuid
from datetime import datetime
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import Base, engine, get_db
from app.core.security import create_access_token
from app.db.models.core import User, Organization, OrganizationMembership, Project
from app.db.models.document_memory import Document, DocumentSheet
from app.db.models.intake import SourceAsset
from app.db.models.decision_memory import RuleDefinition
from app.db.models.knowledge_base import KnowledgeItem, KnowledgeChunk
from app.db.models.maturity import ProjectMaturityProfile

@pytest.fixture
def test_setup(db_session):

    # 1. Crear Organización
    org = Organization(
        id=str(uuid.uuid4()),
        name="Constructora Madurez Informacional SpA",
        slug=f"madurez-spa-{uuid.uuid4().hex[:6]}"
    )
    db_session.add(org)

    # 2. Crear Usuario Auditor
    user = User(
        id=str(uuid.uuid4()),
        email=f"auditor-madurez-{uuid.uuid4().hex[:6]}@madurez.cl",
        display_name="Auditor de Madurez Informacional",
        password_hash="mock_hash_madurez"
    )
    db_session.add(user)

    mem = OrganizationMembership(
        id=str(uuid.uuid4()),
        organization_id=org.id,
        user_id=user.id,
        role="admin"
    )
    db_session.add(mem)

    # 3. Crear Proyecto Inicialmente Vacío (Sin Documentos ni Normativas)
    proj = Project(
        id=str(uuid.uuid4()),
        organization_id=org.id,
        name="Torre Costanera Sur",
        code="PRJ-TCS-2026",
        settings={"stage": "Ingeniería Básica"},
        discipline="architecture"
    )
    db_session.add(proj)

    # 4. Crear Reglas QA/QC Activas
    rule1 = RuleDefinition(
        id=str(uuid.uuid4()),
        code=f"R-ARQ-{uuid.uuid4().hex[:6]}",
        name="Ancho Mínimo de Puertas Habitables",
        category="geometry_qa",
        discipline="architecture",
        description="Verifica ancho mínimo de puertas",
        is_active=True,
        severity_default="critical"
    )
    db_session.add(rule1)

    rule2 = RuleDefinition(
        id=str(uuid.uuid4()),
        code=f"R-EST-{uuid.uuid4().hex[:6]}",
        name="Verificación de Cuantía de Acero en Muros",
        category="normative_compliance",
        discipline="structures",
        description="Verifica cuantía de acero en muros",
        is_active=True,
        severity_default="critical"
    )
    db_session.add(rule2)

    db_session.commit()

    token = create_access_token(subject=user.id, email=user.email, extra_claims={"role": "admin", "org_id": org.id})
    client = TestClient(app)

    org_id = org.id
    proj_id = proj.id
    user_id = user.id

    return {
        "client": client,
        "token": token,
        "org_id": org_id,
        "proj_id": proj_id,
        "user_id": user_id,
        "db": db_session
    }

def test_initial_insufficient_project_maturity(test_setup):
    client = test_setup["client"]
    token = test_setup["token"]
    org_id = test_setup["org_id"]
    proj_id = test_setup["proj_id"]
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

    # 1. Obtener perfil inicial de madurez para proyecto sin datos
    resp = client.get(f"/api/v1/projects/{proj_id}/maturity/latest", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    # REGLA OBLIGATORIA: Estado Inicial Insuficiente
    assert data["maturity_level"] == "insufficient"
    assert data["overall_score"] < 35.0
    assert data["is_target_achieved"] is False
    assert len(data["critical_gaps"]) >= 2

    # Verificar que el diagnóstico refleje bloqueo de auditoría
    cap = data["review_capability_assessment"]
    assert cap["can_issue_stage_verdict"] is False
    assert "bloqueada" in cap["blind_blocked_scope"].lower() or "bloqueadas" in cap["blind_blocked_scope"].lower()

def test_acquisition_routes_generation(test_setup):
    client = test_setup["client"]
    token = test_setup["token"]
    org_id = test_setup["org_id"]
    proj_id = test_setup["proj_id"]
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

    # 2. Consultar Rutas Sugeridas de Adquisición de Información
    routes_resp = client.get(f"/api/v1/projects/{proj_id}/maturity/acquisition-routes", headers=headers)
    assert routes_resp.status_code == 200
    routes = routes_resp.json()
    assert len(routes) >= 2

    # Verificar que cada ruta sea estructurada y accionable
    for r in routes:
        assert "suggested_responsible" in r
        assert "intake_method" in r
        assert "unlock_impact" in r
        assert r["estimated_score_gain"] > 0.0

def test_maturity_evolution_after_knowledge_incorporation(test_setup):
    client = test_setup["client"]
    token = test_setup["token"]
    org_id = test_setup["org_id"]
    proj_id = test_setup["proj_id"]
    db = test_setup["db"]
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

    # 3. Evaluación Inicial (Línea Base Vacía)
    init_resp = client.get(f"/api/v1/projects/{proj_id}/maturity/latest", headers=headers)
    assert init_resp.status_code == 200
    initial_score = init_resp.json()["overall_score"]

    # 4. Incorporar Información Real al Proyecto:
    # A. Cargar Documentos y Láminas
    doc1 = Document(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        project_id=proj_id,
        filename="A-01-Planta-Arquitectura.pdf",
        file_path="/storage/A-01.pdf",
        file_hash_sha256=uuid.uuid4().hex,
        file_size_bytes=102400,
        status="ready"
    )
    db.add(doc1)
    db.flush()

    sheet1 = DocumentSheet(
        id=str(uuid.uuid4()),
        document_id=doc1.id,
        sheet_number=1,
        sheet_code="A-01",
        title="Planta General Piso 1",
        width_px=3000,
        height_px=2000
    )
    db.add(sheet1)

    doc2 = Document(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        project_id=proj_id,
        filename="E-01-Memoria-Calculo-Estructural.pdf",
        file_path="/storage/E-01.pdf",
        file_hash_sha256=uuid.uuid4().hex,
        file_size_bytes=204800,
        status="ready"
    )
    db.add(doc2)

    # B. Registrar Fuente Normativa
    source_norm = SourceAsset(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        project_id=proj_id,
        source_type="normative_document",
        source_origin="file_upload",
        discipline="architecture",
        title="OGUC - Ordenanza General de Urbanismo y Construcciones",
        approval_status="approved",
        mime_type="application/pdf",
        version="1.0",
        status="active",
        owner="auditor",
        linked_memory_target="normative_memory"
    )
    db.add(source_norm)

    # C. Aprobar KnowledgeItem en Base de Conocimiento
    kb_item = KnowledgeItem(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        project_id=proj_id,
        domain="normative_knowledge",
        item_type="normative_article",
        title="OGUC Art. 4.1.7: Ancho Mínimo de Puertas",
        content_text="Las puertas de recintos habitables deberán tener un ancho libre mínimo de 0.85 m.",
        status="approved_for_reuse",
        is_active_for_reuse=True,
        author="auditor_lead"
    )
    db.add(kb_item)
    db.flush()

    chunk = KnowledgeChunk(
        id=str(uuid.uuid4()),
        knowledge_item_id=kb_item.id,
        chunk_index=0,
        chunk_title="Puertas Habitables",
        chunk_text="Las puertas de recintos habitables deberán tener un ancho libre mínimo de 0.85 m.",
        token_count=16,
        metadata_payload={"domain": "normative_knowledge"}
    )
    db.add(chunk)
    db.commit()

    # 4. Re-evaluar Madurez del Proyecto
    eval_resp = client.post(f"/api/v1/projects/{proj_id}/maturity/evaluate", json={
        "stage": "Ingeniería Básica",
        "target_level": "advanced",
        "evaluated_by": "auditor_senior_qa"
    }, headers=headers)

    assert eval_resp.status_code == 200
    updated_profile = eval_resp.json()

    # REGLA OBLIGATORIA: El Perfil Mejora Sustancialmente
    assert updated_profile["overall_score"] > 35.0
    assert updated_profile["maturity_level"] in ["intermediate", "advanced", "basic"]
    assert updated_profile["delta_summary"]["score_delta"] > 0.0
    assert updated_profile["delta_summary"]["level_changed"] is True

    # 5. Ejecutar Interacción con el Asistente RAG usando este Proyecto
    exec_resp = client.post("/api/v1/assistant/execute", json={
        "task_type": "normative_query",
        "prompt": "¿Cuál es el ancho de puertas exigido?",
        "project_id": proj_id,
        "stage": "Ingeniería Básica",
        "discipline": "architecture"
    }, headers=headers)
    assert exec_resp.status_code == 200

    # 6. Re-evaluar nuevamente para verificar Trazabilidad de Uso por el Asistente
    eval_resp_2 = client.post(f"/api/v1/projects/{proj_id}/maturity/evaluate", json={
        "stage": "Ingeniería Básica",
        "target_level": "advanced"
    }, headers=headers)
    assert eval_resp_2.status_code == 200
    profile_with_asst = eval_resp_2.json()

    assert profile_with_asst["assistant_usage_summary"]["total_interactions"] >= 1
    assert profile_with_asst["assistant_usage_summary"]["project_chunks_used_count"] >= 1

    # 7. Exportar Perfil en Formato JSON con Hash SHA-256
    profile_id = profile_with_asst["id"]
    export_resp = client.get(f"/api/v1/projects/{proj_id}/maturity/{profile_id}/export", headers=headers)
    assert export_resp.status_code == 200
    export_data = export_resp.json()
    assert "manifest_hash" in export_data
    assert len(export_data["manifest_hash"]) == 64
    assert export_data["overall_score"] == profile_with_asst["overall_score"]
