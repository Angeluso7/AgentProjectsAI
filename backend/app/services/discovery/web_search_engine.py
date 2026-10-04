import os
import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urlparse
import httpx

logger = logging.getLogger(__name__)

class WebSearchEngine:
    """
    Motor de Búsqueda Web Multi-Proveedor para Descubrimiento de Fuentes Técnicas:
    1. Tavily AI Search API (Principal para agentes de IA técnicos)
    2. Bing Web Search API v7 (Secundario corporativo)
    3. Serper Google SERP API (Opcional / Terciario)
    4. DuckDuckGo Search (Fallback final sin API key)
    5. Curated Technical Backup (Respaldo explícitamente etiquetado ante desconexión)

    REGLA DE ORO:
    - Ninguna URL es inventada, construida o concatenada.
    - Cada resultado tiene trazabilidad de procedencia explícita.
    """

    def __init__(self):
        self.tavily_api_key = os.getenv("TAVILY_API_KEY")
        self.bing_api_key = os.getenv("BING_SEARCH_V7_SUBSCRIPTION_KEY") or os.getenv("AZURE_BING_API_KEY")
        self.serper_api_key = os.getenv("SERPER_API_KEY")
        self.google_api_key = os.getenv("GOOGLE_SEARCH_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.google_cx = os.getenv("GOOGLE_SEARCH_CX") or os.getenv("GOOGLE_CSE_ID")

    def search_with_meta(self, query: str, max_results: int = 30) -> Tuple[List[Dict[str, Any]], str]:
        """
        Ejecuta la búsqueda web en orden de cascada y retorna (resultados, proveedor_utilizado).
        """
        query_clean = query.strip()
        if not query_clean:
            return [], "none"

        # 1. Tavily (Principal)
        if self.tavily_api_key:
            try:
                results = self._search_tavily(query_clean, max_results)
                if results:
                    logger.info(f"Tavily API retornó {len(results)} resultados para '{query_clean}'")
                    return results, "tavily"
            except Exception as e:
                logger.warning(f"Tavily API falló: {e}. Pasando a Bing secundario...")

        # 2. Bing Web Search v7 (Secundario)
        if self.bing_api_key:
            try:
                results = self._search_bing(query_clean, max_results)
                if results:
                    logger.info(f"Bing Web Search retornó {len(results)} resultados para '{query_clean}'")
                    return results, "bing_v7"
            except Exception as e:
                logger.warning(f"Bing Search API falló: {e}. Pasando a Serper terciario...")

        # 3. Serper Google SERP (Terciario / Opcional)
        if self.serper_api_key:
            try:
                results = self._search_serper(query_clean, max_results)
                if results:
                    logger.info(f"Serper API retornó {len(results)} resultados para '{query_clean}'")
                    return results, "serper_google"
            except Exception as e:
                logger.warning(f"Serper API falló: {e}. Pasando a DuckDuckGo fallback...")

        # 4. DuckDuckGo (Fallback final sin API key)
        try:
            results = self._search_duckduckgo(query_clean, max_results)
            if results:
                logger.info(f"DuckDuckGo retornó {len(results)} resultados para '{query_clean}'")
                return results, "duckduckgo"
        except Exception as e:
            logger.error(f"DuckDuckGo search falló: {e}")

        # 5. Respaldo Técnico Curado explícitamente etiquetado
        curated = self._get_curated_technical_fallback(query_clean)
        return curated, "curated_technical_backup"

    def search(self, query: str, max_results: int = 30) -> List[Dict[str, Any]]:
        results, _ = self.search_with_meta(query, max_results)
        return results

    def _search_tavily(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        endpoint = "https://api.tavily.com/search"
        payload = {
            "api_key": self.tavily_api_key,
            "query": query,
            "search_depth": "advanced",
            "max_results": min(max_results, 20)
        }
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(endpoint, json=payload)
            resp.raise_for_status()
            data = resp.json()
            results = []
            for r in data.get("results", []):
                link = r.get("url", "").strip()
                if link:
                    results.append({
                        "title": r.get("title", ""),
                        "url": link,
                        "discovered_url": link,
                        "snippet": r.get("content", ""),
                        "domain": urlparse(link).netloc.lower(),
                        "engine": "tavily",
                        "provider_name": "tavily",
                        "url_provenance": "search_provider",
                        "is_curated_backup": False
                    })
            return results

    def _search_bing(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        endpoint = "https://api.bing.microsoft.com/v7.0/search"
        headers = {"Ocp-Apim-Subscription-Key": self.bing_api_key}
        params = {"q": query, "count": min(max_results, 30)}
        with httpx.Client(timeout=8.0) as client:
            resp = client.get(endpoint, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()
            results = []
            for page in data.get("webPages", {}).get("value", []):
                link = page.get("url", "").strip()
                if link:
                    results.append({
                        "title": page.get("name", ""),
                        "url": link,
                        "discovered_url": link,
                        "snippet": page.get("snippet", ""),
                        "domain": urlparse(link).netloc.lower(),
                        "engine": "bing_v7",
                        "provider_name": "bing_v7",
                        "url_provenance": "search_provider",
                        "is_curated_backup": False
                    })
            return results

    def _search_serper(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        endpoint = "https://google.serper.dev/search"
        headers = {
            "X-API-KEY": self.serper_api_key,
            "Content-Type": "application/json"
        }
        payload = {"q": query, "num": min(max_results, 20)}
        with httpx.Client(timeout=8.0) as client:
            resp = client.post(endpoint, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            results = []
            for org in data.get("organic", []):
                link = org.get("link", "").strip()
                if link:
                    results.append({
                        "title": org.get("title", ""),
                        "url": link,
                        "discovered_url": link,
                        "snippet": org.get("snippet", ""),
                        "domain": urlparse(link).netloc.lower(),
                        "engine": "serper_google",
                        "provider_name": "serper_google",
                        "url_provenance": "search_provider",
                        "is_curated_backup": False
                    })
            return results

    def _search_duckduckgo(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        results = []
        try:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                ddg_gen = ddgs.text(query, max_results=max_results)
                for r in ddg_gen:
                    link = r.get("href", "").strip()
                    if link:
                        results.append({
                            "title": r.get("title", ""),
                            "url": link,
                            "discovered_url": link,
                            "snippet": r.get("body", ""),
                            "domain": urlparse(link).netloc.lower(),
                            "engine": "duckduckgo",
                            "provider_name": "duckduckgo",
                            "url_provenance": "search_provider",
                            "is_curated_backup": False
                        })
        except ImportError:
            try:
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                url = f"https://html.duckduckgo.com/html/?q={query}"
                with httpx.Client(timeout=6.0, follow_redirects=True, headers=headers) as client:
                    resp = client.get(url)
                    if resp.status_code == 200:
                        matches = re.findall(r'<a class="result__url"[^>]*href="([^"]+)"', resp.text)
                        for url_match in matches[:max_results]:
                            link = url_match.strip()
                            if link:
                                results.append({
                                    "title": link,
                                    "url": link,
                                    "discovered_url": link,
                                    "snippet": "",
                                    "domain": urlparse(link).netloc.lower(),
                                    "engine": "duckduckgo_html",
                                    "provider_name": "duckduckgo",
                                    "url_provenance": "search_provider",
                                    "is_curated_backup": False
                                })
            except Exception as http_e:
                logger.warning(f"Lightweight DDG HTML search failed: {http_e}")
        except Exception as e:
            logger.warning(f"DDGS error: {e}")
        return results

    def _get_curated_technical_fallback(self, query: str) -> List[Dict[str, Any]]:
        """
        Base de datos de fuentes canónicas de ingeniería explícitamente etiquetadas como respaldo curado.
        """
        q_lower = query.lower()
        if "piping" in q_lower or "isa" in q_lower or "p&id" in q_lower or "instrument" in q_lower:
            return [
                {
                    "title": "P&ID Symbols and Notation Guide - Wermac (Respaldo Canónico)",
                    "url": "https://www.wermac.org/documents/pid_symbols.html",
                    "discovered_url": "https://www.wermac.org/documents/pid_symbols.html",
                    "snippet": "Catálogo completo de simbología P&ID, válvulas de control, líneas de tubería y etiquetas de instrumentación según ISA 5.1.",
                    "domain": "wermac.org",
                    "engine": "curated_technical_backup",
                    "provider_name": "curated_technical_backup",
                    "url_provenance": "curated_backup",
                    "is_curated_backup": True,
                    "source_origin_type": "curated_technical_backup"
                },
                {
                    "title": "Piping and Instrumentation Diagram Standard Symbols - EnggCyclopedia (Respaldo Canónico)",
                    "url": "https://enggcyclopedia.com/piping-instrumentation-diagram-symbols/",
                    "discovered_url": "https://enggcyclopedia.com/piping-instrumentation-diagram-symbols/",
                    "snippet": "Guía técnica de símbolos de diagramas P&ID para equipos mecánicos, bombas, válvulas de proceso e instrumentación.",
                    "domain": "enggcyclopedia.com",
                    "engine": "curated_technical_backup",
                    "provider_name": "curated_technical_backup",
                    "url_provenance": "curated_backup",
                    "is_curated_backup": True,
                    "source_origin_type": "curated_technical_backup"
                },
                {
                    "title": "ISA 5.1 Instrumentation Symbols - Instrumentation Tools (Respaldo Canónico)",
                    "url": "https://instrumentationtools.com/isa-5-1-instrumentation-symbols-p-id/",
                    "discovered_url": "https://instrumentationtools.com/isa-5-1-instrumentation-symbols-p-id/",
                    "snippet": "Explicación de códigos de letras ISA, números de lazo de control y símbolos de elementos primarios de medición.",
                    "domain": "instrumentationtools.com",
                    "engine": "curated_technical_backup",
                    "provider_name": "curated_technical_backup",
                    "url_provenance": "curated_backup",
                    "is_curated_backup": True,
                    "source_origin_type": "curated_technical_backup"
                },
                {
                    "title": "ISA-5.1-2009: Instrumentation Symbols and Identification (Respaldo Canónico)",
                    "url": "https://www.isa.org/standards-and-publications/isa-standards/isa-standards-committees/isa5-1",
                    "discovered_url": "https://www.isa.org/standards-and-publications/isa-standards/isa-standards-committees/isa5-1",
                    "snippet": "Estándar oficial ISA para la identificación y simbología de instrumentos, lazos de control y diagramas P&ID en plantas de proceso.",
                    "domain": "isa.org",
                    "engine": "curated_technical_backup",
                    "provider_name": "curated_technical_backup",
                    "url_provenance": "curated_backup",
                    "is_curated_backup": True,
                    "source_origin_type": "curated_technical_backup"
                }
            ]
        elif "sísmic" in q_lower or "sismic" in q_lower or "nch433" in q_lower or "hormig" in q_lower:
            return [
                {
                    "title": "NCh433.Of1996 Mod.2009 Diseño Sísmico de Edificios - INN Chile (Respaldo Canónico)",
                    "url": "https://www.inn.cl/normas-chilenas-construccion",
                    "discovered_url": "https://www.inn.cl/normas-chilenas-construccion",
                    "snippet": "Norma oficial chilena para el cálculo y diseño sísmico de estructuras y espectros de aceleración.",
                    "domain": "inn.cl",
                    "engine": "curated_technical_backup",
                    "provider_name": "curated_technical_backup",
                    "url_provenance": "curated_backup",
                    "is_curated_backup": True,
                    "source_origin_type": "curated_technical_backup"
                },
                {
                    "title": "Decreto Supremo DS 61 Reglamento Sísmico - MINVU (Respaldo Canónico)",
                    "url": "https://www.minvu.gob.cl/normativa/decreto-supremo-61-diseno-sismico/",
                    "discovered_url": "https://www.minvu.gob.cl/normativa/decreto-supremo-61-diseno-sismico/",
                    "snippet": "Reglamento que fija requisitos de diseño sísmico de edificios y clasifica suelos de fundación.",
                    "domain": "minvu.gob.cl",
                    "engine": "curated_technical_backup",
                    "provider_name": "curated_technical_backup",
                    "url_provenance": "curated_backup",
                    "is_curated_backup": True,
                    "source_origin_type": "curated_technical_backup"
                }
            ]
        return []
