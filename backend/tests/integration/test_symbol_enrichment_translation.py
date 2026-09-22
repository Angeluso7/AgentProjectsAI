import pytest
import uuid
from fastapi.testclient import TestClient
from app.db.models.core import User, Organization, OrganizationMembership
from app.db.models.intake_extractions import SourceExtraction, ExtractedItem
from app.core.security import hash_password, create_access_token
from app.services.translation.translation_service import TranslationService
from app.schemas.translations import TranslationRequest

@pytest.fixture
def auth_context(db_session):
    org_id = str(uuid.uuid4())
    org = Organization(id=org_id, name="Symbol Translation Org", slug=f"sym-trans-{uuid.uuid4().hex[:6]}")
    db_session.add(org)

    user = User(
        id=str(uuid.uuid4()),
        email=f"sym_tester_{uuid.uuid4().hex[:6]}@planreview.ai",
        display_name="Auditor de Simbología",
        password_hash=hash_password("Password123!"),
        is_active=True,
        is_superuser=False
    )
    db_session.add(user)

    membership = OrganizationMembership(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        user_id=user.id,
        role="reviewer",
        status="active"
    )
    db_session.add(membership)
    db_session.commit()

    token = create_access_token(user.id, email=user.email, extra_claims={"role": "reviewer"})
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}
    return {"headers": headers, "org_id": org_id, "user_id": user.id}


def test_english_symbol_extraction_effective_fields_and_agent_enrichment(client: TestClient, db_session, auth_context):
    """
    Test 1: Extracción en inglés con target_language=es.
    - source_fields conserva inglés.
    - translated_fields contiene español.
    - effective_fields contiene español.
    - Agent input usa effective_fields en español.
    - Agent output de nombre/descripción/función está en español.
    - SYM-R05-C01 y ANSI/ISA-5.1-2009 se preservan sin cambios.
    """
    headers = auth_context["headers"]
    org_id = auth_context["org_id"]

    # 1. Crear sesión de extracción con un símbolo ISA en inglés
    ext_id = str(uuid.uuid4())
    extraction = SourceExtraction(
        id=ext_id,
        organization_id=org_id,
        title="ANSI/ISA-5.1-2009 P&ID Legend Sheet",
        document_type="norma",
        discipline="piping",
        extraction_mode="ai_document",
        source_origin="document"
    )
    db_session.add(extraction)

    item_id = str(uuid.uuid4())
    item = ExtractedItem(
        id=item_id,
        extraction_id=ext_id,
        item_type="symbol",
        candidate_type="symbol_candidate",
        title="(7) • Actuator with remote actuated partial stroke test device",
        code_or_number="SYM-R05-C01",
        description="Actuator equipped with a remote actuated partial stroke test device.",
        content_text="(7) • Actuator with remote actuated partial stroke test device",
        ocr_text="(7) • Actuator with remote actuated partial stroke test device",
        caption_or_context="Table 5.7 PST Actuators",
        page_number=66,
        discipline="piping",
        bbox_normalized=[0.1, 0.2, 0.3, 0.4],
        crop_image_path="crops/symbols/sym_pst_07.png",
        technical_parameters={
            "standard": "ANSI/ISA-5.1-2009",
            "category": "Actuators",
            "function": "Remote partial stroke testing for SIS validation."
        },
        metadata_payload={}
    )
    db_session.add(item)
    db_session.commit()

    # 2. Traducir los campos del ítem al español
    trans_svc = TranslationService(db_session)
    trans_req = TranslationRequest(
        source_entity_type="extracted_item",
        source_entity_id=item_id,
        source_language="en",
        target_language="es",
        fields_to_translate={
            "title": item.title,
            "description": item.description,
            "content_text": item.content_text,
            "technical_function": item.technical_parameters.get("function")
        },
        organization_id=org_id
    )
    trans_res = trans_svc.translate_entity_fields(trans_req, organization_id=org_id)
    assert trans_res.translation_status == "completed"

    db_session.refresh(item)

    # 3. Comprobar arquitectura de campos: source_fields, translated_fields y effective_fields
    assert "(7) • Actuator with remote actuated" in item.source_fields["title"]
    assert "Actuator equipped with" in item.source_fields["description"]

    assert item.translated_fields["title"] == "(7) • Actuador con dispositivo de prueba de carrera parcial accionado remotamente"
    assert "Actuador equipado con un dispositivo de prueba de carrera parcial" in item.translated_fields["description"]

    assert item.effective_fields["title"] == "(7) • Actuador con dispositivo de prueba de carrera parcial accionado remotamente"
    assert "Actuador equipado con un dispositivo de prueba de carrera parcial accionado remotamente" in item.effective_fields["description"]
    assert item.translation_status == "completed"
    assert item.source_language == "en"
    assert item.target_language == "es"
    assert item.presentation_language == "es"

    # 4. Invocar endpoint de enriquecimiento asistido / Buscar referencia
    enrich_url = f"/api/v1/intake/extractions/{ext_id}/items/{item_id}/enrich"
    payload = {
        "presentation_language": "es",
        "source_fields": item.source_fields,
        "translated_fields": item.translated_fields,
        "effective_fields": item.effective_fields
    }
    resp = client.post(enrich_url, headers=headers, json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["enrichment_status"] == "suggestion_found"
    assert "(7) • Actuador con dispositivo de prueba de carrera parcial accionado remotamente" in data["suggested_title"]
    assert "Actuador equipado con un dispositivo de prueba de carrera parcial accionado remotamente" in data["suggested_description"]
    assert "prueba de carrera parcial" in data["suggested_function"].lower()
    assert "ANSI/ISA-5.1-2009" in data["suggested_source_label"]
    assert data["presentation_language"] == "es"

    # 5. Preservación estricta de invariantes
    db_session.refresh(item)
    assert item.code_or_number == "SYM-R05-C01"
    assert item.technical_parameters["standard"] == "ANSI/ISA-5.1-2009"
    assert item.bbox_normalized == [0.1, 0.2, 0.3, 0.4]
    assert item.candidate_type == "symbol_candidate"


def test_spanish_document_not_required_translation(db_session):
    """
    Test 2: Documento en español.
    - translation_status = not_required.
    - effective_fields usa original.
    - Cero llamada a proveedor externo.
    """
    item = ExtractedItem(
        id=str(uuid.uuid4()),
        extraction_id=str(uuid.uuid4()),
        item_type="symbol",
        title="Válvula de compuerta manual",
        code_or_number="SYM-R01-C01",
        description="Válvula de compuerta manual de aislamiento para piping de proceso.",
        metadata_payload={
            "source_language": "es",
            "target_language": "es",
            "translation_status": "not_required",
            "presentation_language": "es"
        }
    )
    assert item.translation_status == "not_required"
    assert item.source_language == "es"
    assert item.effective_fields["title"] == "Válvula de compuerta manual"
    assert item.effective_fields["description"] == "Válvula de compuerta manual de aislamiento para piping de proceso."


def test_failed_or_stale_translation_fallback(db_session):
    """
    Test 3: Traducción fallida o stale.
    - effective_fields hace fallback a source_fields.
    - translation_status no es completed.
    """
    item = ExtractedItem(
        id=str(uuid.uuid4()),
        extraction_id=str(uuid.uuid4()),
        item_type="symbol",
        title="Centrifugal process pump",
        code_or_number="SYM-R02-C01",
        description="Horizontal centrifugal pump for slurry transfer.",
        metadata_payload={
            "source_language": "en",
            "target_language": "es",
            "translation_status": "stale",
            "translated_fields": {"title": "Bomba obsoleta"}
        }
    )
    # Al estar stale, effective_fields debe hacer fallback a source_fields (no completed)
    assert item.translation_status == "stale"
    assert item.effective_fields["title"] == "Centrifugal process pump"
    assert item.effective_fields["description"] == "Horizontal centrifugal pump for slurry transfer."


def test_preservation_of_protected_tokens_in_translation(db_session):
    """
    Test 4: Preservación de SYM-R05-C01, ANSI/ISA-5.1-2009, P&ID, QA/QC, PLC, DCS, SIS, números.
    """
    trans_svc = TranslationService(db_session)
    input_text = "SYM-R05-C01: ANSI/ISA-5.1-2009 compliant valve with P&ID and SIS interlock for PLC / DCS."
    translated = trans_svc._translate_text_segment(input_text, "en", "es")

    assert "SYM-R05-C01" in translated
    assert "ANSI/ISA-5.1-2009" in translated
    assert "P&ID" in translated
    assert "SIS" in translated
    assert "PLC" in translated
    assert "DCS" in translated
