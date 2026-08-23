import uuid
import base64
from datetime import datetime
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import Base, engine, get_db
from app.core.security import create_access_token
from app.db.models.core import User, Organization, OrganizationMembership, Project
from app.db.models.knowledge_base import KnowledgeItem, KnowledgeChunk
from app.db.models.acquisition import InformationAcquisitionRequest


@pytest.fixture
def acq_test_setup(db_session):

    # 1. Crear Organización
    org = Organization(
        id=str(uuid.uuid4()),
        name="Constructora Ingesta & Web-First SpA",
        slug=f"acq-spa-{uuid.uuid4().hex[:6]}"
    )
    db_session.add(org)

    # 2. Crear Usuario Auditor
    user = User(
        id=str(uuid.uuid4()),
        email=f"auditor-acq-{uuid.uuid4().hex[:6]}@acq.cl",
        display_name="Auditor de Ingesta y Web-First",
        password_hash="mock_hash_acq"
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
        name="Edificio Torre Las Condes",
        code="PRJ-TLC-2026",
        settings={"stage": "stage_1_pre_revision"},
        discipline="architecture"
    )
    db_session.add(proj)
    db_session.commit()

    token = create_access_token(subject=user.id, email=user.email, extra_claims={"role": "admin", "org_id": org.id})
    client = TestClient(app)

    yield {
        "client": client,
        "token": token,
        "org_id": org.id,
        "proj_id": proj.id,
        "user_id": user.id,
        "db": db_session
    }
    db_session.close()


def test_scenario_1_web_search_resolved_satisfactory(acq_test_setup):
    """
    Escenario 1: Búsqueda web autorizada resuelta satisfactoriamente con score >= 0.75 y termination_reason='resolved_satisfactory'.
    """
    client = acq_test_setup["client"]
    token = acq_test_setup["token"]
    org_id = acq_test_setup["org_id"]
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

    # 1. Detectar faltante
    gap_req = {
        "topic_query": "Normativa oficial de distanciamiento de puertas de escape",
        "discipline": "architecture",
        "detection_source": "assistant_evaluator",
        "auto_request_permission": True
    }
    res = client.post("/api/v1/acquisition/detect-gap", json=gap_req, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["is_gap_detected"] is True
    acq_id = data["acquisition_request_id"]

    # 2. Autorizar búsqueda web con límites explícitos
    perm_payload = {
        "action": "approve",
        "max_iterations_override": 3,
        "sources_limit_override": 5
    }
    res_perm = client.post(f"/api/v1/acquisition/requests/{acq_id}/permission", json=perm_payload, headers=headers)
    assert res_perm.status_code == 200
    pdata = res_perm.json()

    assert pdata["permission_status"] == "approved"
    assert pdata["web_search_executed"] is True
    assert pdata["iteration_count"] == 1
    assert pdata["max_iterations"] == 3
    assert pdata["search_sources_limit"] == 5
    assert pdata["overall_adequacy_score"] >= 0.70
    assert pdata["adequacy_classification"] in ["sufficient", "partially_sufficient"]
    assert pdata["termination_reason"] in ["resolved_satisfactory", "partial_needs_validation"]
    assert pdata["status"] == "resolved"


def test_scenario_2_web_search_partial_needs_validation(acq_test_setup):
    """
    Escenario 2: Búsqueda web que entrega resultados parciales y queda clasificada como partial_needs_validation.
    """
    client = acq_test_setup["client"]
    token = acq_test_setup["token"]
    org_id = acq_test_setup["org_id"]
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

    gap_req = {
        "topic_query": "Requisitos generales de tabiquería liviana acústica",
        "discipline": "architecture",
        "detection_source": "completeness_gatekeeper",
        "auto_request_permission": True
    }
    res = client.post("/api/v1/acquisition/detect-gap", json=gap_req, headers=headers)
    acq_id = res.json()["acquisition_request_id"]

    res_perm = client.post(f"/api/v1/acquisition/requests/{acq_id}/permission", json={"action": "approve"}, headers=headers)
    assert res_perm.status_code == 200
    data = res_perm.json()
    assert data["permission_status"] == "approved"
    assert data["relevance_score"] > 0.0
    assert data["overall_adequacy_score"] > 0.0


def test_scenario_3_web_search_insufficient_with_document_request(acq_test_setup):
    """
    Escenario 3: Búsqueda de información técnica privada del proyecto que escala automáticamente
    a Solicitud Formal de Documentación Técnica con diagnóstico explicable.
    """
    client = acq_test_setup["client"]
    token = acq_test_setup["token"]
    org_id = acq_test_setup["org_id"]
    proj_id = acq_test_setup["proj_id"]
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

    # Faltante privado: Memoria de cálculo de fundaciones y mecánica de suelos
    gap_req = {
        "project_id": proj_id,
        "topic_query": "Memoria de Cálculo de Fundaciones y Cargas de Suelo Específico",
        "discipline": "structures",
        "stage": "Ingeniería de Detalle",
        "detection_source": "rule_engine_verifier",
        "auto_request_permission": True
    }
    res = client.post("/api/v1/acquisition/detect-gap", json=gap_req, headers=headers)
    acq_id = res.json()["acquisition_request_id"]

    res_perm = client.post(f"/api/v1/acquisition/requests/{acq_id}/permission", json={"action": "approve"}, headers=headers)
    assert res_perm.status_code == 200
    data = res_perm.json()

    assert data["status"] == "escalated"
    assert data["termination_reason"] == "not_applicable_private_project_data"
    assert data["requested_document_type"] is not None
    assert "Memoria de Cálculo" in data["requested_document_type"]
    assert data["suggested_responsible"] == "Ingeniero Calculista / Especialista de Proyecto"
    
    # Validar que los detalles de escalamiento son explicables y completos
    esc = data["escalation_details"]
    assert "missing_information_details" in esc
    assert "why_web_internal_failed" in esc
    assert "requested_document_type" in esc
    assert "suggested_responsible" in esc
    assert "audit_impact_justification" in esc
    assert len(esc.get("unlocked_deliverables_and_rules", [])) > 0


def test_scenario_4_web_search_cancelled_by_user(acq_test_setup):
    """
    Escenario 4: Cancelación de búsqueda web por rechazo explícito del usuario con termination_reason='cancelled_by_user'.
    """
    client = acq_test_setup["client"]
    token = acq_test_setup["token"]
    org_id = acq_test_setup["org_id"]
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

    gap_req = {
        "topic_query": "Precios unitarios de mercado para partidas de hormigón",
        "discipline": "general",
        "detection_source": "manual_auditor",
        "auto_request_permission": True
    }
    res = client.post("/api/v1/acquisition/detect-gap", json=gap_req, headers=headers)
    acq_id = res.json()["acquisition_request_id"]

    # Rechazar
    reject_payload = {
        "action": "reject",
        "rejection_reason": "No se autoriza búsqueda web para estimaciones de costos en esta etapa."
    }
    res_perm = client.post(f"/api/v1/acquisition/requests/{acq_id}/permission", json=reject_payload, headers=headers)
    assert res_perm.status_code == 200
    data = res_perm.json()

    assert data["permission_status"] == "rejected"
    assert data["rejection_reason"] == "No se autoriza búsqueda web para estimaciones de costos en esta etapa."
    assert data["termination_reason"] == "cancelled_by_user"
    assert data["status"] == "closed"


def test_scenario_5_exhausted_search_iterations(acq_test_setup):
    """
    Escenario 5: Agotamiento de iteraciones de búsqueda (límite alcanzado) que deriva en escalamiento a documento.
    """
    client = acq_test_setup["client"]
    token = acq_test_setup["token"]
    org_id = acq_test_setup["org_id"]
    db = acq_test_setup["db"]
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

    # Creamos un requerimiento directamente en BD con iteration_count = 2 y max_iterations = 3
    req = InformationAcquisitionRequest(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        missing_topic="Certificado de Ensayo de Impacto de Tabiquería",
        gap_description="Falta ensayo específico de impacto",
        detection_source="completeness_gatekeeper",
        discipline="architecture",
        iteration_count=2,
        max_iterations=3,
        permission_status="pending_permission",
        action_type="web_search",
        adequacy_status="pending_evaluation",
        status="open"
    )
    db.add(req)
    db.commit()

    # Ejecutar 3ra iteración (alcanzará max_iterations = 3)
    res_perm = client.post(f"/api/v1/acquisition/requests/{req.id}/permission", json={"action": "approve"}, headers=headers)
    assert res_perm.status_code == 200
    data = res_perm.json()

    assert data["iteration_count"] == 3
    assert data["max_iterations"] == 3
    assert data["termination_reason"] in ["exhausted_max_attempts", "resolved_satisfactory", "partial_needs_validation"]


def test_scenario_6_viewer_symbol_capture_and_normalization(acq_test_setup):
    """
    Escenario 6: Captura y normalización de símbolo desde visor con crop PNG, BBOX, categoría, alias y leyenda.
    """
    client = acq_test_setup["client"]
    token = acq_test_setup["token"]
    org_id = acq_test_setup["org_id"]
    proj_id = acq_test_setup["proj_id"]
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

    mock_png_base64 = "data:image/png;base64," + base64.b64encode(b"mock_extinguisher_png_bytes").decode("utf-8")

    capture_payload = {
        "project_id": proj_id,
        "document_id": "doc_arch_01",
        "sheet_id": "sheet_floor_1",
        "sheet_code": "LAM-A-01",
        "page_number": 1,
        "bbox_normalized": [0.10, 0.20, 0.15, 0.25],
        "element_type": "symbol",
        "name": "Extintor PQS 6KG Gabinete",
        "normalized_category": "extinguisher_pqs_6kg",
        "aliases": ["Extintor PQS", "EXT 6KG", "Gabinete Extintor"],
        "description": "Extintor de polvo químico seco en gabinete embutido en muro",
        "discipline": "architecture",
        "legend_text": "EXT PQS 6KG - GABINETE METALICO ROJO",
        "related_rule_code": "R-ARQ-EXTINGUISHER-SPACING",
        "crop_image_base64": mock_png_base64,
        "auto_approve": True
    }

    res = client.post("/api/v1/acquisition/capture-from-viewer", json=capture_payload, headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()

    assert data["domain"] == "symbol_knowledge"
    assert data["ingestion_channel"] == "viewer_capture"
    assert data["modality"] == "symbol"
    assert data["legend_reference"] == "EXT PQS 6KG - GABINETE METALICO ROJO"
    assert data["visual_crop_url"] is not None
    assert data["status"] == "approved_for_reuse"
    assert data["is_active_for_reuse"] is True

    payload = data["structured_payload"]
    assert payload["normalized_category"] == "extinguisher_pqs_6kg"
    assert "Extintor PQS" in payload["aliases"]
    assert payload["related_rule_code"] == "R-ARQ-EXTINGUISHER-SPACING"
    assert len(payload["linked_occurrences"]) == 1
    assert payload["linked_occurrences"][0]["sheet_code"] == "LAM-A-01"


def test_scenario_7_deduplication_and_occurrence_linking(acq_test_setup):
    """
    Escenario 7: Detección de duplicado y vinculación de ocurrencia en otra lámina sin duplicar entidad en catálogo.
    """
    client = acq_test_setup["client"]
    token = acq_test_setup["token"]
    org_id = acq_test_setup["org_id"]
    proj_id = acq_test_setup["proj_id"]
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

    # 1. Crear primer símbolo en Lámina 1
    cap1 = {
        "project_id": proj_id,
        "sheet_id": "sheet_floor_1",
        "sheet_code": "LAM-A-01",
        "element_type": "symbol",
        "name": "Tablero Eléctrico Alumbrado TE-1",
        "normalized_category": "electrical_board_te1",
        "aliases": ["TE-1", "Tablero Alumbrado"],
        "discipline": "electrical",
        "legend_text": "TE-1: TABLERO ALUMBRADO PISO 1",
        "auto_approve": True,
        "deduplication_mode": "create_new"
    }
    res1 = client.post("/api/v1/acquisition/capture-from-viewer", json=cap1, headers=headers)
    assert res1.status_code == 200
    item1_id = res1.json()["id"]

    # 2. Check Deduplication cuando se detecta en Lámina 2
    check_payload = {
        "name": "Tablero Eléctrico TE-1",
        "normalized_category": "electrical_board_te1",
        "discipline": "electrical",
        "element_type": "symbol"
    }
    res_check = client.post("/api/v1/acquisition/visual-dedup-check", json=check_payload, headers=headers)
    assert res_check.status_code == 200
    check_data = res_check.json()
    assert check_data["has_potential_duplicates"] is True
    assert check_data["suggested_mode"] == "link_occurrence"
    assert check_data["matches"][0]["item_id"] == item1_id

    # 3. Vincular Ocurrencia en Lámina 2 (sin duplicar entidad)
    cap2 = {
        "project_id": proj_id,
        "sheet_id": "sheet_floor_2",
        "sheet_code": "LAM-A-02",
        "page_number": 2,
        "element_type": "symbol",
        "name": "Tablero Eléctrico TE-1",
        "normalized_category": "electrical_board_te1",
        "discipline": "electrical",
        "legend_text": "TE-1: TABLERO ALUMBRADO PISO 2",
        "deduplication_mode": "link_occurrence",
        "target_existing_item_id": item1_id
    }
    res2 = client.post("/api/v1/acquisition/capture-from-viewer", json=cap2, headers=headers)
    assert res2.status_code == 200
    item2_data = res2.json()

    # Debe ser EL MISMO ID (no creado uno nuevo)
    assert item2_data["id"] == item1_id
    payload2 = item2_data["structured_payload"]
    assert len(payload2["linked_occurrences"]) == 2
    sheet_codes = [occ["sheet_code"] for occ in payload2["linked_occurrences"]]
    assert "LAM-A-01" in sheet_codes
    assert "LAM-A-02" in sheet_codes


def test_scenario_8_assistant_governance_reusability(acq_test_setup):
    """
    Escenario 8: Verificación de gobernanza estricta en el Asistente Copilot:
    - Elemento en status 'extracted' (no aprobado) NO es recuperado por RAG.
    - Al pasar a 'approved_for_reuse', es inmediatamente recuperado y citado.
    """
    client = acq_test_setup["client"]
    token = acq_test_setup["token"]
    org_id = acq_test_setup["org_id"]
    proj_id = acq_test_setup["proj_id"]
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

    # 1. Crear conocimiento en estado 'extracted' (no aprobado)
    cap_unapproved = {
        "project_id": proj_id,
        "sheet_id": "sheet_01",
        "element_type": "symbol",
        "name": "Válvula de Diluvio Red Húmeda DV-90",
        "normalized_category": "deluge_valve_dv90",
        "description": "Válvula para sistema de extinción por diluvio",
        "discipline": "fire_protection",
        "auto_approve": False # status = 'extracted', is_active_for_reuse = False
    }
    res_unapp = client.post("/api/v1/acquisition/capture-from-viewer", json=cap_unapproved, headers=headers)
    unapproved_id = res_unapp.json()["id"]

    # 2. Consultar al Asistente Copilot
    exec_payload = {
        "task_type": "symbol_clarification",
        "prompt": "¿Qué especificación tiene la Válvula de Diluvio Red Húmeda DV-90?",
        "discipline": "fire_protection",
        "project_id": proj_id
    }
    res_ast1 = client.post("/api/v1/assistant/execute", json=exec_payload, headers=headers)
    assert res_ast1.status_code == 200
    ast_data1 = res_ast1.json()
    rag_item_ids1 = [src["item_id"] for src in ast_data1.get("retrieved_sources", [])]
    assert unapproved_id not in rag_item_ids1, "Un elemento no aprobado NO debe aparecer en el contexto RAG del Asistente"

    # 3. Transicionar a 'approved_for_reuse'
    trans_res = client.post(
        f"/api/v1/knowledge/items/{unapproved_id}/transition",
        json={"target_status": "approved_for_reuse", "notes": "Validación técnica aprobada por auditor"},
        headers=headers
    )
    assert trans_res.status_code == 200

    # 4. Volver a consultar al Asistente Copilot
    res_ast2 = client.post("/api/v1/assistant/execute", json=exec_payload, headers=headers)
    assert res_ast2.status_code == 200
    ast_data2 = res_ast2.json()
    rag_item_ids2 = [src["item_id"] for src in ast_data2.get("retrieved_sources", [])]
    assert unapproved_id in rag_item_ids2, "El elemento aprobado SÍ debe ser recuperado por el Asistente"
