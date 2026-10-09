import pytest
import uuid
from app.db.models.decision_memory import ReviewDiscipline, ReviewTopic, RuleDefinition, RuleApplicability
from app.db.models.intake_extractions import RuleDocument, RuleDocumentItem
from app.services.review.taxonomy_service import TaxonomyService


@pytest.fixture
def taxonomy_seeded(db_session):
    """Asegura que la taxonomía completa esté sembrada en la base de datos."""
    TaxonomyService.seed_taxonomy_and_rules(db_session)
    return db_session


def test_deterministic_discipline_resolution_prefers_piping_over_general(client, db_session, taxonomy_seeded):
    """
    Test 1: Resolución determinística de disciplina.
    Dado que 'GENERAL' se sembró antes que 'PIPING' en la tabla de disciplinas,
    un documento con disciplina 'Piping' debe resolver determinísticamente a 'PIPING'
    y su tópico primario 'PID_SYMBOLS', NUNCA a 'GENERAL' o 'DOCUMENT_COMPLETENESS'.
    """
    doc = RuleDocument(
        id=f"doc-piping-{uuid.uuid4().hex[:8]}",
        title="Especificación ISA 5.1 2009",
        document_type="norma",
        discipline="Piping",
        authority="ISA",
        organization_id="org_test_disc",
        status="active",
        items_count=1,
        rules_count=1
    )
    db_session.add(doc)
    db_session.flush()

    item = RuleDocumentItem(
        id=f"item-isa-{uuid.uuid4().hex[:8]}",
        rule_document_id=doc.id,
        item_type="rule",
        title="Identificación de Instrumentos P&ID",
        code_or_number="ISA51-TAG-01",
        status="validada"
    )
    db_session.add(item)
    db_session.commit()

    # Promoción sin cuerpo (detección automática determinística)
    resp = client.post(f"/api/v1/rules/documents/{doc.id}/promote-to-baseline", json={})
    assert resp.status_code == 200, f"Error: {resp.status_code} - {resp.text}"
    data = resp.json()
    assert data["promoted_count"] == 1

    db_session.expire_all()
    rule_def = db_session.query(RuleDefinition).filter(RuleDefinition.code == "ISA51-TAG-01").first()
    assert rule_def is not None
    # Disciplina debe ser PIPING
    assert rule_def.discipline == "PIPING"
    assert rule_def.rule_scope == "specialty"

    # Aplicabilidad debe ser PIPING y PID_SYMBOLS (el primer tópico de piping)
    app = db_session.query(RuleApplicability).filter(RuleApplicability.rule_id == rule_def.id).first()
    assert app is not None
    disc = db_session.query(ReviewDiscipline).filter(ReviewDiscipline.id == app.discipline_id).first()
    assert disc.code == "PIPING"
    topic = db_session.query(ReviewTopic).filter(ReviewTopic.id == app.topic_id).first()
    assert topic.code == "PID_SYMBOLS"


def test_promote_with_explicit_discipline_and_topic(client, db_session, taxonomy_seeded):
    """
    Test 2: Promoción con disciplina y tópico explícitos pasados en el body.
    """
    doc = RuleDocument(
        id=f"doc-elec-{uuid.uuid4().hex[:8]}",
        title="Norma NCh 4 Electricidad",
        document_type="norma",
        discipline="General", # documento dice general, pero el usuario especifica alcance
        authority="SEC",
        organization_id="org_test_disc",
        status="active",
        items_count=1,
        rules_count=1
    )
    db_session.add(doc)
    db_session.flush()

    item = RuleDocumentItem(
        id=f"item-nch4-{uuid.uuid4().hex[:8]}",
        rule_document_id=doc.id,
        item_type="rule",
        title="Puesta a Tierra de Subestaciones",
        code_or_number="NCH4-TIERRA-01",
        status="validada"
    )
    db_session.add(item)
    db_session.commit()

    resp = client.post(
        f"/api/v1/rules/documents/{doc.id}/promote-to-baseline",
        json={"discipline_code": "PIPING", "topic_code": "PIPING_VALVES"}
    )
    assert resp.status_code == 200, f"Error: {resp.status_code} - {resp.text}"

    db_session.expire_all()
    rule_def = db_session.query(RuleDefinition).filter(RuleDefinition.code == "NCH4-TIERRA-01").first()
    assert rule_def is not None
    assert rule_def.discipline == "PIPING"

    app = db_session.query(RuleApplicability).filter(RuleApplicability.rule_id == rule_def.id).first()
    assert app is not None
    disc = db_session.query(ReviewDiscipline).filter(ReviewDiscipline.id == app.discipline_id).first()
    assert disc.code == "PIPING"
    topic = db_session.query(ReviewTopic).filter(ReviewTopic.id == app.topic_id).first()
    assert topic.code == "PIPING_VALVES"


def test_resync_rule_document_applicability_retargets_without_duplication(client, db_session, taxonomy_seeded):
    """
    Test 3: Reparación / Re-sincronización de aplicabilidad.
    Verifica que al ejecutar resync-applicability sobre un documento,
    todas sus reglas se actualizan a la nueva disciplina y tópico sin duplicar filas en RuleApplicability.
    """
    doc = RuleDocument(
        id=f"doc-resync-{uuid.uuid4().hex[:8]}",
        title="Documento Mal Etiquetado Históricamente",
        document_type="norma",
        discipline="General",
        authority="SEC",
        organization_id="org_test_disc",
        status="promovido_baseline",
        items_count=2,
        rules_count=2
    )
    db_session.add(doc)
    db_session.flush()

    # Crear 2 reglas inicialmente apuntando a GENERAL / DOCUMENT_COMPLETENESS
    gen_disc = db_session.query(ReviewDiscipline).filter(ReviewDiscipline.code == "GENERAL").first()
    gen_topic = db_session.query(ReviewTopic).filter(ReviewTopic.code == "DOCUMENT_COMPLETENESS").first()

    r1 = RuleDefinition(
        code=f"RULE-MISTAGGED-01-{uuid.uuid4().hex[:4]}",
        name="Regla 1 con aplicabilidad errónea",
        description="Descripción de regla 1",
        category="normative_compliance",
        discipline="GENERAL",
        source_document_id=doc.id,
        severity_default="medium",
        is_active=True,
        enabled=True
    )
    r2 = RuleDefinition(
        code=f"RULE-MISTAGGED-02-{uuid.uuid4().hex[:4]}",
        name="Regla 2 con aplicabilidad errónea",
        description="Descripción de regla 2",
        category="normative_compliance",
        discipline="GENERAL",
        source_document_id=doc.id,
        severity_default="medium",
        is_active=True,
        enabled=True
    )
    db_session.add_all([r1, r2])
    db_session.flush()

    app1 = RuleApplicability(
        rule_id=r1.id,
        discipline_id=gen_disc.id,
        topic_id=gen_topic.id,
        role="primary",
        approval_status="approved"
    )
    app2 = RuleApplicability(
        rule_id=r2.id,
        discipline_id=gen_disc.id,
        topic_id=gen_topic.id,
        role="primary",
        approval_status="approved"
    )
    db_session.add_all([app1, app2])
    db_session.commit()

    # Re-sincronizar hacia PIPING + PID_SYMBOLS
    resp = client.post(
        f"/api/v1/rules/documents/{doc.id}/resync-applicability",
        json={"discipline_code": "PIPING", "topic_code": "PID_SYMBOLS"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["updated_rules_count"] == 2
    assert data["discipline_code"] == "PIPING"
    assert data["topic_code"] == "PID_SYMBOLS"

    # Verificar en la base de datos
    db_session.expire_all()
    piping_disc = db_session.query(ReviewDiscipline).filter(ReviewDiscipline.code == "PIPING").first()
    piping_topic = db_session.query(ReviewTopic).filter(ReviewTopic.code == "PID_SYMBOLS").first()

    for r in [r1, r2]:
        r_db = db_session.query(RuleDefinition).filter(RuleDefinition.id == r.id).first()
        assert r_db.discipline == "PIPING"
        assert r_db.rule_scope == "specialty"

        # Debe tener exactamente 1 aplicabilidad primaria
        apps = db_session.query(RuleApplicability).filter(RuleApplicability.rule_id == r.id).all()
        assert len(apps) == 1
        assert apps[0].discipline_id == piping_disc.id
        assert apps[0].topic_id == piping_topic.id
        assert apps[0].role == "primary"
        assert apps[0].approval_status == "approved"


def test_resync_applicability_validations(client, db_session, taxonomy_seeded):
    """
    Test 4: Validaciones de resync-applicability (disciplina inexistente, extra fields).
    """
    doc = RuleDocument(
        id=f"doc-val-{uuid.uuid4().hex[:8]}",
        title="Documento de Prueba",
        organization_id="org_test_disc",
        discipline="Piping"
    )
    db_session.add(doc)
    db_session.commit()

    # Disciplina no válida
    resp = client.post(
        f"/api/v1/rules/documents/{doc.id}/resync-applicability",
        json={"discipline_code": "INVENTADA_999", "topic_code": "PID_SYMBOLS"}
    )
    assert resp.status_code == 400
    assert "no encontrada" in resp.json()["detail"].lower()

    # Extra fields forbidden
    resp_extra = client.post(
        f"/api/v1/rules/documents/{doc.id}/resync-applicability",
        json={"discipline_code": "PIPING", "topic_code": "PID_SYMBOLS", "malicious_flag": True}
    )
    assert resp_extra.status_code == 422
