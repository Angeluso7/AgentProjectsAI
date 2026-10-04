import pytest
from unittest.mock import patch, MagicMock
from app.services.discovery.safe_url_validator import SafeUrlValidator
from app.services.discovery.page_content_validator import PageContentValidator
from app.services.intake.ai_extractor import AiDocumentExtractorService
from app.db.repositories.intake_extraction_repository import IntakeExtractionRepository


def test_ssrf_validator_blocks_private_and_loopback_ips():
    """Valida bloqueo estricto de localhost, 127.0.0.1, IPs privadas RFC1918 y endpoints de metadata de nubes."""
    # 1. Localhost y loopback
    safe, err = SafeUrlValidator.is_safe_url("http://localhost:8000/api")
    assert not safe
    assert "Host bloqueado" in err or "privada" in err

    safe, err = SafeUrlValidator.is_safe_url("http://127.0.0.1/admin")
    assert not safe
    assert "privada" in err or "loopback" in err

    # 2. Redes privadas
    safe, err = SafeUrlValidator.is_safe_url("http://10.0.0.5/secrets")
    assert not safe

    safe, err = SafeUrlValidator.is_safe_url("http://192.168.1.100/router")
    assert not safe

    safe, err = SafeUrlValidator.is_safe_url("http://172.16.0.1/internal")
    assert not safe

    # 3. Metadata endpoint (Cloud AWS / GCP)
    safe, err = SafeUrlValidator.is_safe_url("http://169.254.169.254/latest/meta-data")
    assert not safe

    safe, err = SafeUrlValidator.is_safe_url("http://metadata.google.internal/computeMetadata/v1")
    assert not safe

    # 4. Esquema no permitido (file://, ftp://)
    safe, err = SafeUrlValidator.is_safe_url("file:///etc/passwd")
    assert not safe
    assert "Esquema no permitido" in err

    # 5. URL pública legítima
    safe, err = SafeUrlValidator.is_safe_url("https://www.wermac.org/documents/pid_symbols.html")
    assert safe
    assert err is None


def test_ssrf_validator_blocks_redirect_to_private_network():
    """Valida que si un servidor público responde 302 redirigiendo a una IP privada, el validador corte la petición."""
    # Simular que la URL externa redirige a http://192.168.1.1/secret
    mock_resp_1 = MagicMock()
    mock_resp_1.status_code = 302
    mock_resp_1.headers = {"Location": "http://192.168.1.1/secret"}

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.get.return_value = mock_resp_1
        mock_client_cls.return_value = mock_client

        success, err, data = SafeUrlValidator.safe_fetch_html("https://example.com/external-redirect")
        assert not success
        assert "ssrf_redirect_block" in err


def test_inspect_manual_url_valid_with_internal_sublinks(db_session):
    """Valida la inspección profunda de una URL manual válida con descubrimiento y filtrado de subenlaces del mismo dominio."""
    sample_html = """
    <!DOCTYPE html>
    <html>
        <head>
            <title>P&ID Symbols and Notation Guide - Wermac</title>
            <link rel="canonical" href="https://www.wermac.org/documents/pid_symbols.html" />
        </head>
        <body>
            <h1>Piping and Instrumentation Diagram Symbols (ISA-5.1)</h1>
            <p>Comprehensive guide for piping symbols, control valves, gate valves, pumps and instrumentation lines.</p>
            <table>
                <tr><th>Symbol</th><th>Description</th><th>ISA Code</th></tr>
                <tr><td>FCV</td><td>Flow Control Valve</td><td>ISA S5.1</td></tr>
                <tr><td>PT</td><td>Pressure Transmitter</td><td>ISA S5.1</td></tr>
            </table>
            <!-- Enlaces internos válidos -->
            <a href="/documents/valves_symbols.html">Valve Identification and Codes</a>
            <a href="/documents/line_designations.html">Line Designations and Abbreviations</a>
            <!-- Enlace excluido (auth/login) -->
            <a href="/login">User Login</a>
            <!-- Enlace externo (otro dominio) -->
            <a href="https://www.external-site.org/info">External Reference</a>
        </body>
    </html>
    """

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = sample_html
    mock_resp.headers = {"content-type": "text/html"}

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        service = AiDocumentExtractorService(db_session)
        inspection = service.inspect_manual_url(
            url="https://www.wermac.org/documents/pid_symbols.html",
            discipline="Mecánica",
            document_type="norma",
            search_prompt="Simbología piping ISA S5.1"
        )

        assert inspection["inspection_status"] in ["accessible", "warning"]
        assert inspection["main_source"] is not None
        assert inspection["main_source"]["title"] == "P&ID Symbols and Notation Guide - Wermac"
        assert inspection["main_source"]["domain"] == "www.wermac.org"
        assert inspection["main_source"]["canonical_url"] == "https://www.wermac.org/documents/pid_symbols.html"
        assert inspection["main_source"]["match_bucket"] in ["FULL_MATCH", "HIGH_MATCH"]

        # Verificar enlaces internos descubiertos
        internal_urls = [l["url"] for l in inspection["internal_links"]]
        assert "https://www.wermac.org/documents/valves_symbols.html" in internal_urls
        assert "https://www.wermac.org/documents/line_designations.html" in internal_urls
        # No debe incluir enlaces de login ni enlaces externos
        assert not any("/login" in u for u in internal_urls)
        assert not any("external-site.org" in u for u in internal_urls)


def test_inspect_manual_url_rejects_ssrf_and_soft_404(db_session):
    """Valida rechazo inmediato de URLs con SSRF o pantallas de error Soft-404."""
    service = AiDocumentExtractorService(db_session)

    # 1. Rechazo por SSRF
    res_ssrf = service.inspect_manual_url("http://127.0.0.1:5000/env")
    assert res_ssrf["inspection_status"] == "invalid"
    assert "SSRF" in res_ssrf["message"]

    # 2. Rechazo por Soft-404 "Something's wrong here..."
    error_html = """
    <html>
        <head><title>Engineering Portal</title></head>
        <body>
            <h2>Something's wrong here...</h2>
            <p>0 results found. We could not find the page you requested.</p>
        </body>
    </html>
    """
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = error_html
    mock_resp.headers = {"content-type": "text/html"}

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        res_404 = service.inspect_manual_url("https://www.enggexample.com/broken-sheet")
        assert res_404["inspection_status"] == "invalid"
        assert "soft_404" in res_404["message"] or "error" in res_404["message"].lower()


def test_extract_from_manual_url_main_and_sublinks_persistence(db_session):
    """Valida la extracción estructurada desde la URL principal y subenlaces seleccionados, con persistencia en DB y auditoría."""
    main_source = {
        "url": "https://www.wermac.org/documents/pid_symbols.html",
        "discovered_url": "https://www.wermac.org/documents/pid_symbols.html",
        "resolved_url": "https://www.wermac.org/documents/pid_symbols.html",
        "canonical_url": "https://www.wermac.org/documents/pid_symbols.html",
        "validated_content_url": "https://www.wermac.org/documents/pid_symbols.html",
        "title": "P&ID Symbols and Notation Guide",
        "snippet": "Guide for piping and instrumentation diagram symbols according to ISA 5.1 standard.",
        "domain": "www.wermac.org",
        "estimated_type": "Norma Técnica",
        "source_quality_tier": "secondary",
        "quality_classification": "technical_specialized",
        "authority": "ISA",
        "detected_language": "en",
        "url_provenance": "search_provider",
        "provider_name": "manual_url_entry",
        "validation_status": "validated",
        "match_bucket": "FULL_MATCH",
        "coverage_score": 95.0
    }

    sublinks = [
        {
            "url": "https://www.wermac.org/documents/valves_symbols.html",
            "discovered_url": "https://www.wermac.org/documents/valves_symbols.html",
            "resolved_url": "https://www.wermac.org/documents/valves_symbols.html",
            "validated_content_url": "https://www.wermac.org/documents/valves_symbols.html",
            "title": "Valve Identification and Codes",
            "snippet": "Symbols for gate, globe, check and butterfly valves in process piping.",
            "domain": "www.wermac.org",
            "estimated_type": "Subpágina Especializada",
            "source_quality_tier": "secondary",
            "quality_classification": "technical_specialized",
            "authority": "ISA",
            "detected_language": "en",
            "url_provenance": "internal_link",
            "provider_name": "manual_url_entry",
            "validation_status": "validated",
            "match_bucket": "HIGH_MATCH",
            "coverage_score": 80.0
        }
    ]

    service = AiDocumentExtractorService(db_session)
    session = service.extract_from_manual_url(
        main_source=main_source,
        selected_sublinks=sublinks,
        discipline="Mecánica",
        document_type="norma",
        authority="ISA",
        search_prompt="Simbología piping ISA S5.1",
        translate_to_spanish=True
    )

    assert session is not None
    assert session.extraction_mode == "manual_web_url"
    assert session.source_origin == "web"
    assert session.source_url == "https://www.wermac.org/documents/pid_symbols.html"

    # Verificar extracted_items
    repo = IntakeExtractionRepository(db_session)
    items = repo.list_extracted_items(session.id)
    assert len(items) > 0

    # Verificar que los ítems tienen procedencia web y snapshot
    for item in items:
        assert item.source_origin == "web"
        assert item.source_reference is not None
        assert "wermac.org" in item.source_reference

    # Verificar auditoría en WebSearchHistory
    history = repo.list_web_search_history(limit=5)
    assert len(history) > 0
    latest = history[0]
    assert latest.provider_used == "manual_url_entry"
    assert latest.source_extraction_id == session.id
    assert "https://www.wermac.org/documents/valves_symbols.html" in latest.metadata_payload.get("selected_internal_links", [])


def test_manual_url_api_endpoints_integration(client, db_session):
    """Valida los endpoints POST /inspect-manual-url y POST /process-manual-url mediante FastAPI TestClient."""
    sample_html = """
    <html>
        <head><title>ISA-5.1 Technical Guide</title></head>
        <body>
            <h1>ISA 5.1 Instrumentation Codes</h1>
            <p>Standard symbols for piping and instrumentation diagrams.</p>
            <a href="/subpage1">Subpage 1</a>
        </body>
    </html>
    """
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = sample_html
    mock_resp.headers = {"content-type": "text/html"}

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        # 1. Test /inspect-manual-url
        inspect_payload = {
            "url": "https://www.isa.org/standards/isa5-1.html",
            "discipline": "Instrumentación",
            "document_type": "norma",
            "search_prompt": "ISA S5.1"
        }
        res_inspect = client.post("/api/v1/intake/extractions/inspect-manual-url", json=inspect_payload)
        assert res_inspect.status_code == 200
        inspect_data = res_inspect.json()
        assert inspect_data["inspection_status"] in ["accessible", "warning"]
        assert inspect_data["main_source"]["title"] == "ISA-5.1 Technical Guide"

        # 2. Test /process-manual-url
        process_payload = {
            "main_source": inspect_data["main_source"],
            "selected_sublinks": inspect_data["internal_links"],
            "discipline": "Instrumentación",
            "document_type": "norma",
            "authority": "ISA",
            "search_prompt": "ISA S5.1",
            "translate_to_spanish": True
        }
        res_process = client.post("/api/v1/intake/extractions/process-manual-url", json=process_payload)
        assert res_process.status_code == 201
        process_data = res_process.json()
        assert process_data["extraction_mode"] == "manual_web_url"
        assert process_data["source_origin"] == "web"
        assert len(process_data["items"]) > 0
        assert process_data["id"] is not None

