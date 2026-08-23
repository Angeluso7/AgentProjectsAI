import uuid
import pytest
from datetime import datetime
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import get_db, engine, Base
from app.db.models.core import Organization, User, Project
from app.db.models.normative_memory import NormativeCriterion
from app.db.models.decision_memory import RuleDefinition
from app.db.models.completeness import ProjectDeliverableRequirement
from app.db.models.observations import AuditObservation
from app.db.models.reporting import ProjectStageReportSnapshot
from app.db.models.knowledge_base import KnowledgeItem, KnowledgeChunk
from app.core.security import create_access_token

@pytest.fixture
def test_setup(db_session):

    # Crear Organización 1
    org1 = Organization(
        id=str(uuid.uuid4()),
        name="Constructora Andina Principal",
        slug=f"andina-main-{uuid.uuid4().hex[:6]}"
    )
    db_session.add(org1)

    # Crear Organización 2 (para aislamiento multi-tenant)
    org2 = Organization(
        id=str(uuid.uuid4()),
        name="Constructora Aislada Tenant 2",
        slug=f"tenant2-{uuid.uuid4().hex[:6]}"
    )
    db_session.add(org2)

    from app.db.models.core import OrganizationMembership

    user1 = User(
        id=str(uuid.uuid4()),
        email=f"auditor-{uuid.uuid4().hex[:6]}@andina.cl",
        display_name="Auditor Principal",
        password_hash="mock_hash_123"
    )
    db_session.add(user1)

    mem1 = OrganizationMembership(
        id=str(uuid.uuid4()),
        organization_id=org1.id,
        user_id=user1.id,
        role="admin"
    )
    db_session.add(mem1)

    user2 = User(
        id=str(uuid.uuid4()),
        email=f"auditor-ext-{uuid.uuid4().hex[:6]}@tenant2.cl",
        display_name="Auditor Tenant 2",
        password_hash="mock_hash_456"
    )
    db_session.add(user2)

    mem2 = OrganizationMembership(
        id=str(uuid.uuid4()),
        organization_id=org2.id,
        user_id=user2.id,
        role="admin"
    )
    db_session.add(mem2)

    # Crear Proyectos en Org 1
    proj_a = Project(
        id=str(uuid.uuid4()),
        organization_id=org1.id,
        name="Edificio Torre Norte",
        code="PRJ-TN-2026",
        settings={"stage": "Ingeniería Básica"},
        discipline="architecture"
    )
    db_session.add(proj_a)

    proj_b = Project(
        id=str(uuid.uuid4()),
        organization_id=org1.id,
        name="Centro Logístico Poniente",
        code="PRJ-CLP-2026",
        settings={"stage": "Ingeniería de Detalle"},
        discipline="structural"
    )
    db_session.add(proj_b)

    from app.db.models.normative_memory import NormativeDocument, NormativeClause

    # Obtener o crear Documento Normativo y Criterio
    norm_doc = db_session.query(NormativeDocument).filter(NormativeDocument.code == "OGUC-CHILE-2024").first()
    if not norm_doc:
        norm_doc = NormativeDocument(
            id=str(uuid.uuid4()),
            code="OGUC-CHILE-2024",
            title="Ordenanza General de Urbanismo y Construcciones",
            discipline="architecture",
            country="CL"
        )
        db_session.add(norm_doc)
        db_session.flush()

    clause = db_session.query(NormativeClause).filter(
        NormativeClause.document_id == norm_doc.id,
        NormativeClause.clause_number == "Art. 4.1.7"
    ).first()
    if not clause:
        clause = NormativeClause(
            id=str(uuid.uuid4()),
            document_id=norm_doc.id,
            clause_number="Art. 4.1.7",
            title="Ancho Mínimo de Puertas",
            content_text="Las puertas de recintos habitables deberán tener un ancho libre mínimo de 0.85 m."
        )
        db_session.add(clause)
        db_session.flush()

    crit = db_session.query(NormativeCriterion).filter(
        NormativeCriterion.criterion_code == "CRIT-OGUC-417-DOOR-MIN-WIDTH"
    ).first()
    if not crit:
        crit = NormativeCriterion(
            id=str(uuid.uuid4()),
            clause_id=clause.id,
            criterion_code="CRIT-OGUC-417-DOOR-MIN-WIDTH",
            name="Ancho Mínimo de Puertas Habitables",
            description="Las puertas de recintos habitables deberán tener un ancho libre mínimo de 0.85 m.",
            target_entity="door",
            property_name="width_clear",
            operator="gte",
            threshold_value={"min": 0.85, "unit": "m"},
            severity="high"
        )
        db_session.add(crit)

    # Obtener o crear Regla QA/QC
    rule = db_session.query(RuleDefinition).filter(RuleDefinition.code == "RULE_DOOR_COUNT_MATCH_V1").first()
    if not rule:
        rule = RuleDefinition(
            id=str(uuid.uuid4()),
            code="RULE_DOOR_COUNT_MATCH_V1",
            name="Conciliación de Conteo de Puertas (Dibujo vs Cuadro)",
            category="cross_reconciliation",
            discipline="architecture",
            severity_default="high",
            rule_logic_type="count_reconciliation",
            description="Compara el total de puertas en plano versus cuadro de vanos.",
            is_active=True
        )
        db_session.add(rule)

    # Crear Requisito de Entregable
    req = ProjectDeliverableRequirement(
        id=str(uuid.uuid4()),
        organization_id=org1.id,
        stage="Ingeniería Básica",
        discipline="architecture",
        deliverable_type="plano_general",
        title="Plano General de Arquitectura",
        is_mandatory=True,
        blocked_rule_codes=["RULE_DOOR_COUNT_MATCH_V1"]
    )
    db_session.add(req)

    # Crear Observación Resuelta
    obs = AuditObservation(
        id=str(uuid.uuid4()),
        organization_id=org1.id,
        project_id=proj_a.id,
        stage="Ingeniería Básica",
        code="OBS-PRJ-TN-2026-ARQ-001",
        item_type="technical_observation",
        title="Discrepancia en ancho de vanos de acceso",
        description="La puerta P-12 mide 0.80m incumpliendo los 0.85m exigidos por OGUC.",
        recommendation="Ajustar ancho a 0.85m en planta y cuadro de vanos.",
        discipline="architecture",
        severity="high",
        status="closed",
        resolution_notes="Plano rectificado a 0.85m en lámina A-02 y validado en auditoría.",
        issued_by=user1.email,
        closed_at=datetime.utcnow()
    )
    db_session.add(obs)

    # Crear Snapshot de Corte de Etapa
    snap = ProjectStageReportSnapshot(
        id=str(uuid.uuid4()),
        organization_id=org1.id,
        project_id=proj_a.id,
        stage="Ingeniería Básica",
        revision_number=1,
        title="Informe Consolidado Final - Ingeniería Básica (Rev 1)",
        global_stage_verdict="aprobable_con_observaciones",
        verdict_rationale="Completitud al 100% y 1 observación menor solventada.",
        issued_by=user1.email,
        manifest_hash="aabbccddeeff00112233445566778899aabbccddeeff00112233445566778899",
        completeness_summary={"percentage": 100.0, "gatekeeper_passed": True},
        audit_verdicts_summary={"cumple_count": 12, "no_cumple_count": 1},
        observations_summary={"total": 1, "closed_count": 1, "open_count": 0},
        delta_evolution_summary={"is_initial": True}
    )
    db_session.add(snap)

    db_session.commit()

    token1 = create_access_token(subject=user1.id, email=user1.email, extra_claims={"org_id": org1.id})
    token2 = create_access_token(subject=user2.id, email=user2.email, extra_claims={"org_id": org2.id})

    yield {
        "client": TestClient(app),
        "db": db_session,
        "org1": org1,
        "org2": org2,
        "user1": user1,
        "user2": user2,
        "proj_a": proj_a,
        "proj_b": proj_b,
        "token1": token1,
        "token2": token2
    }

def test_knowledge_base_operational_lifecycle_and_sync(test_setup):
    client = test_setup["client"]
    token1 = test_setup["token1"]
    token2 = test_setup["token2"]
    org1 = test_setup["org1"]
    proj_a = test_setup["proj_a"]
    proj_b = test_setup["proj_b"]

    headers_org1 = {"Authorization": f"Bearer {token1}", "X-Organization-Id": org1.id}
    headers_org2 = {"Authorization": f"Bearer {token2}", "X-Organization-Id": test_setup["org2"].id}

    # =========================================================================
    # 1. SINCRONIZACIÓN TRANSVERSAL DESDE TODOS LOS MÓDULOS OPERACIONALES
    # =========================================================================
    sync_resp = client.post("/api/v1/knowledge/sync/all", json={
        "project_id": proj_a.id,
        "auto_approve": False
    }, headers=headers_org1)

    assert sync_resp.status_code == 200
    sync_data = sync_resp.json()
    assert sync_data["success"] is True
    assert sync_data["total_items_created"] >= 4 # fuentes/normas + reglas + completitud + observaciones + snapshots
    assert sync_data["synced_counts"]["sources"] >= 1
    assert sync_data["synced_counts"]["rules"] >= 1
    assert sync_data["synced_counts"]["completeness"] >= 1
    assert sync_data["synced_counts"]["observations"] >= 1
    assert sync_data["synced_counts"]["snapshots"] >= 1

    # =========================================================================
    # 2. VERIFICACIÓN DE ITEMS Y CHUNKS GENERADOS
    # =========================================================================
    items_resp = client.get("/api/v1/knowledge/items", headers=headers_org1)
    assert items_resp.status_code == 200
    items_list = items_resp.json()
    assert len(items_list) >= 4

    # Verificar que por defecto quedan en status 'extracted' y is_active_for_reuse = False
    for item in items_list:
        assert item["status"] == "extracted"
        assert item["is_active_for_reuse"] is False

    # Obtener detalle de una regla sincronizada
    rule_item = next((i for i in items_list if "DOOR" in i["title"] or "Puertas" in i["title"]), None) or next((i for i in items_list if i["domain"] == "rule_knowledge"), None)
    assert rule_item is not None
    detail_resp = client.get(f"/api/v1/knowledge/items/{rule_item['id']}", headers=headers_org1)
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()
    assert len(detail_data["chunks"]) >= 1
    assert detail_data["chunks"][0]["token_count"] > 0
    assert "provenance_trace" in detail_data

    query_term = "RULE_DOOR_COUNT_MATCH_V1" if "DOOR" in rule_item["title"] else rule_item["title"]

    # =========================================================================
    # 3. GOBERNANZA: APROBACIÓN PARA REUTILIZACIÓN
    # =========================================================================
    # Antes de aprobar: la búsqueda RAG con active_only=True no debe retornar este ítem
    search_before = client.post("/api/v1/knowledge/search", json={
        "query": query_term,
        "active_only": True
    }, headers=headers_org1)
    assert search_before.status_code == 200
    assert search_before.json()["total_matches"] == 0

    # Aprobar el ítem para reutilización
    trans_resp = client.post(f"/api/v1/knowledge/items/{rule_item['id']}/transition", json={
        "target_status": "approved_for_reuse",
        "notes": "Aprobado por el Auditor Líder para recuperación por asistente",
        "reviewer": "auditor-lider@andina.cl"
    }, headers=headers_org1)
    assert trans_resp.status_code == 200
    updated_item = trans_resp.json()
    assert updated_item["status"] == "approved_for_reuse"
    assert updated_item["is_active_for_reuse"] is True

    # Después de aprobar: la búsqueda RAG ahora sí recupera el ítem
    search_after = client.post("/api/v1/knowledge/search", json={
        "query": query_term,
        "active_only": True
    }, headers=headers_org1)
    assert search_after.status_code == 200
    search_results = search_after.json()["results"]
    assert len(search_results) >= 1
    assert search_results[0]["item_id"] == rule_item["id"]
    assert search_results[0]["relevance_score"] > 0.3
    assert search_results[0]["is_active_for_reuse"] is True

    # =========================================================================
    # 4. GOBERNANZA: RECHAZO / OBSOLESCENCIA
    # =========================================================================
    rej_resp = client.post(f"/api/v1/knowledge/items/{rule_item['id']}/transition", json={
        "target_status": "rejected",
        "notes": "Criterio descartado por auditoría"
    }, headers=headers_org1)
    assert rej_resp.status_code == 200
    assert rej_resp.json()["status"] == "rejected"
    assert rej_resp.json()["is_active_for_reuse"] is False

    # Verificar que tras el rechazo, deja de ser elegible para RAG
    search_rej = client.post("/api/v1/knowledge/search", json={
        "query": query_term,
        "active_only": True
    }, headers=headers_org1)
    assert search_rej.json()["total_matches"] == 0

    # =========================================================================
    # 5. VERSIONAMIENTO Y SUCCESIÓN (SUPERSEDED)
    # =========================================================================
    # Re-aprobar item original
    client.post(f"/api/v1/knowledge/items/{rule_item['id']}/transition", json={
        "target_status": "approved_for_reuse"
    }, headers=headers_org1)

    # Crear versión 2
    version_resp = client.post(f"/api/v1/knowledge/items/{rule_item['id']}/version", json={
        "new_title": "Regla Actualizada: Conteo de Puertas v2",
        "new_content_text": "Regla QA/QC actualizada para validar no solo cuadro sino también anchos mínimos.",
        "change_notes": "Ampliación de cobertura a anchos libres.",
        "author": "auditor-experto@andina.cl"
    }, headers=headers_org1)
    assert version_resp.status_code == 200
    v2_item = version_resp.json()
    assert v2_item["version_number"] == 2
    assert v2_item["parent_item_id"] == rule_item["id"]
    assert v2_item["status"] == "reviewed"

    # Verificar que la versión 1 quedó en status 'superseded' e inactiva para reuse
    v1_detail = client.get(f"/api/v1/knowledge/items/{rule_item['id']}", headers=headers_org1).json()
    assert v1_detail["status"] == "superseded"
    assert v1_detail["is_active_for_reuse"] is False

    # =========================================================================
    # 6. AISLAMIENTO MULTI-TENANT & SCOPING POR PROYECTO
    # =========================================================================
    # Tenant 2 no puede ver las unidades de Tenant 1
    t2_items = client.get("/api/v1/knowledge/items", headers=headers_org2).json()
    assert len(t2_items) == 0

    # Estadísticas agregadas de la Base de Conocimiento
    stats_resp = client.get("/api/v1/knowledge/stats", headers=headers_org1)
    assert stats_resp.status_code == 200
    stats_data = stats_resp.json()
    assert stats_data["total_items"] >= 4
    assert "normative_knowledge" in stats_data["items_by_domain"]
    assert "rule_knowledge" in stats_data["items_by_domain"]
    assert "observation_rfi_knowledge" in stats_data["items_by_domain"]
    assert "project_knowledge" in stats_data["items_by_domain"]
