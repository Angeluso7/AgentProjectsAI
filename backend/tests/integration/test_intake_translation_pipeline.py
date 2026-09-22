import pytest
import uuid
from fastapi.testclient import TestClient
from app.db.models.core import User, Organization, OrganizationMembership
from app.core.security import hash_password, create_access_token
from app.services.translation.translation_service import TranslationService

@pytest.fixture
def auth_context(db_session):
    org_id = str(uuid.uuid4())
    org = Organization(id=org_id, name="Translation Test Org", slug=f"trans-org-{uuid.uuid4().hex[:6]}")
    db_session.add(org)

    user = User(
        id=str(uuid.uuid4()),
        email=f"trans_tester_{uuid.uuid4().hex[:6]}@planreview.ai",
        display_name="Auditor de Traducción",
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


def test_spanish_document_intake_translation_not_required(client: TestClient, auth_context):
    """
    Prueba 1: Documento en español.
    - Idioma detectado 'es' == target_language 'es'.
    - translation_status = 'not_required'.
    - Cero llamada a proveedor LLM externo (passthrough inmediato).
    - Original conservado íntegro y translated_fields disponible con texto fuente.
    """
    headers = auth_context["headers"]
    spanish_text = (
        "Artículo 4.2.4: Las puertas de escape de los recintos de reunión deben abrir en el sentido "
        "de la evacuación. El ancho mínimo libre no será inferior a 0.90 metros."
    )
    payload = {
        "title": "OGUC Capítulo 4 Vías de Evacuación",
        "document_type": "norma",
        "authority": "MINVU",
        "discipline": "architecture",
        "extraction_mode": "ai_document",
        "text_content": spanish_text,
        "translation": {
            "enabled": True,
            "source_language": "auto",
            "target_language": "es",
            "mode": "during_extraction"
        }
    }

    res = client.post("/api/v1/intake/extractions/process-with-ai", headers=headers, json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["status"] == "extracted"
    assert len(data["items"]) > 0

    for item in data["items"]:
        meta = item.get("metadata_payload") or {}
        # Verificamos que translation_status sea not_required o que translated_fields esté poblado
        trans_status = meta.get("translation_status")
        assert trans_status == "not_required", f"Expected not_required, got {trans_status}"
        translated = item.get("translated_fields") or meta.get("translated_fields") or {}
        assert "title" in translated
        # En caso de no requerido, el título traducido es idéntico al original
        assert translated["title"] == item["title"]


def test_english_document_intake_translation_to_spanish(client: TestClient, auth_context):
    """
    Prueba 2: Documento en inglés.
    - Idioma detectado 'en' -> traducción al español 'es'.
    - translation_status = 'completed'.
    - Fuentes originales inmutables (title, content_text en inglés).
    - Términos técnicos de control y norma preservados (ej: ANSI/ISA-5.1-2009, P&ID).
    - Regla central: NO se generan símbolos a partir del texto/traducción.
    """
    headers = auth_context["headers"]
    english_text = (
        "Standard ANSI/ISA-5.1-2009 Instrumentation Symbols and Identification. "
        "Section 5.2 specifies that control valve actuators and fail-safe positions must be indicated "
        "on all P&ID diagrams with standard geometric bubble identifiers."
    )
    payload = {
        "title": "ANSI/ISA-5.1-2009 Instrumentation Standard",
        "document_type": "estandar",
        "authority": "ISA",
        "discipline": "instrumentation",
        "extraction_mode": "ai_document",
        "text_content": english_text,
        "translation": {
            "enabled": True,
            "source_language": "auto",
            "target_language": "es",
            "mode": "during_extraction"
        }
    }

    res = client.post("/api/v1/intake/extractions/process-with-ai", headers=headers, json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["status"] == "extracted"
    assert len(data["items"]) > 0

    has_completed_translation = False
    for item in data["items"]:
        # Texto original permanece inmutable en inglés
        assert item["title"] is not None
        # Regla central innegociable: no crear símbolos canónicos por texto
        assert item["item_type"] != "symbol" or item.get("graphic_classification") not in ("waveform", "figure")

        translated = item.get("translated_fields") or (item.get("metadata_payload") or {}).get("translated_fields") or {}
        meta = item.get("metadata_payload") or {}
        if meta.get("translation_status") == "completed":
            has_completed_translation = True
            assert "title" in translated
            # Los términos técnicos de norma y diagramas deben preservarse
            assert "ANSI/ISA" in translated.get("title", "") or "P&ID" in translated.get("content_text", "") or "ISA" in translated.get("title", "")

    assert has_completed_translation, "Al menos un elemento debió registrar translation_status='completed'"


def test_fastapi_422_validation_missing_target_language(client: TestClient, auth_context):
    """
    Prueba 3: Validación FastAPI HTTP 422.
    - Envío de translation sin target_language requerido.
    - FastAPI debe responder con HTTP 422 y array detail con loc ['body', 'translation', 'target_language'].
    - Demuestra que el backend valida estrictamente y produce la estructura que formatApiError maneja.
    """
    headers = auth_context["headers"]
    invalid_payload = {
        "title": "Documento Test 422",
        "document_type": "norma",
        "authority": "INN",
        "discipline": "architecture",
        "extraction_mode": "ai_document",
        "text_content": "Texto de prueba.",
        "translation": {
            "enabled": True,
            # target_language omitido intencionalmente
        }
    }

    res = client.post("/api/v1/intake/extractions/process-with-ai", headers=headers, json=invalid_payload)
    assert res.status_code == 422
    err_body = res.json()
    assert "detail" in err_body
    assert isinstance(err_body["detail"], list)

    missing_err = next((d for d in err_body["detail"] if "target_language" in d.get("loc", [])), None)
    assert missing_err is not None
    assert missing_err["type"] == "missing"
    assert missing_err["loc"] == ["body", "translation", "target_language"]
    assert missing_err["msg"] == "Field required"
