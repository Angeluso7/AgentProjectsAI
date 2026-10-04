import re
import logging
from typing import Dict, Any, Optional, Tuple
from urllib.parse import urlparse
import httpx

logger = logging.getLogger(__name__)

class PageContentValidator:
    """
    Validador Multicriterio de Páginas Activas y Contenido Técnico Útil:
    1. Código de estado HTTP (200 OK obligatorio).
    2. URL final tras redirecciones (detección de redirects a login, error o búsquedas vacías).
    3. Extracción de canonical URL (<link rel="canonical">).
    4. Limpieza de HTML y cálculo de longitud de texto visible útil.
    5. Detección de Soft-404, 'Something's wrong here...', CAPTCHA y plantillas de error en título y contenido.
    6. Detección de Login Walls obligatorios y Paywalls.
    7. Flexibilidad controlada para páginas breves pero con contenido técnico denso (tablas, diagramas, normas, PDFs).
    """

    SOFT_404_PATTERNS = [
        r"\bpage\s+not\s+found\b",
        r"\bp[áa]gina\s+no\s+encontrada\b",
        r"\b404\s+not\s+found\b",
        r"\berror\s+404\b",
        r"\bdocumento\s+no\s+encontrado\b",
        r"\brecurso\s+no\s+disponible\b",
        r"\bthe\s+requested\s+url\s+was\s+not\s+found\b",
        r"\bcontenido\s+no\s+disponible\b",
        r"\bp[áa]gina\s+inexistente\b",
        r"\bno\s+se\s+pudo\s+encontrar\s+la\s+p[áa]gina\b",
        r"\bsomething['’]?s\s+wrong\s+here\b",
        r"\bsomething\s+went\s+wrong\b",
        r"\ban\s+error\s+occurred\b",
        r"\bha\s+ocurrido\s+un\s+error\b",
        r"\b0\s+results?\s+found\b",
        r"\bno\s+se\s+encontraron\s+resultados\b",
        r"\bno\s+search\s+results\b"
    ]

    LOGIN_WALL_PATTERNS = [
        r"\biniciar\s+sesi[óo]n\s+para\s+continuar\b",
        r"\blogin\s+required\b",
        r"\bsign\s+in\s+to\s+view\b",
        r"\bacceso\s+exclusivo\s+para\s+suscriptores\b",
        r"\bsuscr[íi]bete\s+para\s+leer\b",
        r"\benter\s+your\s+credentials\b",
        r"\bplease\s+log\s+in\s+to\s+access\b",
        r"\bautenticaci[óo]n\s+requerida\b",
        r"\baccess\s+denied\b",
        r"\bacceso\s+denegado\b",
        r"\bverify\s+you\s+are\s+human\b",
        r"\battention\s+required\s*\|\s*cloudflare\b"
    ]

    DISALLOWED_REDIRECT_PATHS = [
        r"/login", r"/auth", r"/signin", r"/iniciar-sesion",
        r"/404", r"/error", r"/not-found", r"/access-denied"
    ]

    @classmethod
    def validate_url(
        cls,
        url: str,
        timeout: float = 6.0,
        headers: Optional[Dict[str, str]] = None
    ) -> Tuple[bool, Optional[str], Dict[str, Any]]:
        """
        Valida exhaustivamente una URL externa aplicando prevención de SSRF y análisis semántico.
        Retorna (es_valido, motivo_descarte_si_invalido, metadatos_extraidos).
        """
        from app.services.discovery.safe_url_validator import SafeUrlValidator

        # 1. Validación de seguridad SSRF y petición HTTP controlada paso a paso
        is_fetch_ok, fetch_err, fetch_data = SafeUrlValidator.safe_fetch_html(url, timeout=timeout, headers=headers)
        if not is_fetch_ok:
            return False, fetch_err, fetch_data

        final_url = fetch_data.get("resolved_url", url)
        status_code = fetch_data.get("status_code", 200)
        raw_html = fetch_data.get("raw_html", "")

        # 2. Validación de redirección a páginas de error o login
        parsed_final = urlparse(final_url)
        for dis in cls.DISALLOWED_REDIRECT_PATHS:
            if re.search(dis, parsed_final.path.lower()):
                return False, "redirected_to_login_or_error", {
                    "status_code": status_code,
                    "final_url": final_url,
                    "resolved_url": final_url
                }

        if not raw_html or len(raw_html.strip()) < 100:
            return False, "empty_http_response", {
                "status_code": status_code,
                "final_url": final_url,
                "resolved_url": final_url
            }

        # 3. Extracción de Título y Canonical URL
        title_match = re.search(r"<title[^>]*>(.*?)</title>", raw_html, re.IGNORECASE | re.DOTALL)
        extracted_title = title_match.group(1).strip() if title_match else ""
        extracted_title = re.sub(r"\s+", " ", extracted_title)

        canonical_match = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']', raw_html, re.IGNORECASE)
        if not canonical_match:
            canonical_match = re.search(r'<link[^>]+href=["\']([^"\']+)["\'][^>]+rel=["\']canonical["\']', raw_html, re.IGNORECASE)
        canonical_url = canonical_match.group(1).strip() if canonical_match else None

        # 4. Limpieza de HTML para evaluar texto visible útil
        cleaned_text = cls._extract_visible_text(raw_html)
        clean_len = len(cleaned_text)

        # Detección de elementos técnicos estructurados (tablas, imágenes técnicas, PDFs, normas)
        has_technical_elements = bool(
            re.search(r"<table|<img|\.pdf|norma|standard|diagram|simbolog|symbol|p&id|valvula|valve", raw_html, re.IGNORECASE)
        )

        if clean_len < 150 and not has_technical_elements:
            return False, f"insufficient_useful_content_length_{clean_len}", {
                "status_code": status_code,
                "final_url": final_url,
                "resolved_url": final_url,
                "useful_length": clean_len
            }

        # 5. Detección de Soft-404 en título y cuerpo
        title_lower = extracted_title.lower()
        text_lower = cleaned_text[:3000].lower() # Evaluar encabezado y primeros párrafos

        for pat in cls.SOFT_404_PATTERNS:
            if re.search(pat, title_lower) or re.search(pat, text_lower):
                return False, "soft_404_detected", {
                    "status_code": status_code,
                    "final_url": final_url,
                    "resolved_url": final_url,
                    "matched_pattern": pat
                }

        # 6. Detección de Login Wall obligatorio o Paywall
        for lpat in cls.LOGIN_WALL_PATTERNS:
            if re.search(lpat, text_lower):
                return False, "login_wall_or_paywall_detected", {
                    "status_code": status_code,
                    "final_url": final_url,
                    "resolved_url": final_url,
                    "matched_pattern": lpat
                }

        # Página válida y verificada
        return True, None, {
            "status_code": status_code,
            "final_url": final_url,
            "resolved_url": final_url,
            "canonical_url": canonical_url,
            "title": extracted_title,
            "useful_length": clean_len,
            "clean_text_sample": cleaned_text[:1500],
            "raw_html": raw_html
        }

    @classmethod
    def _extract_visible_text(cls, html_content: str) -> str:
        """
        Elimina etiquetas de scripting, estilos, menús de navegación, encabezados/pies
        y retorna el texto limpio y legible.
        """
        if not html_content:
            return ""

        # 1. Eliminar scripts, styles, noscript, svg, audio, video
        clean = re.sub(r"<(script|style|noscript|svg|video|audio)[^>]*>.*?</\1>", " ", html_content, flags=re.IGNORECASE | re.DOTALL)

        # 2. Eliminar nav, footer, header repetitivos
        clean = re.sub(r"<(nav|footer|header|form)[^>]*>.*?</\1>", " ", clean, flags=re.IGNORECASE | re.DOTALL)

        # 3. Reemplazar tags de bloque por espacios
        clean = re.sub(r"<(div|p|h[1-6]|li|tr|td|th|br|hr)[^>]*>", " ", clean, flags=re.IGNORECASE)

        # 4. Eliminar el resto de tags HTML
        clean = re.sub(r"<[^>]+>", " ", clean)

        # 5. Colapsar espacios en blanco
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean
