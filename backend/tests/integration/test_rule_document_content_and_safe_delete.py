import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import pytest
import uuid
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.models.core import Organization
from app.db.models.intake_extractions import RuleDocument, RuleDocumentItem
from app.db.models.decision_memory import (
    RuleDefinition, RuleApplicability, ReviewDiscipline, ReviewTopic
)
from app.services.review.taxonomy_service import TaxonomyService


@pytest.fixture
def setup_test_data(client, db_session):
    db = db_session
    TaxonomyService.seed_taxonomy_and_rules(db)

    # Ensure Org
    org = db.query(Organization).first()
    if not org:
        org = Organization(id=str(uuid.uuid4()), name="Test Org", slug="test-org")
        db.add(org)
        db.commit()

    disc = db.query(ReviewDiscipline).filter_by(code="PIPING").first()
    top = db.query(ReviewTopic).filter_by(code="PID_SYMBOLS").first()

    return client, db, org, disc, top


def test_document_content_empty_and_reprocess(setup_test_data):
    client, db, org, disc, top = setup_test_data

    # Create empty document
    doc = RuleDocument(
        id=str(uuid.uuid4()),
        organization_id=org.id,
        title="Norma Prueba Piping 2026",
        discipline="Piping",
        document_type="norma",
        version="1.0",
        status="active",
        items_count=0,
        rules_count=0,
        symbols_count=0,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(doc)
    db.commit()

    # 1. GET content on empty doc
    resp = client.get(f"/api/v1/rules/documents/{doc.id}/content")
    assert resp.status_code == 200
    data = resp.json()
    assert data["document_id"] == doc.id
    assert data["content_status"] == "not_extracted"
    assert data["explanation_code"] == "CONTENT_NOT_EXTRACTED"
    assert data["items"] == []
    assert data["summary"]["total_items"] == 0
    assert data["summary"]["rule_candidates"] == 0

    # 2. POST reprocess-content
    rep_resp = client.post(f"/api/v1/rules/documents/{doc.id}/reprocess-content")
    assert rep_resp.status_code == 200
    rep_data = rep_resp.json()
    assert rep_data["extracted_items_count"] > 0
    assert rep_data["rule_candidates_count"] > 0

    # 3. GET content again after reprocess
    resp2 = client.get(f"/api/v1/rules/documents/{doc.id}/content")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["content_status"] == "extracted"
    assert len(data2["items"]) > 0
    assert data2["summary"]["rule_candidates"] > 0
    # Every rule candidate must have can_promote == True
    rule_items = [it for it in data2["items"] if it["item_type"] == "rule_candidate"]
    assert len(rule_items) > 0
    for r in rule_items:
        assert r["can_promote"] is True
        assert r["promotion_status"] == "pending"


def test_deletion_impact_and_safe_delete_keep_baseline(setup_test_data):
    client, db, org, disc, top = setup_test_data

    # Create document with a candidate item
    doc = RuleDocument(
        id=str(uuid.uuid4()),
        organization_id=org.id,
        title="Norma ISA Valvulas 2026",
        discipline="Piping",
        document_type="norma",
        version="1.0",
        status="active",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(doc)

    item = RuleDocumentItem(
        id=str(uuid.uuid4()),
        rule_document_id=doc.id,
        item_type="rule_candidate",
        title="Valvula de Seguridad de Presion",
        code_or_number="ISA-PSV-01",
        description="Todo recipiente a presion debe disponer de valvula PSV tarada.",
        content_text="Seccion de alivio de presion",
        target_destination="rules_engine",
        status="validada",
        promotion_status="pending",
        created_at=datetime.utcnow()
    )
    db.add(item)
    db.commit()

    # 1. Promote candidate to Baseline QA/QC
    promote_payload = {
        "decision": "approve",
        "reviewer_rationale": "Norma obligatoria para recipientes a presion",
        "rule_code": "RULE-PSV-VALV-001",
        "title": "Verificacion de Valvula de Seguridad PSV",
        "severity": "critical",
        "discipline_ids": [disc.id],
        "topic_ids": [top.id],
        "execution_phase": 6,
        "enabled": True
    }
    prom_resp = client.post(
        f"/api/v1/rule-candidates/{item.id}/promote",
        json=promote_payload,
        headers={"x-user-role": "admin"}
    )
    assert prom_resp.status_code == 200
    rule_def_id = prom_resp.json()["rule_definition_id"]
    assert rule_def_id is not None

    # 2. Check deletion impact
    impact_resp = client.get(f"/api/v1/rules/documents/{doc.id}/deletion-impact")
    assert impact_resp.status_code == 200
    impact_data = impact_resp.json()
    assert impact_data["total_items_count"] == 1
    assert impact_data["promoted_rules_count"] == 1
    assert impact_data["active_baseline_rules_count"] == 1
    assert len(impact_data["affected_rules"]) == 1
    assert impact_data["affected_rules"][0]["rule_code"] == "RULE-PSV-VALV-001"
    assert impact_data["recommended_policy"] == "keep_baseline_source_removed"

    # 3. Test cancel policy
    del_cancel = client.delete(f"/api/v1/rules/documents/{doc.id}?policy=cancel")
    assert del_cancel.status_code == 200
    # Document still exists
    assert db.query(RuleDocument).filter_by(id=doc.id).first() is not None

    # 4. Safe delete with keep_baseline_source_removed
    del_resp = client.delete(f"/api/v1/rules/documents/{doc.id}?policy=keep_baseline_source_removed")
    assert del_resp.status_code == 200
    assert del_resp.json()["policy_applied"] == "keep_baseline_source_removed"

    # Document and items are deleted
    assert db.query(RuleDocument).filter_by(id=doc.id).first() is None
    assert db.query(RuleDocumentItem).filter_by(id=item.id).first() is None

    # Promoted Baseline RuleDefinition REMAINS INTACT and active, marked source_removed
    preserved_rule = db.query(RuleDefinition).filter_by(id=rule_def_id).first()
    assert preserved_rule is not None
    assert preserved_rule.enabled is True
    assert preserved_rule.source_status == "source_removed"
    assert preserved_rule.source_document_id is None


def test_deletion_retire_rules_policy(setup_test_data):
    client, db, org, disc, top = setup_test_data

    doc = RuleDocument(
        id=str(uuid.uuid4()),
        organization_id=org.id,
        title="Norma Retiro Test",
        discipline="Piping",
        document_type="norma",
        version="1.0",
        status="active",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(doc)

    item = RuleDocumentItem(
        id=str(uuid.uuid4()),
        rule_document_id=doc.id,
        item_type="rule_candidate",
        title="Regla a Retirar",
        code_or_number="RET-01",
        description="Regla que sera retirada al borrar documento",
        target_destination="rules_engine",
        status="validada",
        promotion_status="pending",
        created_at=datetime.utcnow()
    )
    db.add(item)
    db.commit()

    prom_resp = client.post(
        f"/api/v1/rule-candidates/{item.id}/promote",
        json={
            "decision": "approve",
            "reviewer_rationale": "Regla temporal para prueba de retiro",
            "rule_code": "RULE-RET-TEST-001",
            "title": "Regla Retiro Test",
            "severity": "medium",
            "discipline_ids": [disc.id],
            "topic_ids": [top.id],
            "execution_phase": 6,
            "enabled": True
        },
        headers={"x-user-role": "admin"}
    )
    assert prom_resp.status_code == 200
    rule_def_id = prom_resp.json()["rule_definition_id"]

    # Delete with retire_rules policy
    del_resp = client.delete(f"/api/v1/rules/documents/{doc.id}?policy=retire_rules")
    assert del_resp.status_code == 200

    # RuleDefinition is retired and disabled
    retired_rule = db.query(RuleDefinition).filter_by(id=rule_def_id).first()
    assert retired_rule is not None
    assert retired_rule.enabled is False
    assert retired_rule.is_active is False
    assert retired_rule.source_status == "retired"
