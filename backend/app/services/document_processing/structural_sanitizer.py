"""
Módulo de sanitización estructural y normalización de nodos (DocumentStructuralNode).

Garantiza que ningún nodo estructural (especialmente símbolos de tablas o planos)
propague OCR basura, columnas matriciales binarias o textos concatenados desmedidos a:
- title (VARCHAR 255)
- hierarchy_path (TEXT / VARCHAR 255)
- content_text (TEXT / VARCHAR)

El detalle completo de celdas y trazas OCR se preserva íntegro en structured_payload.
"""

import re
from typing import List, Optional, Any, Dict

# Expresión regular para detectar columnas binarias o de banderas matriciales (ej. "A B C X O 1 0 0", "1 0 0 1 0", "X O - -")
BINARY_MATRIX_REGEX = re.compile(r"^[\s01XOxo\-\.\,\;\|/]+$")

# Prefijos numéricos o de numeración que no aportan semántica al nombre del símbolo
ITEM_PREFIX_REGEX = re.compile(
    r"^(ITEM\s*\d+|N[°o]\s*\d+|N°\s*\d+|[\d\.\-]+)\s*[\:\-\.]?\s*",
    re.IGNORECASE
)

# Palabras técnicas comunes que descartan que un token sea ruido puro
KNOWN_TECHNICAL_TERMS = {
    "mm", "cm", "m", "rf", "dn", "pn", "sch", "nch", "iso", "asme", "astm", "ansi", "api", "din",
    "pqs", "gma", "vlv", "tag", "bar", "psi", "kpa", "clase", "rf", "ff", "sw", "bw", "thd", "npt",
    "bomba", "valvula", "válvula", "filtro", "sensor", "grifo", "extintor", "humo", "alarma"
}


def clean_spacing_and_newlines(text: Optional[str]) -> str:
    """Normaliza saltos de línea y tabulaciones repetitivas a espacios simples."""
    if not text:
        return ""
    # Reemplazar retornos de carro, saltos de línea y tabulaciones
    cleaned = re.sub(r"[\r\n\t]+", " ", str(text))
    # Colapsar espacios múltiples
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def is_binary_or_matrix_garbage(text: Optional[str]) -> bool:
    """
    Detecta si un bloque de texto corresponde a ruido OCR o columnas matriciales
    binarias/banderas sin valor semántico descriptivo (ej. 'A B C X O 1 0 0 1 0', '1 0 0 1', '- - -').
    """
    if not text:
        return True
    cleaned = clean_spacing_and_newlines(text)
    if len(cleaned) == 0:
        return True

    # 1. Secuencia que contiene únicamente caracteres binarios / símbolos de chequeo
    if len(cleaned) >= 2 and BINARY_MATRIX_REGEX.match(cleaned):
        return True

    # 2. Análisis de tokens espaciados (ej. 'A B C X O 1 0 0')
    tokens = cleaned.split(" ")
    if len(tokens) >= 3:
        short_tokens = [t for t in tokens if len(t) <= 2]
        # Si más del 65% de los tokens son letras/números sueltos de 1-2 caracteres
        # y no hay ningún término técnico reconocible de longitud >= 3
        has_tech_word = any(t.lower() in KNOWN_TECHNICAL_TERMS for t in tokens)
        has_real_word = any(len(t) >= 4 and t.isalpha() for t in tokens)
        if (len(short_tokens) / len(tokens) >= 0.65) and not has_tech_word and not has_real_word:
            return True

    # 3. Secuencia de caracteres repetitivos sin estructura (ej. '.....', '------', '|||||')
    if len(cleaned) >= 3 and len(set(cleaned.replace(" ", ""))) <= 2:
        return True

    return False


def sanitize_symbol_title(raw_name: Optional[str], fallback: str = "Símbolo Técnico", max_length: int = 120) -> str:
    """
    Genera un título corto, limpio y representativo para el nodo de símbolo.
    Elimina prefijos de numeración y ruido OCR, limitando la longitud a un máximo seguro (< 150 chars).
    """
    if not raw_name:
        return fallback

    cleaned = clean_spacing_and_newlines(raw_name)
    # Eliminar prefijos tipo "ITEM 1:", "N° 3 -", etc.
    cleaned = ITEM_PREFIX_REGEX.sub("", cleaned).strip()

    # Si el texto restante es basura binaria, usar fallback
    if is_binary_or_matrix_garbage(cleaned):
        return fallback

    # Si contiene múltiples oraciones o cláusulas largas, tomar la primera
    for separator in [". ", "; ", "\n", " - "]:
        if separator in cleaned and len(cleaned) > 50:
            first_part = cleaned.split(separator)[0].strip()
            if len(first_part) >= 3 and not is_binary_or_matrix_garbage(first_part):
                cleaned = first_part
                break

    # Truncar limpiamente respetando palabras si excede max_length
    if len(cleaned) > max_length:
        truncated = cleaned[:max_length]
        last_space = truncated.rfind(" ")
        if last_space > max_length * 0.6:
            cleaned = truncated[:last_space].rstrip(" ,;-.")
        else:
            cleaned = truncated.rstrip(" ,;-.")

    cleaned = cleaned.strip(" ,;:-.")
    return cleaned if len(cleaned) >= 2 else fallback


def sanitize_hierarchy_path(
    base_name: Optional[str],
    chapter_or_section: Optional[str],
    category_slug: str,
    item_identifier: Optional[str],
    max_total_length: int = 180
) -> str:
    """
    Genera un hierarchy_path compacto, estable y semántico.
    Ejemplo: '/doc_plano/cap_seguridad/Simbolos/extintor_pqs'
    """
    def _slugify(segment: Optional[str], max_len: int = 30) -> str:
        if not segment:
            return "general"
        # Limpiar caracteres conflictivos con rutas
        clean = re.sub(r"[^\w\-]+", "_", str(segment).strip()).strip("_")
        if not clean:
            return "general"
        if len(clean) > max_len:
            clean = clean[:max_len].rstrip("_")
        return clean

    doc_part = _slugify(base_name, 25)
    sec_part = _slugify(chapter_or_section, 25)
    cat_part = _slugify(category_slug, 20)
    item_part = _slugify(item_identifier, 35)

    path = f"/{doc_part}/{sec_part}/{cat_part}/{item_part}"
    if len(path) > max_total_length:
        path = path[:max_total_length].rstrip("_/")
    return path


def sanitize_symbol_content_text(
    description: Optional[str],
    title: str,
    technical_function: Optional[str] = None,
    max_length: int = 350
) -> str:
    """
    Genera un content_text breve, limpio y sin repeticiones para el nodo símbolo,
    evitando duplicar el título dentro de la descripción y deduplicando frases.
    """
    clean_title = clean_spacing_and_newlines(title)
    clean_desc = clean_spacing_and_newlines(description)
    clean_fn = clean_spacing_and_newlines(technical_function)

    # Filtrar basura binaria de la descripción
    if is_binary_or_matrix_garbage(clean_desc):
        clean_desc = ""

    # Si clean_desc repite clean_title al inicio, removerlo para no duplicar en tarjeta/modal
    if clean_title and clean_desc:
        norm_title = clean_title.strip(" .")
        if clean_desc.lower().startswith(norm_title.lower()):
            clean_desc = clean_desc[len(norm_title):].lstrip(" .:-–•")

    elements: List[str] = []
    seen_clauses = set()

    for chunk in [clean_desc, clean_fn]:
        if not chunk:
            continue
        for sentence in chunk.split("."):
            s_clean = sentence.strip()
            if not s_clean or len(s_clean) < 3:
                continue
            # Evitar repetir exactamente el título
            if clean_title and s_clean.lower() == clean_title.lower():
                continue
            s_norm = s_clean.lower()
            if s_norm not in seen_clauses:
                seen_clauses.add(s_norm)
                elements.append(s_clean)

    if not elements:
        if clean_desc and clean_desc.lower() != clean_title.lower():
            elements.append(clean_desc)
        elif clean_fn:
            elements.append(clean_fn)
        else:
            return f"Elemento simbólico identificado: {clean_title}."

    result = ". ".join(elements) + "."
    result = re.sub(r"\.+", ".", result)
    result = clean_spacing_and_newlines(result)

    if len(result) > max_length:
        avail = max(0, max_length - 3)
        truncated = result[:avail].rsplit(" ", 1)[0].rstrip(" ,;-.")
        result = (truncated if truncated else result[:avail]) + "..."

    return result
