import pytest
from sqlalchemy.orm import Session
from app.services.discovery.web_search_engine import WebSearchEngine
from app.services.intake.ai_extractor import AiDocumentExtractorService

def test_web_search_engine_discovery():
    engine = WebSearchEngine()
    results = engine.search("Simbología piping ISA S5.1", max_results=10)
    assert isinstance(results, list)
    assert len(results) > 0
    # Verificar que los resultados traigan los campos requeridos
    for r in results:
        assert "title" in r
        assert "url" in r
        assert "domain" in r
        assert "engine" in r

def test_web_search_technical_reranking_piping(db_session: Session):
    extractor = AiDocumentExtractorService(db=db_session)
    results = extractor.search_web_sources(
        search_prompt="Simbología piping ISA S5.1",
        discipline="Piping e Instrumentación",
        document_type="any_web_doc",
        max_results=10
    )
    
    assert isinstance(results, list)
    assert len(results) > 0
    
    # 1. Verificar que no existan dominios residenciales/urbanos irrelevantes (ej. MINVU)
    for res in results:
        domain = res["domain"].lower()
        assert "minvu.gob.cl" not in domain, f"MINVU no debe aparecer en búsqueda de piping ISA: {res}"
        assert "portalinmobiliario.com" not in domain
        
    # 2. Verificar que los resultados contengan señales técnicas de piping o ISA
    top_matches = 0
    for res in results:
        content = f"{res['title']} {res['snippet']} {res['url']}".lower()
        if any(term in content for term in ["piping", "isa", "p&id", "instrument", "valve", "simbolog", "tuber"]):
            top_matches += 1
            
    assert top_matches >= 1, "Al menos una fuente de piping / ISA debe estar presente y verificada en el top."

def test_web_search_diversity_per_domain(db_session: Session):
    extractor = AiDocumentExtractorService(db=db_session)
    results = extractor.search_web_sources(
        search_prompt="Simbología piping ISA S5.1",
        discipline="Piping",
        max_results=20
    )
    
    domain_counts = {}
    for r in results:
        d = r["domain"].lower()
        domain_counts[d] = domain_counts.get(d, 0) + 1
        assert domain_counts[d] <= 3, f"El dominio {d} supera el límite de diversidad (máximo 3 fuentes por dominio)."

def test_web_search_progressive_strategy_and_diagnostics(db_session: Session):
    extractor = AiDocumentExtractorService(db=db_session)
    diag_output = extractor.search_web_sources_with_diagnostics(
        search_prompt="Simbología piping ISA S5.1",
        discipline="Piping e Instrumentación",
        max_results=10
    )
    
    assert "results" in diag_output
    assert "diagnostics" in diag_output
    diag = diag_output["diagnostics"]
    
    assert "provider_used" in diag
    assert "raw_count" in diag
    assert "http_valid_count" in diag
    assert "stage_applied" in diag
    assert "discarded_reasons" in diag
    assert "final_count" in diag
    
    assert diag["provider_used"] in ["tavily", "bing_v7", "serper_google", "duckduckgo", "curated_technical_backup"]
    assert diag["stage_applied"] in ["stage_1_strict", "stage_2_relaxed_threshold", "stage_3_expanded_query", "stage_4_curated_backup"]
    assert isinstance(diag["discarded_reasons"], dict)

def test_curated_backup_explicit_tagging():
    engine = WebSearchEngine()
    curated = engine._get_curated_technical_fallback("Simbología piping ISA S5.1")
    assert len(curated) > 0
    for item in curated:
        assert item["is_curated_backup"] is True
        assert item["source_origin_type"] == "curated_technical_backup"
        assert item["engine"] == "curated_technical_backup"
        assert "Respaldo" in item["title"]


