import re
from typing import Tuple

class LanguageDetector:
    """
    Detector de Idioma y Asignador de Ponderación para Ranking:
    - Español ('es'): Máxima prioridad (+12 puntos de score).
    - Inglés ('en'): Alta prioridad técnica (+6 puntos de score).
    - Otros idiomas ('other'): Neutro (+0 puntos de score).
    
    Principio fundamental: La preferencia por idioma es para ranking y desempate, NO para bloqueo.
    """

    SPANISH_STOPWORDS = {
        "de", "la", "el", "en", "y", "a", "los", "se", "del", "las", "un", "por", "con",
        "no", "una", "su", "para", "es", "al", "lo", "como", "más", "o", "pero", "sus",
        "le", "ya", "o", "este", "sí", "porque", "esta", "son", "entre", "está", "cuando",
        "muy", "sin", "sobre", "ser", "tiene", "también", "me", "hasta", "hay", "donde",
        "cañerías", "válvula", "válvulas", "instrumentación", "norma", "símbolos", "simbología"
    }

    ENGLISH_STOPWORDS = {
        "the", "of", "and", "a", "to", "in", "is", "you", "that", "it", "he", "was", "for",
        "on", "are", "as", "with", "his", "they", "i", "at", "be", "this", "have", "from",
        "or", "one", "had", "by", "word", "but", "not", "what", "all", "were", "we", "when",
        "your", "can", "said", "there", "use", "an", "each", "which", "she", "do", "how",
        "piping", "valve", "valves", "instrumentation", "symbols", "diagram", "diagrams"
    }

    @classmethod
    def detect_language(cls, text: str, html_header: str = "") -> Tuple[str, float]:
        """
        Detecta el idioma de un texto y asigna un puntaje de boost para ranking.
        Retorna (código_idioma, score_boost).
        """
        if not text:
            return "other", 0.0

        # 1. Chequeo de encabezado HTML (lang="es" o lang="en")
        if html_header:
            html_lower = html_header.lower()
            if 'lang="es"' in html_lower or "lang='es'" in html_lower or 'content="es"' in html_lower or 'lang="es-cl"' in html_lower or 'lang="es-es"' in html_lower:
                return "es", 12.0
            if 'lang="en"' in html_lower or "lang='en'" in html_lower or 'content="en"' in html_lower or 'lang="en-us"' in html_lower or 'lang="en-gb"' in html_lower:
                return "en", 6.0

        # 2. Análisis de frecuencias léxicas de palabras funcionales
        words = re.findall(r"\b[a-záéíóúñü]+\b", text.lower())
        if not words:
            return "other", 0.0

        es_count = sum(1 for w in words if w in cls.SPANISH_STOPWORDS)
        en_count = sum(1 for w in words if w in cls.ENGLISH_STOPWORDS)

        total_words = len(words)
        es_ratio = es_count / total_words if total_words > 0 else 0
        en_ratio = en_count / total_words if total_words > 0 else 0

        if es_count > en_count and es_count >= 3:
            return "es", 12.0
        elif en_count > es_count and en_count >= 3:
            return "en", 6.0
        elif es_ratio > 0.05:
            return "es", 12.0
        elif en_ratio > 0.05:
            return "en", 6.0

        return "other", 0.0
