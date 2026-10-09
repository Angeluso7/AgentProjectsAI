import pytest
import uuid
from app.db.models.core import Project
from app.db.models.document_memory import Document, DocumentSheet
from app.db.models.decision_memory import RuleDefinition, RuleExecution, RuleFinding
from app.services.rules.engine import RuleEngine, RuleRegistry


def test_patch_rule_status_synchronizes_flags(client, db_session):
    """
    Test 1: PATCH /api/v1/rules/{rule_code} sincroniza enabled e is_active.
    """
    rule_code = "SYM-UNKNOWN-001"
    RuleRegistry.seed_database_definitions(db_session)
    rule = db_session.query(RuleDefinition).filter(RuleDefinition.code == rule_code).first()
    assert rule is not None

    # Desactivar la regla
    resp = client.patch(f"/api/v1/rules/{rule_code}", json={"enabled": False})
    assert resp.status_code == 200
    data = resp.json()
    assert data["enabled"] is False
    assert data["is_active"] is False

    # Verificar en la BD
    db_session.expire_all()
    rule_db = db_session.query(RuleDefinition).filter(RuleDefinition.code == rule_code).first()
    assert rule_db.enabled is False
    assert rule_db.is_active is False

    # Reactivar la regla
    resp_re = client.patch(f"/api/v1/rules/{rule_code}", json={"enabled": True})
    assert resp_re.status_code == 200
    data_re = resp_re.json()
    assert data_re["enabled"] is True
    assert data_re["is_active"] is True

    db_session.expire_all()
    rule_db = db_session.query(RuleDefinition).filter(RuleDefinition.code == rule_code).first()
    assert rule_db.enabled is True
    assert rule_db.is_active is True


def test_deactivated_rule_hidden_from_list_and_execution(client, db_session):
    """
    Test 2: Regla desactivada no aparece en GET /api/v1/rules ni corre en evaluate_sheet.
    """
    rule_code = "SYM-TAG-MISSING-001"
    RuleRegistry.seed_database_definitions(db_session)

    # Desactivar
    resp = client.patch(f"/api/v1/rules/{rule_code}", json={"enabled": False})
    assert resp.status_code == 200

    # 1. No debe aparecer en GET /api/v1/rules
    resp_list = client.get("/api/v1/rules")
    assert resp_list.status_code == 200
    codes = [r["code"] for r in resp_list.json()]
    assert rule_code not in codes

    # 2. No debe evaluarse en evaluate_sheet
    proj = Project(id=str(uuid.uuid4()), name="Test Project", code="PRJ-TEST-01")
    db_session.add(proj)
    doc = Document(id=str(uuid.uuid4()), project_id=proj.id, filename="test_piping.pdf")
    db_session.add(doc)
    sheet = DocumentSheet(id=str(uuid.uuid4()), document_id=doc.id, sheet_number=1)
    db_session.add(sheet)
    db_session.commit()

    try:
        engine = RuleEngine(db_session)
        findings = engine.evaluate_sheet(sheet.id)
        finding_codes = [f.rule_code for f in findings]
        assert rule_code not in finding_codes
    finally:
        client.patch(f"/api/v1/rules/{rule_code}", json={"enabled": True})


def test_deactivated_rule_survives_seed_defaults(client, db_session):
    """
    Test 3: Una regla desactivada NO vuelve a quedar enabled=true tras seed-defaults o GET /rules.
    """
    rule_code = "SYM-LEGEND-CONSISTENCY-001"
    RuleRegistry.seed_database_definitions(db_session)

    # Desactivar
    client.patch(f"/api/v1/rules/{rule_code}", json={"enabled": False})

    # Disparar seed-defaults
    resp_seed = client.post("/api/v1/rules/seed-defaults")
    assert resp_seed.status_code == 200

    # Disparar GET /rules (que también llama seed_database_definitions)
    client.get("/api/v1/rules")

    # Verificar que continúa desactivada
    db_session.expire_all()
    rule_db = db_session.query(RuleDefinition).filter(RuleDefinition.code == rule_code).first()
    assert rule_db is not None
    assert rule_db.enabled is False
    assert rule_db.is_active is False

    # Restaurar para no afectar otros tests
    client.patch(f"/api/v1/rules/{rule_code}", json={"enabled": True})


def test_delete_rule_physical_when_no_executions(client, db_session):
    """
    Test 4A: DELETE /rules/{rule_code} elimina físicamente si no hay RuleExecution ni RuleFinding.
    """
    temp_code = f"RULE_TEMP_TEST_{uuid.uuid4().hex[:6].upper()}"
    rule = RuleDefinition(
        id=str(uuid.uuid4()),
        code=temp_code,
        name="Regla Temporal de Prueba",
        category="general",
        discipline="piping",
        severity_default="low",
        description="Regla sin ejecuciones para test de eliminación física",
        rule_logic_type="test",
        version="1.0",
        enabled=True,
        is_active=True
    )
    db_session.add(rule)
    db_session.commit()

    # Ejecutar DELETE
    resp = client.delete(f"/api/v1/rules/{temp_code}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["deleted"] is True
    assert data["code"] == temp_code

    # Verificar que ya no existe en la base de datos
    db_session.expire_all()
    deleted = db_session.query(RuleDefinition).filter(RuleDefinition.code == temp_code).first()
    assert deleted is None


def test_delete_rule_409_and_deactivates_when_executions_exist(client, db_session):
    """
    Test 4B: DELETE /rules/{rule_code} responde 409 y desactiva permanentemente si existen ejecuciones asociadas.
    """
    test_code = f"RULE_HISTORICAL_{uuid.uuid4().hex[:6].upper()}"
    rule = RuleDefinition(
        id=str(uuid.uuid4()),
        code=test_code,
        name="Regla Histórica con Ejecuciones",
        category="cross_reconciliation",
        discipline="piping",
        severity_default="medium",
        description="Regla con histórico que no debe ser eliminada físicamente",
        rule_logic_type="count_reconciliation",
        version="1.0",
        enabled=True,
        is_active=True
    )
    db_session.add(rule)
    db_session.commit()

    # Crear una RuleExecution asociada
    execution = RuleExecution(
        id=str(uuid.uuid4()),
        document_id=str(uuid.uuid4()),
        rule_id=rule.id,
        rule_version="1.0",
        execution_status="passed",
        confidence=1.0
    )
    db_session.add(execution)
    db_session.commit()

    # Intentar DELETE -> debe responder 409 Conflict
    resp = client.delete(f"/api/v1/rules/{test_code}")
    assert resp.status_code == 409
    assert "ejecuciones o hallazgos históricos asociados" in resp.json()["detail"]

    # Verificar que la regla NO fue eliminada pero sí desactivada (ambos flags en False)
    db_session.expire_all()
    persisted = db_session.query(RuleDefinition).filter(RuleDefinition.code == test_code).first()
    assert persisted is not None
    assert persisted.enabled is False
    assert persisted.is_active is False


def test_demo_rules_deactivated_by_migration(db_session):
    """
    Test 5: Verificar que las 6 reglas demo están desactivadas y las 5 de piping activas.
    """
    demo_codes = [
        "RULE_DOOR_COUNT_MATCH_V1",
        "RULE_WINDOW_COUNT_MATCH_V1",
        "RULE_TITLE_BLOCK_REQUIRED_FIELDS_V1",
        "RULE_TITLE_BLOCK_SCALE_VALID_V1",
        "RULE_REQUIRED_TABLES_BY_DOCUMENT_TYPE_V1",
        "RULE_NORMATIVE_MIN_WIDTH_DOOR_V1"
    ]
    RuleRegistry.seed_database_definitions(db_session)

    # Las 6 reglas demo no deben estar en default_instances de RuleRegistry
    registered_codes = [r.code for r in RuleRegistry.get_rules()]
    for demo_code in demo_codes:
        assert demo_code not in registered_codes

    # Y las 5 reglas de piping canónicas deben estar en RuleRegistry
    piping_codes = [
        "SYM-UNKNOWN-001",
        "SYM-AMBIGUOUS-001",
        "SYM-LEGEND-CONSISTENCY-001",
        "SYM-TAG-MISSING-001",
        "GEN-DOC-001"
    ]
    for p_code in piping_codes:
        assert p_code in registered_codes
