import uuid
from datetime import datetime
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import Base, engine, get_db
from app.core.security import create_access_token
from app.db.models.core import User, Organization, OrganizationMembership, Project
from app.db.models.knowledge_base import KnowledgeItem, KnowledgeChunk
from app.db.models.assistant import AssistantInteraction

@pytest.fixture
def test_setup(db_session):

    # 1. Crear Organización
    org = Organization(
        id=str(uuid.uuid4()),
        name="Constructora Asistente RAG Corp",
        slug=f"asistente-rag-{uuid.uuid4().hex[:6]}"
    )
    db_session.add(org)

    # 2. Crear Usuario Auditor
    user = User(
        id=str(uuid.uuid4()),
        email=f"auditor-rag-{uuid.uuid4().hex[:6]}@ragcorp.cl",
        display_name="Auditor RAG Lead",
        password_hash="mock_hash_rag"
    )
    db_session.add(user)

    mem = OrganizationMembership(
        id=str(uuid.uuid4()),
        organization_id=org.id,
        user_id=user.id,
        role="admin"
    )
    db_session.add(mem)

    # 3. Crear Proyecto
    proj = Project(
        id=str(uuid.uuid4()),
        organization_id=org.id,
        name="Edificio Parque Oriente",
        code="PRJ-PO-2026",
        settings={"stage": "Ingeniería Básica"},
        discipline="architecture"
    )
    db_session.add(proj)

    # 4. Crear KnowledgeItem APROBADO (elegible para RAG)
    item_approved = KnowledgeItem(
        id=str(uuid.uuid4()),
        organization_id=org.id,
        project_id=proj.id,
        domain="normative_knowledge",
        item_type="normative_article",
        title="OGUC Art. 4.1.7: Ancho Mínimo de Puertas Habitables",
        summary="Las puertas de recintos habitables deberán tener un ancho libre mínimo de 0.85 m.",
        content_text="Las puertas de recintos habitables deberán tener un ancho libre mínimo de 0.85 m en vías de evacuación y accesos.",
        structured_payload={"standard": "OGUC", "article": "4.1.7", "min_width_m": 0.85},
        discipline="architecture",
        stage="Ingeniería Básica",
        status="approved_for_reuse",
        is_active_for_reuse=True,
        confidence_score=1.0,
        author=user.email,
        origin_type="manual_curation",
        tags=["puertas", "ancho_minimo", "oguc"]
    )
    db_session.add(item_approved)
    db_session.flush()

    chunk_approved = KnowledgeChunk(
        id=str(uuid.uuid4()),
        knowledge_item_id=item_approved.id,
        chunk_index=0,
        chunk_title="Ancho Libre Puertas OGUC 4.1.7",
        chunk_text="Las puertas de recintos habitables deberán tener un ancho libre mínimo de 0.85 m.",
        token_count=18,
        metadata_payload={"domain": "normative_knowledge", "discipline": "architecture"}
    )
    db_session.add(chunk_approved)

    # 5. Crear KnowledgeItem NO APROBADO (en draft, debe ser excluido de RAG)
    item_draft = KnowledgeItem(
        id=str(uuid.uuid4()),
        organization_id=org.id,
        project_id=proj.id,
        domain="normative_knowledge",
        item_type="draft_memo",
        title="Borrador no revisado de alturas",
        summary="Texto preliminar sin validación",
        content_text="Texto en borrador no aprobado para reutilización.",
        discipline="architecture",
        status="draft",
        is_active_for_reuse=False,
        confidence_score=0.2,
        author="unknown",
        origin_type="scraping",
        tags=["borrador"]
    )
    db_session.add(item_draft)
    db_session.flush()

    chunk_draft = KnowledgeChunk(
        id=str(uuid.uuid4()),
        knowledge_item_id=item_draft.id,
        chunk_index=0,
        chunk_title="Chunk Borrador",
        chunk_text="Texto en borrador no aprobado para reutilización.",
        token_count=10,
        metadata_payload={"domain": "normative_knowledge"}
    )
    db_session.add(chunk_draft)

    db_session.commit()

    token = create_access_token(subject=user.id, email=user.email, extra_claims={"role": "admin", "org_id": org.id})
    client = TestClient(app)

    item_approved_id = item_approved.id
    item_draft_id = item_draft.id

    return {
        "client": client,
        "token": token,
        "org_id": org.id,
        "proj_id": proj.id,
        "item_approved_id": item_approved_id,
        "item_draft_id": item_draft_id
    }

def test_assistant_task_catalog_and_routing(test_setup):
    client = test_setup["client"]
    token = test_setup["token"]
    org_id = test_setup["org_id"]
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

    # 1. Consultar Catálogo de Tareas Asistidas
    cat_resp = client.get("/api/v1/assistant/tasks", headers=headers)
    assert cat_resp.status_code == 200
    catalog = cat_resp.json()
    assert len(catalog) >= 8
    task_types = [t["task_type"] for t in catalog]
    assert "normative_query" in task_types
    assert "observation_rfi_draft" in task_types
    assert "stage_synthesis" in task_types
    assert "completeness_assistance" in task_types

def test_assistant_normative_query_rag_and_exclusion(test_setup):
    client = test_setup["client"]
    token = test_setup["token"]
    org_id = test_setup["org_id"]
    proj_id = test_setup["proj_id"]
    item_approved_id = test_setup["item_approved_id"]
    item_draft_id = test_setup["item_draft_id"]
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

    # 2. Ejecutar Consulta Normativa con RAG Activo
    exec_resp = client.post("/api/v1/assistant/execute", json={
        "task_type": "normative_query",
        "prompt": "¿Cuál es el ancho mínimo exigido para puertas habitables en OGUC?",
        "project_id": proj_id,
        "stage": "Ingeniería Básica",
        "discipline": "architecture"
    }, headers=headers)

    assert exec_resp.status_code == 200
    data = exec_resp.json()
    assert data["task_type"] == "normative_query"
    assert "Respuesta Normativa Asistida" in data["generated_response"]
    assert len(data["retrieved_sources"]) >= 1

    # Verificar que el ítem aprobado fue recuperado
    source_ids = [s["item_id"] for s in data["retrieved_sources"]]
    assert item_approved_id in source_ids

    # REGLA OBLIGATORIA: Verificar que el ítem en draft fue estrictamente EXCLUIDO
    assert item_draft_id not in source_ids

def test_assistant_tier_1_cheap_default_execution(test_setup):
    client = test_setup["client"]
    token = test_setup["token"]
    org_id = test_setup["org_id"]
    proj_id = test_setup["proj_id"]
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

    # 3. Tarea simple / checklist sin criticidad debe resolverse en Tier 1 (Gratis $0.00)
    exec_resp = client.post("/api/v1/assistant/execute", json={
        "task_type": "completeness_assistance",
        "prompt": "Verificar entregables obligatorios requeridos para el Gatekeeper.",
        "project_id": proj_id,
        "stage": "Ingeniería Básica",
        "discipline": "architecture",
        "context_data": {"severity": "low"}
    }, headers=headers)

    assert exec_resp.status_code == 200
    data = exec_resp.json()
    assert data["tier_used"] == 1
    assert data["engine_model_used"] == "fastapi_rule_reasoner"
    assert data["cost_estimate_usd"] == 0.0
    assert data["was_escalated"] is False

def test_assistant_dynamic_escalation_to_tier_3(test_setup):
    client = test_setup["client"]
    token = test_setup["token"]
    org_id = test_setup["org_id"]
    proj_id = test_setup["proj_id"]
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

    # 4. Tarea crítica o con severidad CRÍTICA debe escalar dinámicamente a Tier 3 (GPT-4o Premium)
    exec_resp = client.post("/api/v1/assistant/execute", json={
        "task_type": "observation_rfi_draft",
        "prompt": "Colapso de vía de evacuación por vano sub-dimensionado (0.70m vs 0.85m normativo).",
        "project_id": proj_id,
        "stage": "Ingeniería Básica",
        "discipline": "architecture",
        "context_data": {
            "severity": "critical",
            "code": "OBS-CRIT-001",
            "is_critical": True
        },
        "allow_escalation": True
    }, headers=headers)

    assert exec_resp.status_code == 200
    data = exec_resp.json()
    assert data["tier_used"] == 3
    assert data["engine_model_used"] == "claude_sonnet"
    assert data["was_escalated"] is True
    assert data["escalation_reason"] == "critical_severity"
    assert data["cost_estimate_usd"] > 0.0
    assert "OBS-CRIT-001" in data["generated_response"]
    assert data["structured_output"]["severity"] == "critical"

def test_assistant_interaction_logging_and_feedback(test_setup):
    client = test_setup["client"]
    token = test_setup["token"]
    org_id = test_setup["org_id"]
    proj_id = test_setup["proj_id"]
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

    # 5. Ejecutar tarea asistida de apoyo a revisión
    exec_resp = client.post("/api/v1/assistant/execute", json={
        "task_type": "review_support",
        "prompt": "Verificar tolerancia de descuadre en lámina A-02.",
        "project_id": proj_id,
        "stage": "Ingeniería Básica",
        "discipline": "architecture"
    }, headers=headers)
    assert exec_resp.status_code == 200
    interaction_id = exec_resp.json()["interaction_id"]

    # 6. Consultar Historial de Interacciones
    list_resp = client.get("/api/v1/assistant/interactions", headers=headers)
    assert list_resp.status_code == 200
    interactions = list_resp.json()
    assert len(interactions) >= 1
    target_inter = next((i for i in interactions if i["id"] == interaction_id), None)
    assert target_inter is not None
    assert target_inter["feedback_status"] == "pending"

    # 7. Registrar Feedback del Auditor (Aceptar y Aplicar)
    feed_resp = client.post(f"/api/v1/assistant/interactions/{interaction_id}/feedback", json={
        "status": "accepted",
        "feedback_notes": "Sugerencia validada y aceptada por el auditor líder.",
        "edited_payload": {"applied": True}
    }, headers=headers)

    assert feed_resp.status_code == 200
    updated_inter = feed_resp.json()
    assert updated_inter["feedback_status"] == "accepted"
    assert updated_inter["feedback_payload"]["notes"] == "Sugerencia validada y aceptada por el auditor líder."
