import pytest
from datetime import datetime
from fastapi import status
from sqlalchemy.orm import Session

from app.db.models.decision_memory import (
    RuleDefinition, RuleApplicability, RuleReviewDecision,
    ReviewDiscipline, ReviewTopic
)
from app.db.models.intake_extractions import (
    RuleDocument, RuleDocumentItem
)
from app.schemas.rule_candidates import PromoteRuleCandidateRequest
from app.services.rules.promotion_service import RulePromotionService
from app.services.review.taxonomy_service import TaxonomyService


@pytest.fixture
def sample_normative_setup(db_session: Session):
    """Crea un documento normativo con candidatos para pruebas de promoción."""
    # Asegurar taxonomía
    TaxonomyService.seed_taxonomy_and_rules(db_session)
    
    doc = RuleDocument(
        id="doc-norm-test-01",
        title="Norma NCh 433 Diseño Sísmico",
        document_type="norma",
        discipline="Estructuras",
        authority="INN",
        organization_id="org_test_promotion",
        status="incorporado"
    )
    db_session.add(doc)
    db_session.flush()

    item_rule = RuleDocumentItem(
        id="item-cand-rule-01",
        rule_document_id=doc.id,
        item_type="rule",
        title="Separación Mínima entre Edificios",
        code_or_number="NCH433-ART-5",
        content_text="La separación entre edificios adyacentes no podrá ser inferior a s = 0.002 * h.",
        description="Separación entre juntas sísmicas según altura de edificación.",
        metadata_payload={"page_number": 12, "bbox": {"x": 50, "y": 100, "w": 300, "h": 150}},
        status="validada",
        promotion_status="pending"
    )
    
    item_symbol = RuleDocumentItem(
        id="item-cand-sym-01",
        rule_document_id=doc.id,
        item_type="symbol",
        title="Símbolo Válvula de Alivio Sísmico",
        code_or_number="SYM-VALV-01",
        content_text="Símbolo gráfico de válvula de seguridad sísmica",
        metadata_payload={"page_number": 15},
        status="validada",
        promotion_status="pending"
    )

    db_session.add_all([item_rule, item_symbol])
    db_session.commit()

    return {
        "doc": doc,
        "item_rule": item_rule,
        "item_symbol": item_symbol
    }


def test_validate_content_does_not_promote(client, sample_normative_setup, db_session):
    """1. Validar contenido solo cambia estado de candidato/fuente, no equivale a promover."""
    headers = {"x-organization-id": "org_test_promotion", "x-user-id": "auditor_1", "x-user-role": "auditor"}
    item_id = sample_normative_setup["item_rule"].id
    doc_id = sample_normative_setup["doc"].id

    res = client.post(
        f"/api/v1/rules/documents/{doc_id}/confirm-content",
        headers=headers,
        json={"confirmed_item_ids": [item_id]}
    )
    assert res.status_code == status.HTTP_200_OK

    # Verificar que NO se creó RuleDefinition en DB
    cand = db_session.query(RuleDocumentItem).filter(RuleDocumentItem.id == item_id).first()
    assert cand.status in ["validada", "confirmada"]
    assert cand.promoted_rule_definition_id is None
    
    rule_defs = db_session.query(RuleDefinition).filter(RuleDefinition.source_candidate_id == item_id).all()
    assert len(rule_defs) == 0


def test_individual_promotion_creates_rule_lineage(client, sample_normative_setup, db_session):
    """2. Promoción individual crea RuleDefinition con linaje fuente inmutable derivado de DB."""
    headers = {"x-organization-id": "org_test_promotion", "x-user-id": "lead_1", "x-user-role": "audit_lead"}
    item_id = sample_normative_setup["item_rule"].id

    payload = {
        "decision": "approve",
        "action": "promote_and_activate",
        "reviewer_rationale": "Regla sísmica mandatoria para revisión de planos.",
        "rule_code": "EST-NCH433-SEP-01",
        "title": "Separación Mínima entre Edificios",
        "severity": "high",
        "discipline_ids": ["STRUCTURES"],
        "topic_ids": ["REGULATORY_COMPLIANCE"],
        "execution_phase": 6,
        "enabled": True
    }

    res = client.post(f"/api/v1/rule-candidates/{item_id}/promote", headers=headers, json=payload)
    assert res.status_code == status.HTTP_200_OK, res.text
    data = res.json()
    assert data["rule_code"] == "EST-NCH433-SEP-01"
    assert data["baseline_status"] == "active"
    assert data["candidate_status"] == "promoted"
    assert data["already_promoted"] is False

    # Verificar en DB el linaje inmutable derivado
    rule_def = db_session.query(RuleDefinition).filter(RuleDefinition.code == "EST-NCH433-SEP-01").first()
    assert rule_def is not None
    assert rule_def.source_candidate_id == item_id
    assert rule_def.source_document_id == sample_normative_setup["doc"].id
    assert rule_def.source_page == 12
    assert rule_def.source_bbox == {"x": 50, "y": 100, "w": 300, "h": 150}
    assert "0.002 * h" in rule_def.source_excerpt
    assert rule_def.source_hash is not None


def test_rule_applicability_approved_and_baseline_visible(client, sample_normative_setup, db_session):
    """3. RuleApplicability aprobada creada y baseline visible en el catálogo."""
    headers = {"x-organization-id": "org_test_promotion", "x-user-id": "admin_1", "x-user-role": "admin"}
    item_id = sample_normative_setup["item_rule"].id

    payload = {
        "decision": "approve",
        "action": "promote_and_activate",
        "reviewer_rationale": "Aprobación baseline por admin.",
        "rule_code": "EST-NCH433-APPL-01",
        "title": "Verificación de Juntas Sísmicas",
        "severity": "critical",
        "discipline_ids": ["STRUCTURES"],
        "topic_ids": ["COORDINATION"],
        "execution_phase": 6,
        "enabled": True
    }

    res = client.post(f"/api/v1/rule-candidates/{item_id}/promote", headers=headers, json=payload)
    assert res.status_code == status.HTTP_200_OK
    rule_def_id = res.json()["rule_definition_id"]

    # Verificar aplicabilidades en DB
    appls = db_session.query(RuleApplicability).filter(RuleApplicability.rule_id == rule_def_id).all()
    assert len(appls) >= 1
    assert any(a.approval_status == "approved" for a in appls)

    # Verificar que aparece en endpoint público de catálogo de reglas
    cat_res = client.get("/api/v1/rules", headers=headers)
    assert cat_res.status_code == status.HTTP_200_OK
    all_rules = cat_res.json()
    assert any(r["code"] == "EST-NCH433-APPL-01" for r in all_rules)


def test_one_click_review_includes_promoted_rule(client, sample_normative_setup, db_session):
    """4. One-Click Review (TaxonomyService.get_applicable_rules) incluye la regla promovida."""
    headers = {"x-organization-id": "org_test_promotion", "x-user-id": "admin_1", "x-user-role": "admin"}
    item_id = sample_normative_setup["item_rule"].id

    payload = {
        "decision": "approve",
        "action": "promote_and_activate",
        "reviewer_rationale": "Activar para revisión automática.",
        "rule_code": "EST-NCH433-OCR-01",
        "title": "Criterio de Resistencia Sísmica",
        "severity": "high",
        "discipline_ids": ["STRUCTURES"],
        "topic_ids": ["REGULATORY_COMPLIANCE"],
        "execution_phase": 6,
        "enabled": True
    }

    res = client.post(f"/api/v1/rule-candidates/{item_id}/promote", headers=headers, json=payload)
    assert res.status_code == status.HTTP_200_OK

    # Consultar reglas aplicables vía TaxonomyService
    applicable_rules = TaxonomyService.get_applicable_rules(
        db=db_session,
        discipline_code="STRUCTURES",
        topic_code="REGULATORY_COMPLIANCE"
    )
    rule_codes = [r["code"] for r in applicable_rules]
    assert "EST-NCH433-OCR-01" in rule_codes


def test_idempotent_promotion(client, sample_normative_setup, db_session):
    """5. Idempotencia: Promover una regla candidata ya promovida no duplica y retorna existente."""
    headers = {"x-organization-id": "org_test_promotion", "x-user-id": "admin_1", "x-user-role": "admin"}
    item_id = sample_normative_setup["item_rule"].id

    payload = {
        "decision": "approve",
        "action": "promote_and_activate",
        "reviewer_rationale": "Primera promoción.",
        "rule_code": "EST-IDEM-001",
        "title": "Regla Idempotente",
        "severity": "medium",
        "discipline_ids": ["STRUCTURES"],
        "topic_ids": ["DOCUMENT_COMPLETENESS"],
        "execution_phase": 6,
        "enabled": True
    }

    res1 = client.post(f"/api/v1/rule-candidates/{item_id}/promote", headers=headers, json=payload)
    assert res1.status_code == status.HTTP_200_OK
    assert res1.json()["already_promoted"] is False

    # Segunda llamada: debe detectar que ya está promovida
    res2 = client.post(f"/api/v1/rule-candidates/{item_id}/promote", headers=headers, json=payload)
    assert res2.status_code == status.HTTP_200_OK
    assert res2.json()["already_promoted"] is True
    assert res2.json()["rule_code"] == "EST-IDEM-001"

    # Verificar que solo hay 1 definición en base de datos
    defs_count = db_session.query(RuleDefinition).filter(RuleDefinition.code == "EST-IDEM-001").count()
    assert defs_count == 1


def test_tenant_isolation(client, sample_normative_setup):
    """6. Aislamiento por Tenant: no se puede promover candidato de otra organización."""
    foreign_headers = {
        "x-organization-id": "org_intruder_999",
        "x-user-id": "intruder_user",
        "x-user-role": "admin"
    }
    item_id = sample_normative_setup["item_rule"].id

    payload = {
        "decision": "approve",
        "action": "promote_and_activate",
        "reviewer_rationale": "Intento de acceso cruzado.",
        "rule_code": "EST-ILLEGAL-01",
        "title": "Violación Tenant",
        "severity": "high",
        "discipline_ids": ["STRUCTURES"],
        "topic_ids": ["DOCUMENT_COMPLETENESS"],
        "execution_phase": 6
    }

    res = client.post(f"/api/v1/rule-candidates/{item_id}/promote", headers=foreign_headers, json=payload)
    # Debe ser 403 Forbidden o 404 Not Found
    assert res.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND]


def test_rbac_by_role(client, sample_normative_setup, db_session):
    """7. RBAC por Rol: viewer rechazado; auditor promueve a revisión; admin/audit_lead activa."""
    item_id = sample_normative_setup["item_rule"].id

    payload = {
        "decision": "approve",
        "action": "promote_and_activate",
        "reviewer_rationale": "Evaluación RBAC.",
        "rule_code": "EST-RBAC-01",
        "title": "Regla Permisos",
        "severity": "medium",
        "discipline_ids": ["STRUCTURES"],
        "topic_ids": ["DOCUMENT_COMPLETENESS"],
        "execution_phase": 6
    }

    # A) Viewer: 403 Forbidden
    viewer_headers = {"x-organization-id": "org_test_promotion", "x-user-id": "v_1", "x-user-role": "viewer"}
    res_v = client.post(f"/api/v1/rule-candidates/{item_id}/promote", headers=viewer_headers, json=payload)
    assert res_v.status_code == status.HTTP_403_FORBIDDEN

    # B) Auditor: promueve como borrador / proposed
    auditor_headers = {"x-organization-id": "org_test_promotion", "x-user-id": "aud_1", "x-user-role": "auditor"}
    payload_aud = dict(payload, action="promote_for_review")
    res_a = client.post(f"/api/v1/rule-candidates/{item_id}/promote", headers=auditor_headers, json=payload_aud)
    assert res_a.status_code == status.HTTP_200_OK
    assert res_a.json()["baseline_status"] == "pending_approval"
    assert res_a.json()["candidate_status"] == "promoted_draft"


def test_reject_candidate_does_not_create_rule(client, sample_normative_setup, db_session):
    """8. Rechazo de regla candidata: actualiza estado y audita HITL sin crear RuleDefinition."""
    headers = {"x-organization-id": "org_test_promotion", "x-user-id": "aud_lead", "x-user-role": "audit_lead"}
    item_id = sample_normative_setup["item_rule"].id

    payload = {
        "decision": "reject",
        "action": "promote_for_review",
        "reviewer_rationale": "Criterio no aplicable al alcance de diseño.",
        "rule_code": "EST-REJECTED-01",
        "title": "Regla Rechazada",
        "severity": "low",
        "discipline_ids": ["STRUCTURES"],
        "topic_ids": ["DOCUMENT_COMPLETENESS"],
        "execution_phase": 6
    }

    res = client.post(f"/api/v1/rule-candidates/{item_id}/promote", headers=headers, json=payload)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["candidate_status"] == "rejected"
    assert data["rule_definition_id"] is None

    # Verificar que el candidato en DB quedó rejected y sin RuleDefinition
    cand = db_session.query(RuleDocumentItem).filter(RuleDocumentItem.id == item_id).first()
    assert cand.promotion_status == "rejected"
    assert cand.promoted_rule_definition_id is None

    # Verificar que se registró la decisión HITL inmutable
    decision = db_session.query(RuleReviewDecision).filter(RuleReviewDecision.candidate_id == item_id).first()
    assert decision is not None
    assert decision.decision == "reject"
    assert "no aplicable" in decision.reviewer_rationale


def test_symbol_cannot_be_promoted_as_rule(client, sample_normative_setup):
    """9. Símbolo (SymbolTemplate / StructuredSymbol) no puede ser promovido a RuleDefinition."""
    headers = {"x-organization-id": "org_test_promotion", "x-user-id": "admin_1", "x-user-role": "admin"}
    symbol_cand_id = sample_normative_setup["item_symbol"].id

    payload = {
        "decision": "approve",
        "action": "promote_and_activate",
        "reviewer_rationale": "Intento inválido de promover símbolo.",
        "rule_code": "SYM-ILLEGAL-01",
        "title": "Símbolo como Regla",
        "severity": "medium",
        "discipline_ids": ["STRUCTURES"],
        "topic_ids": ["DOCUMENT_COMPLETENESS"],
        "execution_phase": 6
    }

    res = client.post(f"/api/v1/rule-candidates/{symbol_cand_id}/promote", headers=headers, json=payload)
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert "símbolo" in res.json()["detail"].lower()
