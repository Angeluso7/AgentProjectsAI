import re
import logging
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urljoin, urlparse
import urllib.robotparser
from app.services.discovery.page_content_validator import PageContentValidator
from app.services.discovery.term_coverage_matcher import TermCoverageMatcher

logger = logging.getLogger(__name__)

class SubpageCrawler:
    """
    Explorador Seguro, Limitado y Trazable de Subpáginas de Contenido Técnico:
    - Búsqueda exclusiva en enlaces internos reales (<a href="...">) del mismo dominio.
    - Respeta robots.txt y user-agent identificado.
    - Limita exploración a profundidad 1 y máximo 10-15 enlaces relevantes.
    - Ordena enlaces candidatos usando TermCoverageMatcher antes de validar su existencia.
    - Cero invención o suposición de rutas sintéticas.
    """

    INDEX_PATH_PATTERNS = [
        r"/$", r"/documents/?$", r"/standards/?$", r"/category/",
        r"/index\.(html?|php)$", r"/publicaciones/?$", r"/normas/?$",
        r"/standards-committees/?", r"/resources/?$", r"/guides/?$"
    ]

    _ROBOTS_CACHE: Dict[str, urllib.robotparser.RobotFileParser] = {}

    @classmethod
    def _is_allowed_by_robots(cls, url: str, user_agent: str = "PlanReviewAiBot") -> bool:
        """Verifica si la URL está permitida según robots.txt del dominio."""
        try:
            parsed = urlparse(url)
            base_robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
            if base_robots_url not in cls._ROBOTS_CACHE:
                rp = urllib.robotparser.RobotFileParser()
                rp.set_url(base_robots_url)
                try:
                    rp.read()
                except Exception:
                    # Si no hay robots.txt accesible, asumimos permitido
                    pass
                cls._ROBOTS_CACHE[base_robots_url] = rp
            else:
                rp = cls._ROBOTS_CACHE[base_robots_url]
            return rp.can_fetch(user_agent, url)
        except Exception:
            return True

    @classmethod
    def explore_subpages(
        cls,
        initial_url: str,
        html_content: str,
        search_prompt: str,
        max_subpages_to_check: int = 10
    ) -> Dict[str, Any]:
        """
        Analiza si la página actual contiene subpáginas con contenido técnico más profundo y relevante.
        Retorna metadatos completos de trazabilidad y procedencia.
        """
        parsed_initial = urlparse(initial_url)
        domain = parsed_initial.netloc.lower()

        # Determinar si la URL inicial califica como índice / landing
        is_index = any(re.search(p, parsed_initial.path.lower()) for p in cls.INDEX_PATH_PATTERNS)
        query_struct = TermCoverageMatcher.extract_query_structure(search_prompt)

        traceability = {
            "initial_url": initial_url,
            "resolved_url": initial_url,
            "canonical_url": None,
            "content_subpage_url": initial_url,
            "url_provenance": "search_provider",
            "selection_reason": "URL inicial contiene contenido directo verificado",
            "match_bucket": "MEDIUM_MATCH",
            "crawler_depth": 0,
            "robots_allowed": True,
            "validation_result": True,
            "discard_reason": None
        }

        if not html_content:
            return traceability

        # Extraer canonical URL de la página inicial
        canonical_match = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']', html_content, re.IGNORECASE)
        if canonical_match:
            traceability["canonical_url"] = canonical_match.group(1).strip()

        # Si no es un índice y ya tiene contenido técnico largo y específico, mantener URL inicial
        if not is_index and len(html_content) > 3500:
            return traceability

        # Extraer enlaces internos reales en el HTML
        links = re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html_content, re.IGNORECASE | re.DOTALL)
        candidate_subpages: List[Tuple[float, str, str, Dict[str, Any]]] = []

        seen_hrefs = set()

        for href, anchor_html in links:
            clean_href = href.split("#")[0].split("?")[0].strip()
            if not clean_href or clean_href.startswith("javascript:") or clean_href.startswith("mailto:") or clean_href.startswith("tel:"):
                continue

            full_subpage_url = urljoin(initial_url, clean_href)
            parsed_sub = urlparse(full_subpage_url)

            # Debe ser estrictamente del mismo dominio
            if parsed_sub.netloc.lower() != domain:
                continue

            # No evaluar la misma URL
            if full_subpage_url.rstrip('/') == initial_url.rstrip('/'):
                continue

            if full_subpage_url in seen_hrefs:
                continue
            seen_hrefs.add(full_subpage_url)

            clean_anchor = re.sub(r"<[^>]+>", " ", anchor_html)
            clean_anchor = re.sub(r"\s+", " ", clean_anchor).strip()

            # Evaluar coincidencia de términos del enlace con TermCoverageMatcher
            eval_res = TermCoverageMatcher.evaluate_candidate_coverage(
                query_struct=query_struct,
                url=full_subpage_url,
                title="",
                snippet=clean_anchor,
                anchor_text=clean_anchor
            )

            score = eval_res["coverage_score"]
            if score >= 10.0 or eval_res["match_bucket"] != "REJECTED":
                candidate_subpages.append((score, full_subpage_url, clean_anchor, eval_res))

        # Ordenar subpáginas por score de cobertura de mayor a menor
        candidate_subpages.sort(key=lambda x: x[0], reverse=True)

        # Probar hasta `max_subpages_to_check` enlaces reales respetando robots.txt
        checked_count = 0
        for score, sub_url, anchor, eval_res in candidate_subpages:
            if checked_count >= max_subpages_to_check:
                break
            checked_count += 1

            if not cls._is_allowed_by_robots(sub_url):
                logger.info(f"Subpágina {sub_url} bloqueada por robots.txt, omitiendo...")
                continue

            is_valid, discard_reason, meta = PageContentValidator.validate_url(sub_url, timeout=4.5)
            if is_valid:
                # Si la subpágina tiene contenido válido, evaluamos su cobertura completa
                sub_clean_text = meta.get("clean_text_sample", "")
                sub_title = meta.get("title", anchor)
                full_eval = TermCoverageMatcher.evaluate_candidate_coverage(
                    query_struct=query_struct,
                    url=meta.get("final_url", sub_url),
                    title=sub_title,
                    snippet=anchor,
                    clean_text=sub_clean_text
                )

                traceability["content_subpage_url"] = meta.get("final_url", sub_url)
                traceability["resolved_url"] = meta.get("final_url", sub_url)
                traceability["url_provenance"] = "internal_link"
                traceability["crawler_depth"] = 1
                traceability["robots_allowed"] = True
                traceability["validation_result"] = True
                traceability["match_bucket"] = full_eval["match_bucket"]

                if meta.get("canonical_url"):
                    traceability["canonical_url"] = meta["canonical_url"]

                anchor_snippet = anchor[:60] if anchor else "enlace interno relevante"
                traceability["selection_reason"] = (
                    f"Subpágina interna especializada descubierta vía '{anchor_snippet}' "
                    f"({meta.get('useful_length', 0)} caracteres de contenido técnico útil, bucket: {full_eval['match_bucket']})."
                )
                return traceability

        return traceability
