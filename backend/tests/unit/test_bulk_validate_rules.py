import pytest
import uuid
from app.db.models.intake_extractions import RuleDocument, RuleDocumentItem


@pytest.fixture
def sample_rule_document(db_session):
    doc = RuleDocument(
        id=f"doc-test-{uuid.uuid4().hex[:8]}",
        title="Especificación Técnica ASME B31.3 Piping",
        document_type="norma",
        discipline="Piping",
        authority="ASME",
        organization_id="org_test_bulk",
        status="active",
        items_count=7,
        rules_count=0,
        symbols_count=1,
    )
    db_session.add(doc)
    db_session.flush()

    # Rule item 1 (por_confirmar)
    r1 = RuleDocumentItem(
        id=f"item-rule-1-{uuid.uuid4().hex[:6]}",
        rule_document_id=doc.id,
        item_type="rule",
        title="Espesor Mínimo de Pared en Tuberías",
        code_or_number="ASME-B31.3-304.1.2",
        status="por_confirmar",
    )
    # Rule item 2 (draft)
    r2 = RuleDocumentItem(
        id=f"item-rule-2-{uuid.uuid4().hex[:6]}",
        rule_document_id=doc.id,
        item_type="regla",
        title="Prueba Hidrostática de Líneas de Proceso",
        code_or_number="ASME-B31.3-345.4",
        status="draft",
    )
    # Rule item 3 (active)
    r3 = RuleDocumentItem(
        id=f"item-rule-3-{uuid.uuid4().hex[:6]}",
        rule_document_id=doc.id,
        item_type="article",
        title="Inspección Radiográfica en Soldaduras Circunferenciales",
        code_or_number="ASME-B31.3-344.5",
        status="active",
    )
    # Rule item 4 (eliminado - no debe validarse)
    r4_deleted = RuleDocumentItem(
        id=f"item-rule-del-{uuid.uuid4().hex[:6]}",
        rule_document_id=doc.id,
        item_type="rule",
        title="Regla Obsoleta Eliminada",
        code_or_number="ASME-B31.3-OBS",
        status="eliminado",
    )
    # Symbol item (no debe validarse)
    s1 = RuleDocumentItem(
        id=f"item-sym-1-{uuid.uuid4().hex[:6]}",
        rule_document_id=doc.id,
        item_type="symbol",
        title="Válvula de Compuerta",
        code_or_number="PIP-VALVE-GATE",
        status="por_confirmar",
    )
    # Table item (no debe validarse)
    t1 = RuleDocumentItem(
        id=f"item-tbl-1-{uuid.uuid4().hex[:6]}",
        rule_document_id=doc.id,
        item_type="table",
        title="Tabla de Esfuerzos Admisibles",
        code_or_number="TBL-A-1",
        status="por_confirmar",
    )
    # Figure item (no debe validarse)
    f1 = RuleDocumentItem(
        id=f"item-fig-1-{uuid.uuid4().hex[:6]}",
        rule_document_id=doc.id,
        item_type="figura",
        title="Detalle Típico de Soportería",
        code_or_number="FIG-320",
        status="por_confirmar",
    )

    db_session.add_all([r1, r2, r3, r4_deleted, s1, t1, f1])
    db_session.commit()

    return {
        "doc": doc,
        "rules": [r1, r2, r3],
        "deleted_rule": r4_deleted,
        "symbol": s1,
        "table": t1,
        "figure": f1,
    }


def test_bulk_validate_all_rules_without_body(client, db_session, sample_rule_document):
    """
    Test 1: Validar masivamente sin body (o body vacío) valida todos los ítems de tipo regla,
    excluyendo símbolos, tablas, figuras y eliminados.
    """
    doc_id = sample_rule_document["doc"].id
    resp = client.post(f"/api/v1/rules/documents/{doc_id}/items/bulk-validate", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert data["document_id"] == doc_id
    assert data["validated_count"] == 3
    assert data["total_validated_rules"] == 3
    assert "3 regla(s)" in data["message"]

    # Verificar en la base de datos
    db_session.expire_all()
    for r in sample_rule_document["rules"]:
        item_db = db_session.query(RuleDocumentItem).filter(RuleDocumentItem.id == r.id).first()
        assert item_db.status == "validada"

    # Símbolos, tablas y figuras permanecen sin validar
    sym_db = db_session.query(RuleDocumentItem).filter(RuleDocumentItem.id == sample_rule_document["symbol"].id).first()
    assert sym_db.status == "por_confirmar"

    tbl_db = db_session.query(RuleDocumentItem).filter(RuleDocumentItem.id == sample_rule_document["table"].id).first()
    assert tbl_db.status == "por_confirmar"

    fig_db = db_session.query(RuleDocumentItem).filter(RuleDocumentItem.id == sample_rule_document["figure"].id).first()
    assert fig_db.status == "por_confirmar"

    # Eliminados permanecen eliminados
    del_db = db_session.query(RuleDocumentItem).filter(RuleDocumentItem.id == sample_rule_document["deleted_rule"].id).first()
    assert del_db.status == "eliminado"

    # Contador de reglas en el documento se actualizó
    doc_db = db_session.query(RuleDocument).filter(RuleDocument.id == doc_id).first()
    assert doc_db.rules_count == 3


def test_bulk_validate_specific_item_ids(client, db_session, sample_rule_document):
    """
    Test 2: Validar masivamente especificando item_ids solo valida los ítems indicados.
    """
    doc_id = sample_rule_document["doc"].id
    target_rule = sample_rule_document["rules"][0]
    other_rule = sample_rule_document["rules"][1]

    resp = client.post(
        f"/api/v1/rules/documents/{doc_id}/items/bulk-validate",
        json={"item_ids": [target_rule.id]}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["validated_count"] == 1

    db_session.expire_all()
    target_db = db_session.query(RuleDocumentItem).filter(RuleDocumentItem.id == target_rule.id).first()
    assert target_db.status == "validada"

    other_db = db_session.query(RuleDocumentItem).filter(RuleDocumentItem.id == other_rule.id).first()
    assert other_db.status == "draft"


def test_bulk_validate_rejects_extra_fields(client, sample_rule_document):
    """
    Test 3: Schema Pydantic con extra='forbid' rechaza campos no permitidos con HTTP 422.
    """
    doc_id = sample_rule_document["doc"].id
    resp = client.post(
        f"/api/v1/rules/documents/{doc_id}/items/bulk-validate",
        json={"item_ids": [], "unrecognized_param": "forbidden"}
    )
    assert resp.status_code == 422


def test_bulk_validate_document_not_found(client):
    """
    Test 4: Si el documento normativo no existe, retorna 404 Not Found.
    """
    resp = client.post("/api/v1/rules/documents/doc-non-existent-999/items/bulk-validate", json={})
    assert resp.status_code == 404
    assert "no encontrado" in resp.json()["detail"].lower()
