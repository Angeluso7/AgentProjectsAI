import json
import pytest
from unittest.mock import MagicMock

from app.services.ai.claude_client import ClaudeClient, ClaudeClientError, ClaudeClientDisabledError
from app.services.intake.ai_extractor import AiDocumentExtractorService
from app.services.assistant.router import AiEngineRouter
from app.services.engines.registry import EngineRegistry


def test_claude_client_disabled_mode():
    """Confirma que sin API key o con placeholder, ClaudeClient entra en modo disabled sin romper."""
    # Key None
    client_none = ClaudeClient(api_key=None)
    # Si settings tiene key en el entorno, forzamos None explícito
    client_none._raw_api_key = None
    client_none.is_enabled = False
    assert client_none.is_available() is False

    # Key vacía
    client_empty = ClaudeClient(api_key="")
    assert client_empty.is_enabled is False
    assert client_empty.is_available() is False

    # Placeholder sk-ant-xxxxx
    client_placeholder = ClaudeClient(api_key="sk-ant-xxxxx")
    assert client_placeholder.is_enabled is False
    assert client_placeholder.is_available() is False

    # Al invocar complete(), debe lanzar ClaudeClientDisabledError
    with pytest.raises(ClaudeClientDisabledError) as exc_info:
        client_empty.complete("system", "user prompt")
    assert "deshabilitado" in str(exc_info.value)


def test_claude_client_mock_successful_completion():
    """Confirma que con mock inyectado, complete() invoca el SDK y extrae el texto correctamente."""
    mock_sdk = MagicMock()
    mock_block = MagicMock()
    mock_block.text = "Respuesta técnica estructurada de prueba."
    mock_response = MagicMock()
    mock_response.content = [mock_block]
    mock_sdk.messages.create.return_value = mock_response

    client = ClaudeClient(
        api_key="sk-ant-valid-looking-test-key",
        model="claude-sonnet-5-5",
        client=mock_sdk
    )
    assert client.is_available() is True

    result = client.complete(
        system_prompt="Eres un auditor.",
        user_prompt="¿Cuál es el ancho de pasillo?",
        max_tokens=1000,
        temperature=0.2
    )

    assert result == "Respuesta técnica estructurada de prueba."
    mock_sdk.messages.create.assert_called_once()
    call_kwargs = mock_sdk.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-3-5-sonnet-20241022"  # Resuelto desde alias
    assert call_kwargs["max_tokens"] == 1000
    assert call_kwargs["system"] == "Eres un auditor."
    assert call_kwargs["messages"] == [{"role": "user", "content": "¿Cuál es el ancho de pasillo?"}]
    assert call_kwargs["extra_body"] == {"temperature": 0.2}


def test_claude_client_handles_sdk_errors():
    """Confirma que errores del SDK se envuelven en ClaudeClientError sin exponer claves."""
    mock_sdk = MagicMock()
    mock_sdk.messages.create.side_effect = RuntimeError("Conexión interrumpida con Anthropic")

    client = ClaudeClient(
        api_key="sk-ant-test-key",
        client=mock_sdk
    )

    with pytest.raises(ClaudeClientError) as exc_info:
        client.complete(user_prompt="Hola")
    assert "Error invocando Claude API" in str(exc_info.value)


def test_ai_document_extractor_heuristic_fallback_when_disabled(db_session):
    """Confirma que con ANTHROPIC_API_KEY vacía / cliente disabled, el extractor funciona 100% en modo heurístico."""
    disabled_client = ClaudeClient(api_key="")
    extractor = AiDocumentExtractorService(db=db_session, claude_client=disabled_client)

    session = extractor.extract_document_with_ai(
        title="OGUC Titulo 4 Arquitectura",
        document_type="norma",
        discipline="architecture",
        text_content="Art. 4.1.1 Las escaleras principales tendrán un ancho mínimo de 1.20m."
    )

    assert session.status == "extracted"
    assert session.total_items > 0
    assert "Fallback" in session.metadata_info["ai_engine"] or "Local" in session.metadata_info["ai_engine"]
    assert len(session.items) > 0

    # Los items fueron generados por la heurística sin errores
    first_item = session.items[0]
    assert first_item.item_type in ["rule", "chapter", "article"]


def test_ai_document_extractor_uses_mocked_claude_response(db_session):
    """Confirma que con mock de Claude activo, el extractor procesa y utiliza la respuesta estructurada de Claude."""
    mock_response_json = {
        "items": [
            {
                "item_type": "rule",
                "candidate_type": "rule_candidate",
                "code_or_number": "CLAUDE-RULE-01",
                "title": "Regla Extraída por Claude: Resistencia al Fuego",
                "description": "Muros cortafuego deberán contar con resistencia mínima F-120.",
                "content_text": "Exigencia F-120 obligatoria según análisis de Claude.",
                "derived_text": "F-120 en muros medianeros.",
                "ocr_text": "Texto literal F-120.",
                "target_destination": "rules_engine",
                "item_nature": "official_rule",
                "page_number": 1
            },
            {
                "item_type": "article",
                "candidate_type": "premise_candidate",
                "code_or_number": "CLAUDE-ART-02",
                "title": "Artículo Extraído por Claude: Evacuación",
                "description": "Vías de escape expeditas.",
                "content_text": "Despeje total sin obstáculos.",
                "derived_text": "Despeje continuo.",
                "ocr_text": "Texto literal de evacuación.",
                "target_destination": "knowledge_base",
                "item_nature": "official_rule",
                "page_number": 1
            }
        ]
    }

    mock_client = MagicMock(spec=ClaudeClient)
    mock_client.is_available.return_value = True
    mock_client.model = "claude-sonnet-5-5"
    mock_client.complete.return_value = f"```json\n{json.dumps(mock_response_json)}\n```"

    extractor = AiDocumentExtractorService(db=db_session, claude_client=mock_client)
    session = extractor.extract_document_with_ai(
        title="NCh 935 Prevención de Incendios",
        document_type="norma",
        discipline="structures",
        text_content="Texto de prueba para análisis con Claude."
    )

    assert session.status == "extracted"
    assert "Claude Sonnet" in session.metadata_info["ai_engine"]
    assert len(session.items) == 2

    rule_item = next(it for it in session.items if it.code_or_number == "CLAUDE-RULE-01")
    assert rule_item.title == "Regla Extraída por Claude: Resistencia al Fuego"
    assert "F-120" in rule_item.content_text

    art_item = next(it for it in session.items if it.code_or_number == "CLAUDE-ART-02")
    assert art_item.code_or_number == "CLAUDE-ART-02"


def test_ai_document_extractor_fallback_when_claude_fails(db_session):
    """Confirma que ante fallo del API de Claude, el extractor conmuta al fallback heurístico limpiamente."""
    failing_client = MagicMock(spec=ClaudeClient)
    failing_client.is_available.return_value = True
    failing_client.model = "claude-sonnet-5-5"
    failing_client.complete.side_effect = ClaudeClientError("Credit balance too low / 400 error")

    extractor = AiDocumentExtractorService(db=db_session, claude_client=failing_client)

    # Debe capturar el error y caer en el fallback heurístico sin lanzar excepción
    items = extractor._generate_structured_items_from_doc(
        title="Norma con Fallback",
        doc_type="norma",
        discipline="general",
        authority="MINVU",
        raw_text="Párrafo 1 de prueba.\n\nPárrafo 2 de prueba."
    )

    assert len(items) > 0
    assert any("SEC-" in it["code_or_number"] or "Capítulo" in it["code_or_number"] for it in items)


def test_ai_engine_router_claude_routing_and_fallback():
    """Confirma que AiEngineRouter usa Claude cuando está disponible y cae a Tier 1 heurístico si falla."""
    # 1. Router con Claude mockeado
    mock_client = MagicMock(spec=ClaudeClient)
    mock_client.is_available.return_value = True
    mock_client.complete.return_value = "### Diagnóstico Generado por Claude\nAnálisis detallado de RFI."

    router = AiEngineRouter(claude_client=mock_client)

    # Tarea Tier 2 (rule_suggestion)
    init_tier, exec_tier, engine_id, was_esc, reason = router.evaluate_routing(
        task_type="rule_suggestion",
        prompt="Sugerir regla de vanos",
        rag_sources=[]
    )
    assert exec_tier == 2
    assert engine_id == "claude_sonnet"

    resp_md, struct_out, conf, cost = router.execute_inference(
        task_type="rule_suggestion",
        prompt="Sugerir regla de vanos",
        rag_sources=[],
        context_data={},
        executed_tier=exec_tier,
        engine_id=engine_id
    )

    assert "Diagnóstico Generado por Claude" in resp_md
    assert struct_out["rule_logic_type"] == "deterministic_threshold"

    # 2. Router cuando Claude falla: debe hacer fallback sin excepción
    failing_client = MagicMock(spec=ClaudeClient)
    failing_client.is_available.return_value = True
    failing_client.complete.side_effect = ClaudeClientError("Error de cuota API")

    router_fallback = AiEngineRouter(claude_client=failing_client)
    resp_fallback, struct_fb, conf_fb, cost_fb = router_fallback.execute_inference(
        task_type="rule_suggestion",
        prompt="Sugerir regla de vanos",
        rag_sources=[],
        context_data={},
        executed_tier=2,
        engine_id="claude_sonnet"
    )

    assert "Sugerencia de Regla QA/QC Reutilizable" in resp_fallback
    assert struct_fb["rule_logic_type"] == "deterministic_threshold"


def test_engine_registry_claude_and_unconnected_engines():
    """Confirma que EngineRegistry expone claude_sonnet y marca como inactivos los no implementados."""
    reg = EngineRegistry()
    llms = {e.id: e for e in reg.list_engines(category="llm")}

    assert "claude_sonnet" in llms
    claude_eng = llms["claude_sonnet"]
    assert claude_eng.provider == "Anthropic"
    assert claude_eng.required_credentials == ["ANTHROPIC_API_KEY"]

    # Los motores no conectados deben estar explícitamente inactivos
    assert "google_gemini_flash" in llms
    assert llms["google_gemini_flash"].is_active is False
    assert llms["google_gemini_flash"].has_credentials is False

    assert "openai_gpt4o" in llms
    assert llms["openai_gpt4o"].is_active is False
    assert llms["openai_gpt4o"].has_credentials is False
