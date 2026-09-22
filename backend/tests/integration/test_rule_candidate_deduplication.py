import pytest
import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.models.core import Organization, Project
from app.db.models.intake_extractions import SourceExtraction, ExtractedItem, RuleDocument, RuleDocumentItem
from app.db.repositories.intake_extraction_repository import IntakeExtractionRepository

@pytest.fixture
def setup_org_and_project(db_session: Session):
    org = db_session.query(Organization).first()
    if not org:
        org = Organization(id=str(uuid.uuid4()), name="Org Deduplicacion Test", slug="org-dedup-test", status="active")
        db_session.add(org)
        db_session.flush()

    proj = db_session.query(Project).filter(Project.organization_id == org.id).first()
    if not proj:
        proj = Project(id=str(uuid.uuid4()), organization_id=org.id, name="Proyecto Test Dedup", code="PRJ-DEDUP", status="active")
        db_session.add(proj)
        db_session.flush()

    db_session.commit()
    return org, proj


def test_rule_candidate_exact_match_and_backend_blocking(client: TestClient, db_session: Session, setup_org_and_project):
    """
    Verifica que:
    1. Una regla candidata con coincidencia exacta contra el Motor QA/QC se clasifica como 'exact_match_existing_rule'.
    2. 'blocked_from_acceptance' se establece en True.
    3. La regla candidata SIGUE APARECIENDO en el listado de candidatos (no desaparece).
    4. Muestra la referencia exacta a la regla existente en el motor.
    5. Intentar marcarla como 'accepted' / 'validada' vía PUT retorna HTTP 409 Conflict.
    6. Intentar incorporarla vía POST /commit retorna HTTP 409 Conflict.
    """
    org, proj = setup_org_and_project
    repo = IntakeExtractionRepository(db_session)

    # 1. Crear documento y regla existente activa en el Motor QA/QC
    rule_doc_id = str(uuid.uuid4())
    existing_rule_id = str(uuid.uuid4())

    existing_doc = RuleDocument(
        id=rule_doc_id,
        organization_id=org.id,
        project_id=proj.id,
        title="Norma Técnica de Seguridad Eléctrica NSEG-05",
        document_type="norma",
        source_origin="con_ia_documento",
        authority="SEC",
        discipline="electrical",
        version="1.0",
        status="active",
        items_count=1,
        rules_count=1
    )
    db_session.add(existing_doc)

    existing_item = RuleDocumentItem(
        id=existing_rule_id,
        rule_document_id=rule_doc_id,
        item_type="rule",
        source_origin="document",
        title="Distancia mínima de seguridad entre conductores eléctricos y ductos de gas",
        code_or_number="SEC-ELEC-401",
        description="Los conductores de energía eléctrica deben mantener una separación libre mínima de 30 cm respecto a tuberías de gas.",
        content_text="Los conductores de energía eléctrica deben mantener una separación libre mínima de 30 cm respecto a tuberías de gas.",
        status="active"
    )
    db_session.add(existing_item)
    db_session.commit()

    # 2. Crear una nueva sesión de extracción
    extraction = repo.create_extraction_session(
        title="Extracción de Prueba Deduplicación",
        document_type="norma",
        authority="SEC",
        discipline="electrical",
        extraction_mode="ai_document",
        source_origin="document",
        project_id=proj.id
    )

    # 3. Agregar una regla candidata que coincide exactamente por código y contenido
    candidate_item = repo.add_extracted_item(
        extraction_id=extraction.id,
        item_type="rule",
        candidate_type="rule_candidate",
        title="Distancia mínima de seguridad entre conductores eléctricos y ductos de gas",
        code_or_number="SEC-ELEC-401",
        description="Los conductores de energía eléctrica deben mantener una separación libre mínima de 30 cm respecto a tuberías de gas.",
        content_text="Los conductores de energía eléctrica deben mantener una separación libre mínima de 30 cm respecto a tuberías de gas.",
        target_destination="rules_engine",
        review_status="to_confirm"
    )

    # 4. Validar clasificación de coincidencia exacta
    assert candidate_item.duplicate_status == "exact_match_existing_rule"
    assert candidate_item.blocked_from_acceptance is True
    assert candidate_item.best_match_rule_code == "SEC-ELEC-401"
    assert candidate_item.best_match_title == "Distancia mínima de seguridad entre conductores eléctricos y ductos de gas"
    assert candidate_item.duplicate_confidence == 1.0
    assert "Coincidencia exacta" in (candidate_item.duplicate_reason or "")

    # 5. Validar que la regla SIGUE en el listado de candidatos (GET /candidates)
    resp_list = client.get(f"/api/v1/intake/extractions/{extraction.id}/candidates")
    assert resp_list.status_code == 200
    candidates = resp_list.json()
    assert len(candidates) == 1
    c_data = candidates[0]
    assert c_data["id"] == candidate_item.id
    assert c_data["duplicate_status"] == "exact_match_existing_rule"
    assert c_data["blocked_from_acceptance"] is True
    assert c_data["best_match_rule_code"] == "SEC-ELEC-401"

    # 6. Intentar aceptar/validar la regla vía PUT -> Debe fallar con HTTP 409 Conflict
    resp_put = client.put(
        f"/api/v1/intake/extractions/{extraction.id}/items/{candidate_item.id}",
        json={"review_status": "accepted"}
    )
    assert resp_put.status_code == 409
    err_detail = resp_put.json().get("detail", "")
    assert "ya existe en el Motor de Reglas QA/QC" in err_detail

    # 7. Intentar incorporar/commit hacia Motor QA/QC -> Debe fallar con HTTP 409 Conflict
    resp_commit = client.post(
        f"/api/v1/intake/extractions/{extraction.id}/commit",
        json={"approved_item_ids": [candidate_item.id]}
    )
    assert resp_commit.status_code == 409
    commit_err = resp_commit.json().get("detail", "")
    assert "ya existe en el Motor de Reglas QA/QC" in commit_err


def test_likely_duplicate_rule_is_not_blocked(client: TestClient, db_session: Session, setup_org_and_project):
    """
    Verifica que:
    1. Una regla con similitud parcial alta se clasifique como 'likely_duplicate_existing_rule'.
    2. 'blocked_from_acceptance' permanezca en False.
    3. Permita ser aceptada y validada normalmente sin bloqueo 409.
    """
    org, proj = setup_org_and_project
    repo = IntakeExtractionRepository(db_session)

    # 1. Crear documento y regla existente en el motor
    rule_doc_id = str(uuid.uuid4())
    existing_doc = RuleDocument(
        id=rule_doc_id,
        organization_id=org.id,
        project_id=proj.id,
        title="Manual de Climatización y Ventilación HVAC",
        document_type="manual",
        source_origin="con_ia_documento",
        authority="ASHRAE",
        discipline="mechanical",
        version="1.0",
        status="active"
    )
    db_session.add(existing_doc)

    existing_item = RuleDocumentItem(
        id=str(uuid.uuid4()),
        rule_document_id=rule_doc_id,
        item_type="rule",
        source_origin="document",
        title="Velocidad máxima en ductos principales de aire",
        code_or_number="HVAC-VEL-01",
        description="La velocidad de flujo de aire en ductos principales no debe exceder 7.5 m/s en zonas de oficinas.",
        content_text="La velocidad de flujo de aire en ductos principales no debe exceder 7.5 m/s en zonas de oficinas.",
        status="active"
    )
    db_session.add(existing_item)
    db_session.commit()

    # 2. Crear sesión de extracción
    extraction = repo.create_extraction_session(
        title="Sesión HVAC Parcial",
        document_type="manual",
        authority="ASHRAE",
        discipline="mechanical",
        project_id=proj.id
    )

    # 3. Agregar regla con redacción similar pero código nuevo y matices distintos
    likely_item = repo.add_extracted_item(
        extraction_id=extraction.id,
        item_type="rule",
        candidate_type="rule_candidate",
        title="Límite de velocidad de aire en ductos de distribución",
        code_or_number="HVAC-AIR-NEW-02",
        description="El flujo de aire en ductos de impulsión debe mantenerse en rangos menores a 8.0 m/s para control acústico.",
        content_text="El flujo de aire en ductos de impulsión debe mantenerse en rangos menores a 8.0 m/s para control acústico.",
        target_destination="rules_engine",
        review_status="to_confirm"
    )

    # 4. Validar que NO esté bloqueada
    assert likely_item.duplicate_status in ["likely_duplicate_existing_rule", "related_existing_rule", "no_match"]
    assert likely_item.blocked_from_acceptance is False

    # 5. Validar que el PUT para aceptar sea exitoso (HTTP 200)
    resp_put = client.put(
        f"/api/v1/intake/extractions/{extraction.id}/items/{likely_item.id}",
        json={"review_status": "accepted"}
    )
    assert resp_put.status_code == 200
    assert resp_put.json()["review_status"] == "accepted"


def test_inactive_or_draft_rules_in_motor_do_not_block_candidates(client: TestClient, db_session: Session, setup_org_and_project):
    """
    Verifica que reglas en estado 'draft', 'archived' o 'inactive' en el motor NO bloqueen nuevas reglas candidatas.
    """
    org, proj = setup_org_and_project
    repo = IntakeExtractionRepository(db_session)

    # 1. Crear documento en estado 'draft' en el motor
    draft_doc_id = str(uuid.uuid4())
    draft_doc = RuleDocument(
        id=draft_doc_id,
        organization_id=org.id,
        project_id=proj.id,
        title="Borrador no validado",
        document_type="manual",
        source_origin="con_ia_documento",
        discipline="architecture",
        version="0.1",
        status="draft" # NO elegible para bloqueo
    )
    db_session.add(draft_doc)

    draft_item = RuleDocumentItem(
        id=str(uuid.uuid4()),
        rule_document_id=draft_doc_id,
        item_type="rule",
        source_origin="document",
        title="Ancho libre de pasillos interiores",
        code_or_number="ARCH-CORR-DRAFT",
        description="Pasillos principales con ancho libre de 1.40 m.",
        content_text="Pasillos principales con ancho libre de 1.40 m.",
        status="draft"
    )
    db_session.add(draft_item)
    db_session.commit()

    # 2. Crear sesión de extracción
    extraction = repo.create_extraction_session(
        title="Sesión Arquitectura",
        document_type="norma",
        discipline="architecture",
        project_id=proj.id
    )

    # 3. Agregar candidato con el mismo código
    candidate = repo.add_extracted_item(
        extraction_id=extraction.id,
        item_type="rule",
        candidate_type="rule_candidate",
        title="Ancho libre de pasillos interiores",
        code_or_number="ARCH-CORR-DRAFT",
        description="Pasillos principales con ancho libre de 1.40 m.",
        content_text="Pasillos principales con ancho libre de 1.40 m.",
        target_destination="rules_engine",
        review_status="to_confirm"
    )

    # 4. Validar que NO fue bloqueado porque la regla del motor está en 'draft'
    assert candidate.blocked_from_acceptance is False
    assert candidate.duplicate_status == "no_match"
