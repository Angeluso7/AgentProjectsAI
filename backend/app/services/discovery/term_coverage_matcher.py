import re
import unicodedata
from typing import Dict, Any, List, Set, Tuple, Optional

class TermCoverageMatcher:
    """
    Motor de Matching por Cobertura Real de Términos y Ponderación por Capas:
    1. Normalización semántica (sin acentos, minúsculas, stopwords filtradas).
    2. Identificación de términos compuestos técnicos indivisibles.
    3. Clasificación de términos críticos vs secundarios con grupos de equivalencias ES/EN.
    4. Puntuación por capas: URL/slug, title, snippet, anchor text y contenido visible.
    5. Asignación de Buckets: FULL_MATCH, HIGH_MATCH, MEDIUM_MATCH, LOW_MATCH, REJECTED.
    """

    GENERIC_STOPWORDS = {
        "de", "la", "el", "en", "y", "a", "los", "se", "del", "las", "un", "por", "con",
        "no", "una", "su", "para", "es", "al", "lo", "como", "mas", "o", "pero", "sus",
        "le", "ya", "este", "esta", "son", "entre", "esta", "cuando", "muy", "sin", "sobre",
        "ser", "tiene", "tambien", "me", "hasta", "hay", "donde", "que", "the", "of", "and",
        "to", "in", "is", "for", "on", "are", "as", "with", "at", "by", "this", "from",
        "an", "be", "or", "which", "it", "how", "what", "all", "were", "we", "when", "your"
    }

    COMPOUND_TECHNICAL_TERMS = [
        ("isa s5.1", ["isa s5.1", "isa-s5.1", "isa 5.1", "isa-5.1", "isa 5 1", "isa5-1", "isa5.1", "s5.1"]),
        ("p&id", ["p&id", "p & id", "p-id", "pid", "p&di", "piping and instrumentation diagram"]),
        ("instrumentation symbols", ["instrumentation symbols", "instrument symbols", "simbologia de instrumentacion", "simbolos de instrumentacion"]),
        ("piping symbols", ["piping symbols", "simbologia piping", "simbologia de cañerias", "simbologia de tuberias", "simbolos de cañerias"]),
        ("control valve", ["control valve", "control valves", "valvula de control", "valvulas de control"]),
        ("gate valve", ["gate valve", "gate valves", "valvula de compuerta", "valvulas de compuerta"]),
        ("line list", ["line list", "lista de lineas", "listado de lineas"]),
        ("nch 433", ["nch 433", "nch433", "nch-433"]),
        ("oguc", ["oguc", "ordenanza general de urbanismo y construcciones"])
    ]

    # Grupos de equivalencias técnicas entre español e inglés
    EQUIVALENCE_GROUPS = [
        {"simbologia", "simbolos", "simbolo", "symbols", "symbol", "symbology", "notation"},
        {"piping", "caneria", "canerias", "tuberia", "tuberias", "pipe", "pipes"},
        {"instrumentacion", "instrumentos", "instrumento", "instrumentation", "instruments", "instrument"},
        {"valvula", "valvulas", "valve", "valves"},
        {"diagrama", "diagramas", "diagram", "diagrams", "drawing", "drawings", "plano", "planos"},
        {"norma", "normas", "standard", "standards", "spec", "specification"},
        {"sismo", "sismico", "sismica", "seismic", "earthquake"},
        {"fuego", "incendio", "fire", "fireproof"},
        {"evacuacion", "escape", "evacuation", "egress"}
    ]

    @classmethod
    def normalize_text(cls, text: str) -> str:
        """Normaliza texto eliminando acentos, caracteres especiales innecesarios y convirtiendo a minúsculas."""
        if not text:
            return ""
        # Transliterar acentos
        nfkd = unicodedata.normalize('NFKD', text)
        clean = "".join([c for c in nfkd if not unicodedata.combining(c)])
        clean = clean.lower()
        # Normalizar caracteres especiales comunes
        clean = clean.replace('&', ' & ').replace('-', ' ').replace('_', ' ').replace('/', ' ')
        clean = re.sub(r"[^\w\s\.\&]", " ", clean)
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean

    @classmethod
    def extract_query_structure(cls, query: str) -> Dict[str, Any]:
        """
        Extrae tokens, términos compuestos y clasifica términos críticos vs secundarios.
        """
        norm_query = cls.normalize_text(query)
        detected_compounds: List[str] = []
        
        # 1. Detección de términos compuestos
        for canonical, variants in cls.COMPOUND_TECHNICAL_TERMS:
            for var in variants:
                norm_var = cls.normalize_text(var)
                if norm_var in norm_query:
                    detected_compounds.append(canonical)
                    break

        # 2. Tokenización y filtrado de stopwords
        raw_tokens = [t for t in norm_query.split() if len(t) > 1 and t not in cls.GENERIC_STOPWORDS]
        
        # 3. Categorización de términos críticos
        critical_terms: Set[str] = set()
        secondary_terms: Set[str] = set()

        for token in raw_tokens:
            is_critical = False
            # Si contiene dígitos o códigos técnicos (e.g. s5.1, 433, isa, oguc, p&id)
            if any(c.isdigit() for c in token) or token in ["isa", "pid", "p&id", "oguc", "sec", "inn", "ridaa", "nch"]:
                is_critical = True
            # Si es término técnico nuclear de disciplina (piping, valve, symbols, etc.)
            elif token in ["piping", "simbologia", "simbolos", "symbols", "instrumentacion", "instrumentation", "valvula", "valves"]:
                is_critical = True

            if is_critical:
                critical_terms.add(token)
            else:
                secondary_terms.add(token)

        # Añadir compuestos identificados a los términos críticos
        for comp in detected_compounds:
            for comp_tok in comp.split():
                if comp_tok not in cls.GENERIC_STOPWORDS:
                    critical_terms.add(comp_tok)

        return {
            "normalized_query": norm_query,
            "tokens": raw_tokens,
            "compounds": detected_compounds,
            "critical_terms": list(critical_terms),
            "secondary_terms": list(secondary_terms)
        }

    @classmethod
    def _expand_term_with_equivalences(cls, term: str) -> Set[str]:
        """Retorna el conjunto de variantes y equivalencias multilingües de un término."""
        variants = {term}
        norm_term = cls.normalize_text(term)
        variants.add(norm_term)

        for group in cls.EQUIVALENCE_GROUPS:
            if norm_term in group or any(norm_term == cls.normalize_text(g) for g in group):
                variants.update(group)
                break

        return variants

    @classmethod
    def evaluate_candidate_coverage(
        cls,
        query_struct: Dict[str, Any],
        url: str,
        title: str,
        snippet: str,
        clean_text: str = "",
        anchor_text: str = ""
    ) -> Dict[str, Any]:
        """
        Calcula la cobertura por capas y asigna el Bucket de coincidencia real.
        """
        norm_url = cls.normalize_text(url)
        norm_title = cls.normalize_text(title)
        norm_snippet = cls.normalize_text(snippet)
        norm_anchor = cls.normalize_text(anchor_text)
        norm_content = cls.normalize_text(clean_text[:4000]) if clean_text else ""

        full_text_corpus = f"{norm_url} {norm_title} {norm_snippet} {norm_anchor} {norm_content}"

        critical_terms: List[str] = query_struct.get("critical_terms", [])
        secondary_terms: List[str] = query_struct.get("secondary_terms", [])
        all_terms = list(set(critical_terms + secondary_terms))

        matched_critical: Set[str] = set()
        missing_critical: Set[str] = set()
        matched_secondary: Set[str] = set()
        matched_terms: Set[str] = set()

        # 1. Coincidencia de términos críticos con equivalencias
        for term in critical_terms:
            equivs = cls._expand_term_with_equivalences(term)
            if any(re.search(r"\b" + re.escape(eq) + r"\b", full_text_corpus) for eq in equivs):
                matched_critical.add(term)
                matched_terms.add(term)
            else:
                missing_critical.add(term)

        # 2. Coincidencia de términos secundarios con equivalencias
        for term in secondary_terms:
            equivs = cls._expand_term_with_equivalences(term)
            if any(re.search(r"\b" + re.escape(eq) + r"\b", full_text_corpus) for eq in equivs):
                matched_secondary.add(term)
                matched_terms.add(term)

        # 3. Coincidencia de frases compuestas exactas
        compounds = query_struct.get("compounds", [])
        exact_phrase_matches: List[str] = []
        for comp in compounds:
            variants = []
            for canonical, vars_list in cls.COMPOUND_TECHNICAL_TERMS:
                if canonical == comp:
                    variants = vars_list
                    break
            if any(cls.normalize_text(v) in full_text_corpus for v in variants):
                exact_phrase_matches.append(comp)

        # 4. Cálculo de porcentajes de cobertura
        crit_count = len(critical_terms)
        tot_count = len(all_terms)

        critical_coverage_pct = (len(matched_critical) / crit_count) if crit_count > 0 else 1.0
        total_coverage_pct = (len(matched_terms) / tot_count) if tot_count > 0 else 1.0

        # 5. Puntuación por capas
        url_matches = sum(1 for t in all_terms if any(eq in norm_url for eq in cls._expand_term_with_equivalences(t)))
        title_matches = sum(1 for t in all_terms if any(eq in norm_title for eq in cls._expand_term_with_equivalences(t)))
        snippet_matches = sum(1 for t in all_terms if any(eq in norm_snippet for eq in cls._expand_term_with_equivalences(t)))
        content_matches = sum(1 for t in all_terms if any(eq in norm_content for eq in cls._expand_term_with_equivalences(t)))

        # Score ponderado (0 - 100)
        base_score = (critical_coverage_pct * 60.0) + (total_coverage_pct * 25.0)
        if exact_phrase_matches:
            base_score += 15.0 * len(exact_phrase_matches)
        if title_matches > 0:
            base_score += min(title_matches * 3.0, 10.0)
        if url_matches > 0:
            base_score += min(url_matches * 2.0, 6.0)

        coverage_score = round(min(base_score, 100.0), 1)

        # 6. Asignación de Buckets
        if (critical_coverage_pct >= 0.75 and total_coverage_pct >= 0.75) or (len(exact_phrase_matches) > 0 and critical_coverage_pct >= 0.5):
            match_bucket = "FULL_MATCH"
        elif critical_coverage_pct >= 0.5 or total_coverage_pct >= 0.6:
            match_bucket = "HIGH_MATCH"
        elif critical_coverage_pct >= 0.25 or total_coverage_pct >= 0.35:
            match_bucket = "MEDIUM_MATCH"
        elif total_coverage_pct >= 0.15:
            match_bucket = "LOW_MATCH"
        else:
            match_bucket = "REJECTED"

        return {
            "coverage_score": coverage_score,
            "match_bucket": match_bucket,
            "critical_coverage_pct": round(critical_coverage_pct, 2),
            "total_coverage_pct": round(total_coverage_pct, 2),
            "exact_phrase_matches": exact_phrase_matches,
            "matched_terms": list(matched_terms),
            "missing_critical_terms": list(missing_critical),
            "layer_stats": {
                "url_matches": url_matches,
                "title_matches": title_matches,
                "snippet_matches": snippet_matches,
                "content_matches": content_matches
            }
        }
