import pytest
from unittest.mock import patch, MagicMock
from app.services.discovery.page_content_validator import PageContentValidator
from app.services.discovery.language_detector import LanguageDetector
from app.services.discovery.subpage_crawler import SubpageCrawler
from app.services.discovery.term_coverage_matcher import TermCoverageMatcher
from app.services.intake.ai_extractor import AiDocumentExtractorService
from app.db.repositories.intake_extraction_repository import IntakeExtractionRepository


def test_term_coverage_matcher_compounds_and_equivalencies():
    """Verifica la normalización, términos compuestos, equivalencias ES/EN y asignación de buckets."""
    query = "Simbología piping ISA S5.1"
    struct = TermCoverageMatcher.extract_query_structure(query)
    
    assert "isa s5.1" in struct["compounds"] or "isa" in struct["critical_terms"]
    assert "piping" in struct["critical_terms"]
    assert "simbologia" in struct["critical_terms"]

    # 1. Cobertura Alta / Completa (en inglés técnico con ISA 5.1 y P&ID)
    full_eval = TermCoverageMatcher.evaluate_candidate_coverage(
        query_struct=struct,
        url="https://www.wermac.org/documents/pid_symbols.html",
        title="P&ID Symbols and Notation Guide - Wermac",
        snippet="Complete catalog of ISA 5.1 piping and instrumentation diagram symbols, control valves and line identifiers.",
        clean_text="Detailed engineering guide explaining ISA-5.1 symbols, piping codes, and control valve notations."
    )

    assert full_eval["match_bucket"] in ["FULL_MATCH", "HIGH_MATCH"]
    assert full_eval["coverage_score"] >= 65.0
    assert full_eval["critical_coverage_pct"] >= 0.5
    assert len(full_eval["matched_terms"]) > 0

    # 2. Cobertura Nula / Descarte (página irrelevante de portal inmobiliario)
    rejected_eval = TermCoverageMatcher.evaluate_candidate_coverage(
        query_struct=struct,
        url="https://www.portalinmobiliario.com/departamentos-en-arriendo",
        title="Departamentos en Arriendo Santiago Centro",
        snippet="Encuentra los mejores departamentos y propiedades residenciales en arriendo.",
        clean_text="Consulta precios, dormitorios, baños y ubicaciones de inmuebles en la región metropolitana."
    )

    assert rejected_eval["match_bucket"] == "REJECTED"
    assert rejected_eval["coverage_score"] < 15.0


def test_page_content_validator_soft_404_something_wrong_and_loginwall():
    """Valida descarte multicriterio de Soft-404, 'Something's wrong here...', Loginwall y error templates."""
    
    # 1. Caso Soft-404 con "Something's wrong here..."
    error_html = """
    <html>
        <head><title>Technical Portal - Error</title></head>
        <body>
            <h1>Something's wrong here...</h1>
            <p>The page you are looking for does not exist or has been removed from our servers.</p>
        </body>
    </html>
    """
    with patch("httpx.Client") as mock_client:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.url = "https://example.com/broken-subroute"
        mock_resp.text = error_html * 4
        mock_client.return_value.__enter__.return_value.get.return_value = mock_resp

        is_valid, reason, meta = PageContentValidator.validate_url("https://example.com/broken-subroute")
        assert not is_valid
        assert reason == "soft_404_detected"

    # 2. Caso Login Wall / Access Denied
    login_html = """
    <html>
        <head><title>Portal de Normas - Acceso Restringido</title></head>
        <body>
            <h1>Iniciar sesión para continuar</h1>
            <p>Acceso exclusivo para suscriptores. Ingrese sus credenciales para consultar el documento.</p>
        </body>
    </html>
    """
    with patch("httpx.Client") as mock_client:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.url = "https://example.com/restricted"
        mock_resp.text = login_html * 4
        mock_client.return_value.__enter__.return_value.get.return_value = mock_resp

        is_valid, reason, meta = PageContentValidator.validate_url("https://example.com/restricted")
        assert not is_valid
        assert reason == "login_wall_or_paywall_detected"


def test_zero_invented_urls_and_strict_provenance(db_session):
    """Demuestra que todas las URLs tienen procedencia estricta y validated_content_url confirmado."""
    service = AiDocumentExtractorService(db_session)
    
    diag = service.search_web_sources_with_diagnostics(
        search_prompt="Simbología piping ISA S5.1",
        discipline="Piping",
        document_type="norma",
        max_results=5
    )

    results = diag["results"]
    assert len(results) > 0

    for res in results:
        # 1. Debe poseer procedencia explícita
        assert "url_provenance" in res
        assert res["url_provenance"] in ["search_provider", "internal_link", "curated_backup"]
        assert "provider_name" in res
        
        # 2. Debe poseer URL de contenido validada
        assert res.get("validated_content_url") is not None
        assert res.get("validation_status") == "validated"

        # 3. Debe tener score de cobertura y bucket asignado
        assert "match_bucket" in res
        assert res["match_bucket"] in ["FULL_MATCH", "HIGH_MATCH", "MEDIUM_MATCH", "LOW_MATCH"]
        assert res.get("coverage_score", 0) > 0


def test_high_coverage_outranks_generic_official(db_session):
    """Demuestra que una página técnica con alta cobertura supera a una página oficial genérica o vacía."""
    service = AiDocumentExtractorService(db_session)
    query = "Simbología piping ISA S5.1"
    struct = TermCoverageMatcher.extract_query_structure(query)

    # Fuente 1: Especializada con Cobertura Completa (wermac.org)
    spec_eval = TermCoverageMatcher.evaluate_candidate_coverage(
        query_struct=struct,
        url="https://www.wermac.org/documents/pid_symbols.html",
        title="P&ID Symbols and Notation Guide - Wermac",
        snippet="Complete catalog of ISA 5.1 piping and instrumentation diagram symbols.",
        clean_text="Detailed ISA-5.1 piping symbols, valves and instrumentation loops notation guide."
    )

    # Fuente 2: Oficial pero genérica sobre trámites generales (ej. minvu.gob.cl sobre subsidios)
    gen_official_eval = TermCoverageMatcher.evaluate_candidate_coverage(
        query_struct=struct,
        url="https://www.minvu.gob.cl/tramites-generales",
        title="Trámites Generales y Subsidios Habitacionales MINVU",
        snippet="Portal de postulación a subsidios de vivienda y trámites sectoriales.",
        clean_text="Información sobre postulación a llamados DS49 y DS1 para proyectos habitacionales."
    )

    # Puntuación combinada simulada
    spec_total_score = spec_eval["coverage_score"] + 15.0 + 6.0 # coverage + technical_spec + EN boost
    gen_total_score = gen_official_eval["coverage_score"] + 18.0 + 12.0 # low coverage + official + ES boost

    assert spec_eval["coverage_score"] > gen_official_eval["coverage_score"]
    assert spec_total_score > gen_total_score
    assert spec_eval["match_bucket"] in ["FULL_MATCH", "HIGH_MATCH"]


def test_language_detector_ranking_boost():
    """Verifica la detección de idioma y asignación de puntajes de ranking (ES > EN > Other)."""
    spanish_text = "Esta norma técnica describe los símbolos de instrumentación y cañerías para diagramas P&ID según estándares oficiales."
    lang_es, boost_es = LanguageDetector.detect_language(spanish_text)
    assert lang_es == "es"
    assert boost_es == 12.0

    english_text = "This technical standard specifies piping symbols, gate valves, and instrumentation loops for process diagrams."
    lang_en, boost_en = LanguageDetector.detect_language(english_text)
    assert lang_en == "en"
    assert boost_en == 6.0

    assert boost_es > boost_en


def test_subpage_crawler_traceability_and_limits():
    """Verifica que el crawler solo descubra enlaces internos reales respetando profundidad y límites."""
    landing_html = """
    <html>
        <head>
            <title>Wermac Piping Standards Directory</title>
            <link rel="canonical" href="https://www.wermac.org/documents/index.html" />
        </head>
        <body>
            <h1>Piping Documents and Directories</h1>
            <ul>
                <li><a href="/documents/pid_symbols.html">P&ID Symbols and Notation Detailed Guide</a></li>
                <li><a href="/documents/valves_guide.html">Valves and Piping Specifications</a></li>
                <li><a href="https://external-domain.com/unrelated">External Link</a></li>
            </ul>
        </body>
    </html>
    """
    
    with patch.object(PageContentValidator, "validate_url") as mock_val, \
         patch.object(SubpageCrawler, "_is_allowed_by_robots", return_value=True):
        mock_val.return_value = (
            True,
            None,
            {
                "final_url": "https://www.wermac.org/documents/pid_symbols.html",
                "canonical_url": "https://www.wermac.org/documents/pid_symbols.html",
                "useful_length": 1500,
                "title": "P&ID Symbols Detailed Guide",
                "clean_text_sample": "ISA 5.1 piping and instrumentation diagram symbols."
            }
        )

        trace = SubpageCrawler.explore_subpages(
            initial_url="https://www.wermac.org/documents/",
            html_content=landing_html,
            search_prompt="Simbología piping ISA S5.1",
            max_subpages_to_check=5
        )

        assert trace["initial_url"] == "https://www.wermac.org/documents/"
        assert trace["content_subpage_url"] == "https://www.wermac.org/documents/pid_symbols.html"
        assert trace["url_provenance"] == "internal_link"
        assert trace["crawler_depth"] == 1
        assert trace["robots_allowed"] is True
        assert trace["validation_result"] is True


def test_post_extraction_translation_to_spanish(db_session):
    """Verifica que items en inglés sean traducidos al español conservando trazabilidad y textos originales."""
    service = AiDocumentExtractorService(db_session)
    
    english_spec = {
        "item_type": "symbol",
        "title": "Gate Valve Standard Symbol",
        "description": "Standard Gate Valve symbol for process lines according to ISA-5.1.",
        "content_text": "Piping and Instrumentation Diagram standard gate valve symbol representation.",
        "technical_parameters": {"valve_type": "manual"}
    }

    translated = service._translate_item_to_spanish(english_spec)

    assert "Válvula de Compuerta" in translated["title"]
    assert "Válvula de Compuerta" in translated["description"]
    assert "Diagrama de Cañerías e Instrumentación (P&ID)" in translated["content_text"]

    tech_params = translated["technical_parameters"]
    assert tech_params["translation_applied"] is True
    assert tech_params["source_language"] == "en"
    assert tech_params["target_language"] == "es"
    assert tech_params["original_title"] == "Gate Valve Standard Symbol"


def test_web_search_history_persistence(client, db_session):
    """Verifica la persistencia en base de datos del historial con tokens, términos críticos y buckets."""
    service = AiDocumentExtractorService(db_session)
    repo = IntakeExtractionRepository(db_session)

    diag = service.search_web_sources_with_diagnostics(
        search_prompt="Simbología piping ISA S5.1",
        discipline="Piping",
        document_type="norma",
        max_results=5
    )

    assert "results" in diag
    assert "search_history_id" in diag
    history_id = diag["search_history_id"]

    history_record = repo.get_web_search_history_by_id(history_id)
    assert history_record is not None
    assert history_record.search_prompt == "Simbología piping ISA S5.1"
    assert history_record.discipline == "Piping"
    assert history_record.extraction_status == "searched"
    assert len(history_record.results_found) > 0
    assert history_record.metadata_payload.get("query_tokens") is not None
    assert history_record.metadata_payload.get("critical_terms") is not None

    # Probar endpoint API GET /api/v1/intake/extractions/search-history
    res = client.get("/api/v1/intake/extractions/search-history")
    assert res.status_code == 200
    items = res.json()
    assert any(item["id"] == history_id for item in items)

    # Probar endpoint API GET /api/v1/intake/extractions/search-history/{id}
    res_detail = client.get(f"/api/v1/intake/extractions/search-history/{history_id}")
    assert res_detail.status_code == 200
    detail = res_detail.json()
    assert detail["id"] == history_id
    assert detail["search_prompt"] == "Simbología piping ISA S5.1"
    assert len(detail["results_found"]) > 0
