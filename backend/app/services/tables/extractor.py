import os
import re
import uuid
import math
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from collections import Counter, defaultdict
from PIL import Image

from app.core.settings import settings
from app.core.logging import logger
from app.services.extraction.candidate_enrichment_service import TECHNICAL_KNOWLEDGE_CATALOG
from app.services.symbols.geometric_validator import GeometricEvidenceValidator, CellGeometricEvaluation
from app.services.document_processing.structural_sanitizer import (
    clean_spacing_and_newlines,
    is_binary_or_matrix_garbage,
    sanitize_symbol_title,
    sanitize_symbol_content_text
)

# Factor de conversión estándar PDF point a milímetro: 1 pt = 25.4 / 72 mm
PT_TO_MM = 25.4 / 72.0

STD_REGEX = re.compile(
    r"(ASME\s+[A-Z0-9\.]+|API\s+[0-9]+|ISA\s+[0-9\.]+|OGUC\s+(?:Art\.?\s*)?[0-9\.]+|"
    r"NCh\s+[0-9\.\/]+|ISO\s+[0-9]+|NFPA\s+[0-9]+|RIC\s+N?[°o]?\s*[0-9]+|DIN\s+[0-9]+|ASTM\s+[A-Z0-9]+)",
    re.IGNORECASE
)
TAG_REGEX = re.compile(
    r"\b([A-Z]{1,4}-\d{1,4}[A-Z]?|V-\d+|FCV-\d+|TCV-\d+|PCV-\d+|PT-\d+|TT-\d+|FT-\d+|LT-\d+|PQS-\d+|F-\d{2,3}|P-\d{2,3})\b",
    re.IGNORECASE
)


@dataclass
class TableOrientationResult:
    """Resultado de la detección automática del sentido de lectura y organización de una tabla."""
    orientation: str                     # "row_major", "col_major", "mixed", "undetermined", "none"
    orientation_confidence: float        # 0.0 a 1.0
    orientation_reason: str              # Explicación técnica de la decisión


@dataclass
class ExtractedSymbolCandidateDTO:
    """Candidato a símbolo extraído desde una celda tabular o elemento gráfico."""
    id: str
    symbol_name: str
    canonical_symbol_family: str
    standard_reference: Optional[str] = None
    discipline: str = "piping"
    category: str = "valvulas"
    source_render_mode: str = "vector"          # vector, raster, mixed
    layout_context: str = "inside_table"        # inside_table, semi_structured_legend, free_layout, manual_crop
    context_association_mode: str = "row_band"  # row_band, lateral_band, caption_band, manual_assignment
    bbox_normalized: List[float] = field(default_factory=list)
    estimated_physical_size_mm: Dict[str, Any] = field(default_factory=dict)
    crop_image_path: Optional[str] = None
    technical_function: Optional[str] = None
    aliases: List[str] = field(default_factory=list)
    confidence_score: float = 0.88
    human_validation_notes: Optional[str] = None
    visual_variant_group_id: Optional[str] = None
    # Linaje estructural tabla-fila-columna
    source_table_id: Optional[str] = None
    row_index: Optional[int] = None
    col_index: Optional[int] = None
    cell_bbox: Optional[List[float]] = None
    inner_drawing_bbox: Optional[List[float]] = None
    symbol_crop_bbox: Optional[List[float]] = None
    crop_margin_mm: float = 3.0
    row_span: int = 1
    col_span: int = 1
    graphic_classification: str = "symbol"       # symbol, figure, table_graphic, not_symbol, requires_human_review
    row_bbox: Optional[List[float]] = None
    tag_or_code: Optional[str] = None
    symbol_description: Optional[str] = None
    needs_visual_crop: bool = False
    crop_error_reason: Optional[str] = None
    reading_orientation: str = "row_major"       # row_major, col_major, mixed, undetermined
    orientation_confidence: float = 1.0
    orientation_reason: str = ""
    requires_human_review: bool = False
    # Auditoría geométrica obligatoria
    geometric_evidence: bool = True
    geometric_confidence: float = 0.0
    evidence_sources: List[str] = field(default_factory=list)
    shape_features: Dict[str, Any] = field(default_factory=dict)
    text_mask_overlap_ratio: float = 0.0
    rejection_reason: Optional[str] = None
    # Metadatos de grilla física y tabla
    grid_source: str = "vector"                  # vector, raster, logical_alignment
    grid_confidence: float = 1.0
    physical_grid_detected: bool = True
    x_boundaries: List[float] = field(default_factory=list)
    y_boundaries: List[float] = field(default_factory=list)
    table_bbox: Optional[List[float]] = None
    content_class: str = "symbol_only"           # symbol_only, mixed, figure, table_graphic, text_only, empty, not_symbol
    boundary_evidence: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    border_coverage_ratio: float = 0.0


@dataclass
class ExtractedCellDTO:
    """Celda individual descompuesta con coordenadas matriciales exactas tipo hoja de cálculo."""
    row_index: int
    column_index: int
    text: str
    normalized_text: str
    confidence: float
    bbox: List[float]
    bbox_normalized: List[float]
    is_header: bool
    source_text_refs: List[str]
    cell_type: str = "text_only"                 # text_only, symbol_only, mixed, empty, figure
    symbol_id: Optional[str] = None
    has_symbol: bool = False
    symbol_name: Optional[str] = None
    crop_image_path: Optional[str] = None
    inner_drawing_bbox: Optional[List[float]] = None
    symbol_crop_bbox: Optional[List[float]] = None
    crop_margin_mm: float = 3.0
    row_span: int = 1
    col_span: int = 1
    graphic_classification: str = "none"         # symbol, figure, table_graphic, not_symbol, requires_human_review, none
    content_class: str = "empty"                 # empty, text_only, symbol_only, mixed, figure, table_graphic, not_symbol
    needs_visual_crop: bool = False
    crop_error_reason: Optional[str] = None
    # Auditoría geométrica obligatoria
    geometric_evidence: bool = False
    geometric_confidence: float = 0.0
    evidence_sources: List[str] = field(default_factory=list)
    shape_features: Dict[str, Any] = field(default_factory=dict)
    text_mask_overlap_ratio: float = 0.0
    rejection_reason: Optional[str] = None
    boundary_evidence: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    border_coverage_ratio: float = 0.0


@dataclass
class ExtractedTableDTO:
    """Tabla completa descompuesta con estructura matricial e indicadores de simbología."""
    title: str
    bbox: List[float]
    bbox_normalized: List[float]
    row_count: int
    column_count: int
    confidence: float
    extraction_status: str
    headers: List[str]
    cells: List[ExtractedCellDTO]
    raw_structure: Dict[str, Any]
    extracted_symbols: List[ExtractedSymbolCandidateDTO] = field(default_factory=list)
    has_symbols: bool = False
    reading_orientation: str = "none"            # row_major, col_major, mixed, undetermined, none
    orientation_confidence: float = 1.0
    orientation_reason: str = "Tabla documental"
    x_boundaries: List[float] = field(default_factory=list)
    y_boundaries: List[float] = field(default_factory=list)
    grid_source: str = "vector"                  # vector, raster, logical_alignment
    grid_confidence: float = 1.0
    physical_grid_detected: bool = True
    table_bbox: List[float] = field(default_factory=list)


def detect_table_reading_orientation(
    cells: List[ExtractedCellDTO],
    num_rows: int,
    num_cols: int
) -> TableOrientationResult:
    """
    Detecta el sentido dominante de organización y lectura de una tabla con símbolos:
    - row_major: Símbolos organizados en una columna (ej. Col 0 o 1) con información técnica a la derecha por filas.
    - col_major: Símbolos organizados en una fila (ej. Fila 0 o 1) con información técnica debajo por columnas.
    - mixed: Símbolos distribuidos en múltiples filas y columnas o con encabezados superiores y descripciones laterales concurrentes.
    - undetermined: Distribución espacial dispersa o ambigua que no permite inferir el orden con confianza >= 0.60.
    - none: Tabla puramente textual sin celdas de simbología gráfica.
    """
    sym_cells = [c for c in cells if c.cell_type in ("symbol_only", "mixed", "symbol_cell", "mixed_cell") or c.has_symbol]
    if not sym_cells:
        return TableOrientationResult(
            orientation="none",
            orientation_confidence=1.0,
            orientation_reason="Tabla puramente textual sin celdas de simbología gráfica detectadas."
        )

    # Coordenadas de celdas de símbolos
    coords = [(c.row_index, c.column_index) for c in sym_cells]
    col_counts = Counter(col for r, col in coords)
    row_counts = Counter(r for r, col in coords)

    dominant_col, max_c_count = col_counts.most_common(1)[0]
    dominant_c_ratio = max_c_count / len(sym_cells)

    dominant_row, max_r_count = row_counts.most_common(1)[0]
    dominant_r_ratio = max_r_count / len(sym_cells)

    cells_by_row: Dict[int, List[ExtractedCellDTO]] = defaultdict(list)
    cells_by_col: Dict[int, List[ExtractedCellDTO]] = defaultdict(list)
    for c in cells:
        cells_by_row[c.row_index].append(c)
        cells_by_col[c.column_index].append(c)

    # Verificar presencia de texto adyacente a la derecha por fila
    right_text_hits = 0
    for r, col in coords:
        row_cells = cells_by_row.get(r, [])
        if any(other.column_index > col and other.cell_type in ("text_only", "mixed", "text_cell", "mixed_cell") and other.text.strip() for other in row_cells):
            right_text_hits += 1

    # Verificar presencia de texto adyacente abajo por columna
    below_text_hits = 0
    for r, col in coords:
        col_cells = cells_by_col.get(col, [])
        if any(other.row_index > r and other.cell_type in ("text_only", "mixed", "text_cell", "mixed_cell") and other.text.strip() for other in col_cells):
            below_text_hits += 1

    # Caso A: Símbolos alineados en columna con texto a la derecha -> Row-Major
    if dominant_c_ratio >= 0.70 and right_text_hits >= below_text_hits and right_text_hits > 0:
        conf = 0.95 if dominant_c_ratio >= 0.90 else 0.85
        return TableOrientationResult(
            orientation="row_major",
            orientation_confidence=conf,
            orientation_reason=f"{len(sym_cells)} símbolos agrupados en columna {dominant_col} ({int(dominant_c_ratio*100)}% de celdas gráficas) con descripciones técnicas a la derecha por fila."
        )

    # Caso B: Símbolos alineados en fila con texto abajo -> Col-Major
    if dominant_r_ratio >= 0.70 and below_text_hits > right_text_hits and below_text_hits > 0:
        conf = 0.95 if dominant_r_ratio >= 0.90 else 0.85
        return TableOrientationResult(
            orientation="col_major",
            orientation_confidence=conf,
            orientation_reason=f"{len(sym_cells)} símbolos agrupados en fila {dominant_row} ({int(dominant_r_ratio*100)}% de celdas gráficas) con descripciones técnicas en celdas inferiores por columna."
        )

    # Caso C: Modo Mixto estructurado (múltiples columnas y filas de símbolos con texto)
    if len(col_counts) > 1 and len(row_counts) > 1 and (right_text_hits > 0 or below_text_hits > 0):
        return TableOrientationResult(
            orientation="mixed",
            orientation_confidence=0.85,
            orientation_reason="Símbolos distribuidos en múltiples filas y columnas con encabezados superiores y descripciones laterales concurrentes (modo mixto 2D)."
        )

    # Caso D: Símbolo único
    if len(sym_cells) == 1:
        if right_text_hits > 0 and below_text_hits == 0:
            return TableOrientationResult(
                orientation="row_major",
                orientation_confidence=0.85,
                orientation_reason="Símbolo único con texto técnico descriptivo ubicado a la derecha en la misma fila."
            )
        elif below_text_hits > 0 and right_text_hits == 0:
            return TableOrientationResult(
                orientation="col_major",
                orientation_confidence=0.85,
                orientation_reason="Símbolo único con texto técnico descriptivo ubicado en la celda inferior de la columna."
            )

    # Caso E: Indeterminado / Baja confianza
    return TableOrientationResult(
        orientation="undetermined",
        orientation_confidence=0.40,
        orientation_reason="Distribución espacial ambigua de símbolos y texto sin patrón claro de fila ni columna; requiere revisión humana obligatoria."
    )


def associate_symbol_semantics_directional(
    dominant_orientation: str,
    adjacent_dominant_texts: List[str],
    col_header: str,
    row_header: str,
    table_subtitles: List[str],
    table_title: str,
    row_index: int,
    col_index: int,
    category_hint: Optional[str] = None,
    orientation_confidence: float = 1.0,
    raw_symbol_text: Optional[str] = None
) -> Dict[str, Any]:
    """
    Enriquece un símbolo según la jerarquía del sentido detectado:
    1. Celdas adyacentes del sentido dominante (derecha si row_major, abajo si col_major, ambas si mixed).
    2. Encabezados de fila / columna.
    3. Títulos o subtítulos superiores de la tabla/sección.
    4. Contexto general de la tabla / disciplina.
    Si orientation == 'undetermined' o orientation_confidence < 0.60:
    Marca requires_human_review = True en vez de inventar o falsear información.
    """
    # Si la orientación no se pudo determinar con suficiente confianza:
    if dominant_orientation == "undetermined" or orientation_confidence < 0.60:
        base_name = raw_symbol_text.strip() if raw_symbol_text and raw_symbol_text.strip() else f"Símbolo (Fila {row_index}, Col {col_index})"
        return {
            "symbol_name": sanitize_symbol_title(base_name, fallback=f"Símbolo R{row_index}C{col_index}"),
            "symbol_description": "Orientación de lectura de tabla no determinada con suficiente confianza (<60%). Requiere revisión y validación humana obligatoria.",
            "technical_function": None,
            "standard_reference": None,
            "canonical_symbol_family": category_hint or "other",
            "category": "simbologia",
            "discipline": "general",
            "tag_or_code": f"SYM-R{row_index:02d}-C{col_index:02d}",
            "aliases": [base_name] if base_name else [],
            "raw_right_texts": adjacent_dominant_texts,
            "requires_human_review": True
        }

    # Filtrar textos ruidosos tipo binarios/matriciales
    valid_texts = []
    for t in adjacent_dominant_texts:
        if not t:
            continue
        cleaned_t = clean_spacing_and_newlines(t)
        if cleaned_t and not is_binary_or_matrix_garbage(cleaned_t):
            no_prefix = re.sub(r"^(N[°o]\s*\d+|ITEM\s*\d+|[\d\.\-]+)\s*[\:\-\.]?\s*", "", cleaned_t, flags=re.IGNORECASE).strip()
            if no_prefix and not is_binary_or_matrix_garbage(no_prefix):
                valid_texts.append(no_prefix)

    primary_adj = valid_texts[0] if valid_texts else ""
    secondary_adjs = valid_texts[1:] if len(valid_texts) > 1 else []
    full_adj_str = " - ".join(valid_texts)

    c_hdr = clean_spacing_and_newlines(col_header)
    r_hdr = clean_spacing_and_newlines(row_header)
    hdr_context = f"{c_hdr} {r_hdr}".strip()
    sub_context = " ".join(clean_spacing_and_newlines(s) for s in table_subtitles if s).strip()
    tbl_title = clean_spacing_and_newlines(table_title)

    # 1. Búsqueda de norma / estándar
    all_context = f"{full_adj_str} {hdr_context} {sub_context} {tbl_title}".strip()
    standard_ref = None
    std_match = STD_REGEX.search(all_context)
    if std_match:
        standard_ref = std_match.group(0).strip()

    # 2. Búsqueda de tag o código
    tag_or_code = None
    tag_match = TAG_REGEX.search(full_adj_str)
    if tag_match:
        tag_or_code = tag_match.group(0).strip().upper()
    else:
        tag_or_code = f"SYM-R{row_index:02d}-C{col_index:02d}"

    # 3. Match en TECHNICAL_KNOWLEDGE_CATALOG
    matched_cat = None
    search_space = f"{primary_adj} {' '.join(secondary_adjs)} {hdr_context} {sub_context}".lower()
    for entry in TECHNICAL_KNOWLEDGE_CATALOG:
        for kw in entry.get("keywords", []):
            if kw in search_space:
                matched_cat = entry
                break
        if matched_cat:
            break

    # 4. Síntesis de symbol_name
    if primary_adj:
        if matched_cat and len(primary_adj) < 80:
            symbol_name = sanitize_symbol_title(primary_adj, fallback=matched_cat["title"])
        else:
            symbol_name = sanitize_symbol_title(primary_adj, fallback=f"Símbolo Fila {row_index}")
    elif matched_cat:
        symbol_name = matched_cat["title"]
    elif hdr_context:
        symbol_name = sanitize_symbol_title(f"{hdr_context} - Símbolo {row_index}", fallback=f"Símbolo Fila {row_index}")
    else:
        symbol_name = f"Símbolo Fila {row_index}"

    # 5. Síntesis de symbol_description
    desc_clauses = []
    if primary_adj and primary_adj != symbol_name:
        desc_clauses.append(primary_adj)
    if secondary_adjs:
        desc_clauses.extend(secondary_adjs)
    if matched_cat:
        desc_clauses.append(matched_cat["description"])
    elif hdr_context:
        desc_clauses.append(f"Clasificación: {hdr_context}")

    raw_desc = ". ".join(desc_clauses) if desc_clauses else f"Elemento simbólico en {tbl_title}."
    symbol_description = sanitize_symbol_content_text(
        description=raw_desc,
        title=symbol_name,
        technical_function=matched_cat.get("function") if matched_cat else None,
        max_length=350
    )

    # 6. technical_function
    if matched_cat:
        technical_function = matched_cat.get("function")
    elif primary_adj:
        technical_function = f"Componente de control, paso o seccionamiento según {standard_ref or tbl_title}."
    else:
        technical_function = f"Elemento simbólico identificado en {tbl_title}."

    # 7. Familia Canónica y disciplina
    raw_cat = category_hint or (matched_cat.get("properties", {}).get("category") if matched_cat else "valves")
    raw_cat_lower = str(raw_cat).lower()
    if any(k in raw_cat_lower for k in ["valve", "válvula"]):
        canonical_family = "valves"
    elif any(k in raw_cat_lower for k in ["instrument", "sensor", "transmisor", "indicador"]):
        canonical_family = "instruments"
    elif any(k in raw_cat_lower for k in ["pump", "bomba", "compresor"]):
        canonical_family = "pumps"
    elif any(k in raw_cat_lower for k in ["fitting", "accesorio", "brida", "codo"]):
        canonical_family = "fittings"
    elif any(k in raw_cat_lower for k in ["line", "tubería", "tuberia"]):
        canonical_family = "line_types"
    else:
        canonical_family = raw_cat_lower if raw_cat_lower in ["valves", "instruments", "pumps", "fittings", "line_types", "architectural", "structural", "electrical", "other"] else "valves"

    category_display = (matched_cat.get("properties", {}).get("category") if matched_cat else canonical_family.capitalize())
    discipline = (matched_cat.get("discipline") if matched_cat else "piping").split(" / ")[0].lower()
    if standard_ref is None and matched_cat:
        standard_ref = matched_cat.get("source_label", "Norma ISA 5.1 / ASME B16.34")

    # 8. Aliases
    aliases = []
    for txt in valid_texts:
        if txt and txt != symbol_name and txt not in aliases:
            aliases.append(txt)
    if tag_or_code and tag_or_code not in aliases:
        aliases.append(tag_or_code)
    if matched_cat and matched_cat["title"] != symbol_name and matched_cat["title"] not in aliases:
        aliases.append(matched_cat["title"])

    return {
        "symbol_name": symbol_name,
        "symbol_description": symbol_description,
        "technical_function": technical_function,
        "standard_reference": standard_ref or "Norma Técnica Aplicable",
        "canonical_symbol_family": canonical_family,
        "category": category_display,
        "discipline": discipline,
        "tag_or_code": tag_or_code,
        "aliases": aliases,
        "raw_right_texts": adjacent_dominant_texts,
        "requires_human_review": False
    }


def associate_symbol_semantics_two_sources(
    right_texts: List[str],
    immediate_top_header: str,
    table_title: str,
    row_index: int,
    col_index: int,
    category_hint: Optional[str] = None
) -> Dict[str, Any]:
    """
    Asocia y enriquece semánticamente un símbolo delegando en el motor direccional con modo row_major.
    """
    return associate_symbol_semantics_directional(
        dominant_orientation="row_major",
        adjacent_dominant_texts=right_texts,
        col_header=immediate_top_header,
        row_header="",
        table_subtitles=[],
        table_title=table_title,
        row_index=row_index,
        col_index=col_index,
        category_hint=category_hint,
        orientation_confidence=1.0
    )


class TableExtractor:
    """
    Extractor espacial híbrido y auditable de tablas a partir de bloques OCR
    y candidatos simbólicos (P&ID, cuadros técnicos y leyendas estructuradas).
    Detecta celdas con simbología B/N, genera recortes visuales obligatorios y
    vincula el linaje tabla-fila-columna.
    """

    def __init__(self, width_px: int = 8000, height_px: int = 6000):
        self.width_px = width_px
        self.height_px = height_px
        self.geometric_validator = GeometricEvidenceValidator(self.width_px, self.height_px)
        self.crops_dir = os.path.join(settings.STORAGE_LOCAL_ROOT, "crops", "symbols")
    def _classify_and_merge_vector_segments(
        self,
        rx0: float, ry0: float, rx1: float, ry1: float,
        page: Optional[Any],
        drawings: Optional[List[Any]]
    ) -> Tuple[Optional[List[float]], Optional[List[float]], List[Dict[str, Any]]]:
        """
        Detección estructural basada en grafo de segmentos vectoriales y taxonomía de 9 clases:
        1. table_outer_border
        2. table_row_boundary
        3. table_column_boundary
        4. table_subgrid
        5. cell_content
        6. axis
        7. waveform
        8. diagram_connection
        9. unknown

        Regla innegociable: Solo table_outer_border, table_row_boundary y table_column_boundary
        pueden formar x_boundaries y y_boundaries.
        Los segmentos axis, waveform, cell_content, diagram_connection y unknown no pueden modificar cell_bbox.
        """
        page_drawings = drawings if drawings is not None else (page.get_drawings() if page else [])
        if not page_drawings:
            return None, None, []

        pw = float(page.rect.width) if page else float(self.width_px)
        ph = float(page.rect.height) if page else float(self.height_px)

        table_w_pt = (rx1 - rx0) * pw
        table_h_pt = (ry1 - ry0) * ph

        if table_w_pt < 20.0 or table_h_pt < 20.0:
            return None, None, []

        h_segs = []
        v_segs = []

        for d in page_drawings:
            dr = d.get("rect")
            if not dr:
                continue
            dx0 = dr.x0 / pw
            dy0 = dr.y0 / ph
            dx1 = dr.x1 / pw
            dy1 = dr.y1 / ph

            # Segmento horizontal: altura delgada (<= 5 pt) y longitud >= 10 pt
            if (rx0 - 0.02) <= dx1 and dx0 <= (rx1 + 0.02) and (ry0 - 0.02) <= dy1 and dy0 <= (ry1 + 0.02):
                if dr.height <= 5.0 and dr.width >= 10.0:
                    h_segs.append({
                        "id": f"h_{len(h_segs)}",
                        "x0": dr.x0,
                        "y0": (dr.y0 + dr.y1) / 2.0,
                        "x1": dr.x1,
                        "y1": (dr.y0 + dr.y1) / 2.0,
                        "w": dr.width,
                        "rect": dr,
                        "drawing": d
                    })
                elif dr.width <= 5.0 and dr.height >= 10.0:
                    v_segs.append({
                        "id": f"v_{len(v_segs)}",
                        "x0": (dr.x0 + dr.x1) / 2.0,
                        "y0": dr.y0,
                        "x1": (dr.x0 + dr.x1) / 2.0,
                        "y1": dr.y1,
                        "h": dr.height,
                        "rect": dr,
                        "drawing": d
                    })

        if not h_segs or not v_segs:
            return None, None, []

        # 1. Fusión de segmentos verticales colineales (tolerancia x <= 2.0 pt, gap <= 4.5 pt)
        v_groups: List[Dict[str, Any]] = []
        for s in sorted(v_segs, key=lambda s: s["x0"]):
            placed = False
            for g in v_groups:
                if abs(g["x"] - s["x0"]) <= 2.0:
                    g["segments"].append(s)
                    g["x"] = sum(seg["x0"] for seg in g["segments"]) / len(g["segments"])
                    placed = True
                    break
            if not placed:
                v_groups.append({"x": s["x0"], "segments": [s]})

        merged_v: List[Dict[str, Any]] = []
        for g in v_groups:
            segs = sorted(g["segments"], key=lambda s: s["y0"])
            cur_y0 = segs[0]["y0"]
            cur_y1 = segs[0]["y1"]
            cur_segs = [segs[0]]
            for nxt in segs[1:]:
                if nxt["y0"] <= cur_y1 + 4.5:
                    cur_y1 = max(cur_y1, nxt["y1"])
                    cur_segs.append(nxt)
                else:
                    merged_v.append({
                        "x": g["x"],
                        "y0": cur_y0,
                        "y1": cur_y1,
                        "h": cur_y1 - cur_y0,
                        "segments": cur_segs
                    })
                    cur_y0 = nxt["y0"]
                    cur_y1 = nxt["y1"]
                    cur_segs = [nxt]
            merged_v.append({
                "x": g["x"],
                "y0": cur_y0,
                "y1": cur_y1,
                "h": cur_y1 - cur_y0,
                "segments": cur_segs
            })

        long_outer_v = [v for v in merged_v if v["h"] >= table_h_pt * 0.35]
        if not long_outer_v:
            long_outer_v = merged_v

        v_table_y0 = min(v["y0"] for v in long_outer_v)
        v_table_y1 = max(v["y1"] for v in long_outer_v)
        eff_table_h = max(10.0, v_table_y1 - v_table_y0)

        # 2. Identificar columnas (span >= 35% de la altura efectiva de tabla)
        column_lines = [v for v in merged_v if v["h"] >= eff_table_h * 0.35]
        col_xs_pt = sorted([v["x"] for v in column_lines])

        left_edge_pt = rx0 * pw
        right_edge_pt = rx1 * pw
        if not col_xs_pt:
            col_xs_pt = [left_edge_pt, right_edge_pt]
        else:
            if abs(col_xs_pt[0] - left_edge_pt) <= 15.0:
                col_xs_pt[0] = min(col_xs_pt[0], left_edge_pt)
            else:
                col_xs_pt.insert(0, left_edge_pt)

            if abs(col_xs_pt[-1] - right_edge_pt) <= 15.0:
                col_xs_pt[-1] = max(col_xs_pt[-1], right_edge_pt)
            else:
                col_xs_pt.append(right_edge_pt)

        clustered_col_xs: List[float] = []
        for cx in col_xs_pt:
            if not clustered_col_xs:
                clustered_col_xs.append(cx)
            elif abs(cx - clustered_col_xs[-1]) <= 4.0:
                clustered_col_xs[-1] = (clustered_col_xs[-1] + cx) / 2.0
            else:
                clustered_col_xs.append(cx)

        # 3. Fusión de segmentos horizontales colineales
        h_groups: List[Dict[str, Any]] = []
        for s in sorted(h_segs, key=lambda s: s["y0"]):
            placed = False
            for g in h_groups:
                if abs(g["y"] - s["y0"]) <= 2.0:
                    g["segments"].append(s)
                    g["y"] = sum(seg["y0"] for seg in g["segments"]) / len(g["segments"])
                    placed = True
                    break
            if not placed:
                h_groups.append({"y": s["y0"], "segments": [s]})

        merged_h: List[Dict[str, Any]] = []
        for g in h_groups:
            segs = sorted(g["segments"], key=lambda s: s["x0"])
            cur_x0 = segs[0]["x0"]
            cur_x1 = segs[0]["x1"]
            cur_segs = [segs[0]]
            for nxt in segs[1:]:
                if nxt["x0"] <= cur_x1 + 4.5:
                    cur_x1 = max(cur_x1, nxt["x1"])
                    cur_segs.append(nxt)
                else:
                    merged_h.append({
                        "y": g["y"],
                        "x0": cur_x0,
                        "x1": cur_x1,
                        "w": cur_x1 - cur_x0,
                        "segments": cur_segs
                    })
                    cur_x0 = nxt["x0"]
                    cur_x1 = nxt["x1"]
                    cur_segs = [nxt]
            merged_h.append({
                "y": g["y"],
                "x0": cur_x0,
                "x1": cur_x1,
                "w": cur_x1 - cur_x0,
                "segments": cur_segs
            })

        # 4. Clasificación según la taxonomía estricta de 9 clases
        classified_segments: List[Dict[str, Any]] = []
        valid_row_ys_pt: List[float] = []

        for h in merged_h:
            hy = h["y"]
            hx0 = h["x0"]
            hx1 = h["x1"]
            hw = h["w"]

            touches_left_col = any(abs(hx0 - cx) <= 6.0 for cx in clustered_col_xs)
            touches_right_col = any(abs(hx1 - cx) <= 6.0 for cx in clustered_col_xs)
            spans_full_table = (abs(hx0 - clustered_col_xs[0]) <= 8.0 and abs(hx1 - clustered_col_xs[-1]) <= 8.0)
            connects_columns = (touches_left_col and touches_right_col and hw >= 25.0) or spans_full_table

            if spans_full_table and (abs(hy - v_table_y0) <= 6.0 or abs(hy - v_table_y1) <= 6.0):
                classification = "table_outer_border"
                valid_row_ys_pt.append(hy)
            elif connects_columns:
                classification = "table_row_boundary"
                valid_row_ys_pt.append(hy)
            elif hw >= 100.0 and not touches_left_col and not touches_right_col:
                classification = "axis"
            elif hw < 100.0 and not connects_columns:
                classification = "waveform"
            else:
                classification = "cell_content"

            classified_segments.append({
                "orientation": "horizontal",
                "x0_pt": hx0,
                "y0_pt": hy,
                "x1_pt": hx1,
                "y1_pt": hy,
                "x0_norm": hx0 / pw,
                "y0_norm": hy / ph,
                "x1_norm": hx1 / pw,
                "y1_norm": hy / ph,
                "y_norm": hy / ph,
                "width_pt": hw,
                "classification": classification
            })

        for v in merged_v:
            vx = v["x"]
            vy0 = v["y0"]
            vy1 = v["y1"]
            vh = v["h"]

            is_col_line = any(abs(vx - cx) <= 3.0 for cx in clustered_col_xs)
            is_outer_v = (abs(vx - clustered_col_xs[0]) <= 5.0 or abs(vx - clustered_col_xs[-1]) <= 5.0)

            if is_outer_v and vh >= eff_table_h * 0.35:
                classification = "table_outer_border"
            elif is_col_line and vh >= eff_table_h * 0.35:
                classification = "table_column_boundary"
            elif vh >= 40.0 and not is_col_line:
                classification = "axis"
            elif vh < 40.0:
                classification = "table_subgrid"
            else:
                classification = "cell_content"

            classified_segments.append({
                "orientation": "vertical",
                "x0_pt": vx,
                "y0_pt": vy0,
                "x1_pt": vx,
                "y1_pt": vy1,
                "x0_norm": vx / pw,
                "y0_norm": vy0 / ph,
                "x1_norm": vx / pw,
                "y1_norm": vy1 / ph,
                "x_norm": vx / pw,
                "height_pt": vh,
                "classification": classification
            })

        # 5. Clusterizar coordenadas Y de filas válidas
        clustered_row_ys: List[float] = []
        for ry in sorted(valid_row_ys_pt):
            if not clustered_row_ys:
                clustered_row_ys.append(ry)
            elif abs(ry - clustered_row_ys[-1]) <= 4.0:
                clustered_row_ys[-1] = (clustered_row_ys[-1] + ry) / 2.0
            else:
                clustered_row_ys.append(ry)

        top_edge_pt = ry0 * ph
        bot_edge_pt = ry1 * ph
        if not clustered_row_ys:
            clustered_row_ys = [top_edge_pt, bot_edge_pt]
        else:
            if abs(clustered_row_ys[0] - top_edge_pt) <= 15.0:
                clustered_row_ys[0] = min(clustered_row_ys[0], top_edge_pt)
            else:
                clustered_row_ys.insert(0, top_edge_pt)

            if abs(clustered_row_ys[-1] - bot_edge_pt) <= 15.0:
                clustered_row_ys[-1] = max(clustered_row_ys[-1], bot_edge_pt)
            else:
                clustered_row_ys.append(bot_edge_pt)

        norm_grid_x = [round(x / pw, 4) for x in clustered_col_xs]
        norm_grid_y = [round(y / ph, 4) for y in clustered_row_ys]

        if len(norm_grid_x) >= 2 and len(norm_grid_y) >= 2:
            return norm_grid_x, norm_grid_y, classified_segments

        return None, None, classified_segments

    def _compute_cell_boundary_evidence(
        self,
        cell_bbox_norm: List[float],
        classified_segments: List[Dict[str, Any]],
        grid_source: str
    ) -> Tuple[Dict[str, Dict[str, Any]], float]:
        """
        Calcula la evidencia física de fronteras (top, bottom, left, right)
        y ratio de cobertura perimetral de una celda.
        """
        c_x0, c_y0, c_x1, c_y1 = cell_bbox_norm
        cell_w = max(0.001, c_x1 - c_x0)
        cell_h = max(0.001, c_y1 - c_y0)

        cov_top = 0.0
        cov_bottom = 0.0
        cov_left = 0.0
        cov_right = 0.0

        for seg in classified_segments:
            if seg["classification"] not in ["table_outer_border", "table_row_boundary", "table_column_boundary"]:
                continue
            if seg["orientation"] == "horizontal":
                if abs(seg["y_norm"] - c_y0) <= 0.015:
                    ov = max(0.0, min(seg["x1_norm"], c_x1) - max(seg["x0_norm"], c_x0))
                    cov_top = max(cov_top, min(1.0, ov / cell_w))
                if abs(seg["y_norm"] - c_y1) <= 0.015:
                    ov = max(0.0, min(seg["x1_norm"], c_x1) - max(seg["x0_norm"], c_x0))
                    cov_bottom = max(cov_bottom, min(1.0, ov / cell_w))
            elif seg["orientation"] == "vertical":
                if abs(seg["x_norm"] - c_x0) <= 0.015:
                    ov = max(0.0, min(seg["y1_norm"], c_y1) - max(seg["y0_norm"], c_y0))
                    cov_left = max(cov_left, min(1.0, ov / cell_h))
                if abs(seg["x_norm"] - c_x1) <= 0.015:
                    ov = max(0.0, min(seg["y1_norm"], c_y1) - max(seg["y0_norm"], c_y0))
                    cov_right = max(cov_right, min(1.0, ov / cell_h))

        if grid_source == "raster" and (cov_top + cov_bottom + cov_left + cov_right) == 0.0:
            cov_top = cov_bottom = cov_left = cov_right = 0.85
        elif grid_source == "logical_alignment" and (cov_top + cov_bottom + cov_left + cov_right) == 0.0:
            cov_top = cov_bottom = cov_left = cov_right = 0.40

        mean_cov = round((cov_top + cov_bottom + cov_left + cov_right) / 4.0, 3)
        evidence = {
            "top": {
                "detected": cov_top >= 0.50,
                "coverage_ratio": round(cov_top, 3),
                "source": f"{grid_source}_grid"
            },
            "bottom": {
                "detected": cov_bottom >= 0.50,
                "coverage_ratio": round(cov_bottom, 3),
                "source": f"{grid_source}_grid"
            },
            "left": {
                "detected": cov_left >= 0.50,
                "coverage_ratio": round(cov_left, 3),
                "source": f"{grid_source}_grid"
            },
            "right": {
                "detected": cov_right >= 0.50,
                "coverage_ratio": round(cov_right, 3),
                "source": f"{grid_source}_grid"
            }
        }
        return evidence, mean_cov

    def _detect_vector_grid_lines(
        self,
        rx0: float, ry0: float, rx1: float, ry1: float,
        page: Optional[Any],
        drawings: Optional[List[Any]]
    ) -> Tuple[Optional[List[float]], Optional[List[float]], List[Dict[str, Any]]]:
        """
        Prioridad 1: Detecta líneas divisorias físicas vectoriales delegando en el grafo estructural.
        """
        return self._classify_and_merge_vector_segments(rx0, ry0, rx1, ry1, page, drawings)

    def _detect_raster_grid_lines(
        self,
        rx0: float, ry0: float, rx1: float, ry1: float,
        page: Optional[Any],
        image_path: Optional[str],
        image_bytes: Optional[bytes]
    ) -> Tuple[Optional[List[float]], Optional[List[float]]]:
        """
        Prioridad 2: Detecta líneas divisorias físicas en imagen raster mediante morfología y proyecciones.
        """
        try:
            import cv2
            import numpy as np
        except ImportError:
            return None, None

        img_gray = None
        pw = float(self.width_px)
        ph = float(self.height_px)

        if page is not None:
            try:
                import fitz
                pw = float(page.rect.width)
                ph = float(page.rect.height)
                clip = fitz.Rect(rx0 * pw, ry0 * ph, rx1 * pw, ry1 * ph)
                pix = page.get_pixmap(dpi=150, clip=clip)
                img_data = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
                if pix.n >= 3:
                    img_gray = cv2.cvtColor(img_data, cv2.COLOR_RGB2GRAY)
                else:
                    img_gray = img_data[:, :, 0]
            except Exception:
                img_gray = None
        elif image_path and os.path.exists(image_path):
            try:
                full_img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
                if full_img is not None:
                    h, w = full_img.shape
                    img_gray = full_img[int(ry0 * h):int(ry1 * h), int(rx0 * w):int(rx1 * w)]
            except Exception:
                img_gray = None
        elif image_bytes:
            try:
                arr = np.frombuffer(image_bytes, np.uint8)
                full_img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
                if full_img is not None:
                    h, w = full_img.shape
                    img_gray = full_img[int(ry0 * h):int(ry1 * h), int(rx0 * w):int(rx1 * w)]
            except Exception:
                img_gray = None

        if img_gray is None or img_gray.shape[0] < 20 or img_gray.shape[1] < 20:
            return None, None

        reg_h, reg_w = img_gray.shape
        _, binary = cv2.threshold(img_gray, 205, 255, cv2.THRESH_BINARY_INV)

        kernel_len_h = max(15, int(reg_w * 0.18))
        kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_len_h, 1))
        h_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_h)

        kernel_len_v = max(15, int(reg_h * 0.18))
        kernel_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, kernel_len_v))
        v_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_v)

        h_proj = np.sum(h_lines, axis=1)
        v_proj = np.sum(v_lines, axis=0)

        h_thresh = reg_w * 0.20 * 255
        v_thresh = reg_h * 0.20 * 255

        raw_y = [ry0 + (y / reg_h) * (ry1 - ry0) for y in range(reg_h) if h_proj[y] >= h_thresh]
        raw_x = [rx0 + (x / reg_w) * (rx1 - rx0) for x in range(reg_w) if v_proj[x] >= v_thresh]

        if not raw_y or not raw_x:
            return None, None

        def _cluster(coords: List[float], min_v: float, max_v: float) -> List[float]:
            if not coords:
                return [round(min_v, 4), round(max_v, 4)]
            coords.sort()
            cl: List[float] = []
            for c in coords:
                if not cl:
                    cl.append(c)
                elif abs(c - cl[-1]) <= 0.015:
                    cl[-1] = (cl[-1] + c) / 2.0
                else:
                    cl.append(c)
            if not cl or abs(cl[0] - min_v) > 0.025:
                cl.insert(0, min_v)
            else:
                cl[0] = min_v
            if abs(cl[-1] - max_v) > 0.025:
                cl.append(max_v)
            else:
                cl[-1] = max_v
            return [round(c, 4) for c in cl]

        grid_y = _cluster(raw_y, ry0, ry1)
        grid_x = _cluster(raw_x, rx0, rx1)

        if len(grid_y) >= 2 and len(grid_x) >= 2:
            return grid_x, grid_y
        return None, None

    def _detect_logical_alignment_grid(
        self,
        rx0: float, ry0: float, rx1: float, ry1: float,
        col_centers: Optional[List[float]],
        rows_data: Optional[List[Any]]
    ) -> Tuple[List[float], List[float]]:
        """
        Prioridad 3: Grilla lógica deducida por alineamiento y centroides de contenido.
        """
        if col_centers and len(col_centers) > 0:
            grid_x = [rx0] + [(col_centers[i] + col_centers[i + 1]) / 2.0 for i in range(len(col_centers) - 1)] + [rx1]
        else:
            grid_x = [rx0, rx1]

        if rows_data and len(rows_data) > 0:
            row_y_centers = []
            for r in rows_data:
                if isinstance(r, list) and len(r) > 0:
                    valid_cy = [elem["cy"] for elem in r if isinstance(elem, dict) and "cy" in elem]
                    if valid_cy:
                        row_y_centers.append(sum(valid_cy) / len(valid_cy))
            if len(row_y_centers) > 1:
                grid_y = [ry0] + [(row_y_centers[i] + row_y_centers[i + 1]) / 2.0 for i in range(len(row_y_centers) - 1)] + [ry1]
            else:
                grid_y = [ry0, ry1]
        else:
            grid_y = [ry0, ry1]

        return [round(x, 4) for x in grid_x], [round(y, 4) for y in grid_y]

    def _detect_table_grid(
        self,
        rx0: float, ry0: float, rx1: float, ry1: float,
        page: Optional[Any],
        drawings: Optional[List[Any]],
        image_path: Optional[str] = None,
        image_bytes: Optional[bytes] = None,
        col_centers: Optional[List[float]] = None,
        rows_data: Optional[List[Any]] = None
    ) -> Tuple[List[float], List[float], str, float, bool, List[Dict[str, Any]]]:
        """
        Detección jerárquica de grilla:
        1. Vectorial -> 2. Raster -> 3. Logical alignment fallback.
        Retorna (x_boundaries, y_boundaries, grid_source, grid_confidence, physical_grid_detected, classified_segments).
        """
        # Prioridad 1: Vectorial
        vx, vy, classified_segs = self._detect_vector_grid_lines(rx0, ry0, rx1, ry1, page, drawings)
        if vx and vy and len(vx) >= 2 and len(vy) >= 2:
            return vx, vy, "vector", 0.95, True, classified_segs

        # Prioridad 2: Raster
        rx, ry = self._detect_raster_grid_lines(rx0, ry0, rx1, ry1, page, image_path, image_bytes)
        if rx and ry and len(rx) >= 2 and len(ry) >= 2:
            return rx, ry, "raster", 0.88, True, []

        # Prioridad 3: Grilla lógica por alineamiento de contenido
        lx, ly = self._detect_logical_alignment_grid(rx0, ry0, rx1, ry1, col_centers, rows_data)
        conf = 0.65 if (len(lx) >= 2 and len(ly) >= 2) else 0.40
        return lx, ly, "logical_alignment", conf, False, []

    def _calculate_cell_spans(
        self,
        r_idx: int,
        c_idx: int,
        grid_x: List[float],
        grid_y: List[float],
        page_drawings: Optional[List[Any]],
        pw: float,
        ph: float
    ) -> Tuple[int, int]:
        """
        Determina si una celda física tiene col_span o row_span debido a celdas combinadas
        (ausencia de divisor interior entre dos límites consecutivos de la grilla).
        """
        col_span = 1
        row_span = 1
        num_cols = len(grid_x) - 1
        num_rows = len(grid_y) - 1

        if c_idx < num_cols - 1 and page_drawings:
            div_x = grid_x[c_idx + 1]
            y_start = grid_y[r_idx]
            y_end = grid_y[r_idx + 1]
            has_v_divider = False

            for d in page_drawings:
                dr = d.get("rect")
                if not dr:
                    continue
                dx = ((dr.x0 + dr.x1) / 2.0) / pw
                dy0 = dr.y0 / ph
                dy1 = dr.y1 / ph
                if abs(dx - div_x) <= 0.015 and dr.width <= 10.0:
                    overlap_y0 = max(dy0, y_start)
                    overlap_y1 = min(dy1, y_end)
                    if (overlap_y1 - overlap_y0) >= (y_end - y_start) * 0.55:
                        has_v_divider = True
                        break
            if not has_v_divider:
                col_span = 2

        if r_idx < num_rows - 1 and page_drawings:
            div_y = grid_y[r_idx + 1]
            x_start = grid_x[c_idx]
            x_end = grid_x[c_idx + 1]
            has_h_divider = False

            for d in page_drawings:
                dr = d.get("rect")
                if not dr:
                    continue
                dy = ((dr.y0 + dr.y1) / 2.0) / ph
                dx0 = dr.x0 / pw
                dx1 = dr.x1 / pw
                if abs(dy - div_y) <= 0.015 and dr.height <= 10.0:
                    overlap_x0 = max(dx0, x_start)
                    overlap_x1 = min(dx1, x_end)
                    if (overlap_x1 - overlap_x0) >= (x_end - x_start) * 0.55:
                        has_h_divider = True
                        break
            if not has_h_divider:
                row_span = 2

        return row_span, col_span

    def extract_from_region(
        self,
        region_bbox_norm: List[float],
        texts: List[Any],
        symbols: Optional[List[Any]] = None,
        page: Optional[Any] = None,
        image_path: Optional[str] = None,
        image_bytes: Optional[bytes] = None,
        drawings: Optional[List[Any]] = None,
        doc_uid: str = "doc",
        crops_dir: Optional[str] = None
    ) -> Optional[ExtractedTableDTO]:
        rx0, ry0, rx1, ry1 = region_bbox_norm
        actual_crops_dir = crops_dir or self.crops_dir
        os.makedirs(actual_crops_dir, exist_ok=True)

        # 1. Filtrar textos que caigan dentro de la macro-región
        region_texts = []
        for t in (texts or []):
            t_bbox = getattr(t, "bbox_normalized", None) or (t.get("bbox_normalized") if isinstance(t, dict) else None)
            if not t_bbox or len(t_bbox) < 4:
                continue
            tx0, ty0, tx1, ty1 = t_bbox
            cx = (tx0 + tx1) / 2.0
            cy = (ty0 + ty1) / 2.0
            if rx0 <= cx <= rx1 and ry0 <= cy <= ry1:
                region_texts.append(t)

        # 1b. Filtrar símbolos que caigan dentro de la macro-región
        region_symbols = []
        if symbols:
            for s in symbols:
                s_bbox = getattr(s, "bbox_normalized", None) or (s.get("bbox_normalized") if isinstance(s, dict) else None)
                if s_bbox and len(s_bbox) >= 4:
                    sx0, sy0, sx1, sy1 = s_bbox
                    scx = (sx0 + sx1) / 2.0
                    scy = (sy0 + sy1) / 2.0
                    if rx0 <= scx <= rx1 and ry0 <= scy <= ry1:
                        region_symbols.append(s)

        if not region_texts and not region_symbols and not page and not image_path and not image_bytes:
            return None

        # 2. Separar título si la línea superior contiene palabras clave de tabla
        title = "Cuadro Técnico"
        body_texts = list(region_texts)

        if region_texts:
            region_texts.sort(key=lambda t: (
                getattr(t, "bbox_normalized", [0, 0, 0, 0])[1] if hasattr(t, "bbox_normalized") else t.get("bbox_normalized", [0, 0, 0, 0])[1],
                getattr(t, "bbox_normalized", [0, 0, 0, 0])[0] if hasattr(t, "bbox_normalized") else t.get("bbox_normalized", [0, 0, 0, 0])[0]
            ))
            first_line = body_texts[0]
            first_txt = getattr(first_line, "text", "") or (first_line.get("text", "") if isinstance(first_line, dict) else "")
            if re.search(r"(CUADRO|TABLA|LISTA|RESUMEN|ESPECIFICACI|LEYENDA|SIMBOLOG)", first_txt.upper()):
                title = first_txt.strip()
                body_texts = body_texts[1:]

            if not body_texts and not region_symbols:
                body_texts = [first_line]

        # 3. Agrupación en Filas por coordenada Y considerando textos, símbolos y trazos vectoriales internos
        row_tol = 0.025 # 2.5% tolerancia vertical normalizada
        all_row_items: List[Dict[str, Any]] = []

        for t in body_texts:
            t_bbox = getattr(t, "bbox_normalized", None) or (t.get("bbox_normalized") if isinstance(t, dict) else None)
            all_row_items.append({
                "type": "text",
                "item": t,
                "cy": (t_bbox[1] + t_bbox[3]) / 2.0,
                "y0": t_bbox[1],
                "y1": t_bbox[3],
                "cx": (t_bbox[0] + t_bbox[2]) / 2.0,
                "x0": t_bbox[0],
                "x1": t_bbox[2]
            })

        for s in region_symbols:
            s_bbox = getattr(s, "bbox_normalized", None) or (s.get("bbox_normalized") if isinstance(s, dict) else None)
            all_row_items.append({
                "type": "symbol",
                "item": s,
                "cy": (s_bbox[1] + s_bbox[3]) / 2.0,
                "y0": s_bbox[1],
                "y1": s_bbox[3],
                "cx": (s_bbox[0] + s_bbox[2]) / 2.0,
                "x0": s_bbox[0],
                "x1": s_bbox[2]
            })

        # Incluir trazos vectoriales internos SOLO para filas de símbolos puros sin texto (ej. tablas col_major)
        if page or drawings:
            existing_text_cys = [it["cy"] for it in all_row_items if it["type"] == "text"]
            pw = page.rect.width if page else self.width_px
            ph = page.rect.height if page else self.height_px
            page_drawings = drawings if drawings is not None else (page.get_drawings() if page else [])
            for d in (page_drawings or []):
                dr = d.get("rect")
                if not dr:
                    continue
                dx0 = dr.x0 / pw
                dy0 = dr.y0 / ph
                dx1 = dr.x1 / pw
                dy1 = dr.y1 / ph
                if rx0 <= dx0 and dx1 <= rx1 and ry0 <= dy0 and dy1 <= ry1:
                    w_norm = dx1 - dx0
                    h_norm = dy1 - dy0
                    d_cy = (dy0 + dy1) / 2.0
                    # Ignorar líneas largas divisorias de la cuadrícula
                    if 0.005 <= w_norm <= (rx1 - rx0) * 0.45 and 0.005 <= h_norm <= (ry1 - ry0) * 0.45:
                        all_row_items.append({
                            "type": "drawing",
                            "item": d,
                            "cy": d_cy,
                            "y0": dy0,
                            "y1": dy1,
                            "cx": (dx0 + dx1) / 2.0,
                            "x0": dx0,
                            "x1": dx1
                        })

        all_row_items.sort(key=lambda it: it["cy"])

        rows: List[List[Dict[str, Any]]] = []
        for it in all_row_items:
            placed = False
            for r in rows:
                r_cy = sum(elem["cy"] for elem in r) / len(r)
                if abs(it["cy"] - r_cy) <= row_tol:
                    r.append(it)
                    placed = True
                    break
            if not placed:
                rows.append([it])

        rows.sort(key=lambda r: min(elem["y0"] for elem in r))
        for r in rows:
            r.sort(key=lambda elem: elem["x0"])

        # 3.b Fusionar palabras contiguas en la misma fila para que formen frases por celda
        merged_rows: List[List[Dict[str, Any]]] = []
        for r in rows:
            merged_r: List[Dict[str, Any]] = []
            for elem in r:
                if (
                    merged_r
                    and elem["type"] == "text"
                    and merged_r[-1]["type"] == "text"
                    and (elem["x0"] - merged_r[-1]["x1"]) <= 0.035
                ):
                    prev = merged_r[-1]
                    prev_txt = getattr(prev["item"], "text", "") or (prev["item"].get("text", "") if isinstance(prev["item"], dict) else "")
                    curr_txt = getattr(elem["item"], "text", "") or (elem["item"].get("text", "") if isinstance(elem["item"], dict) else "")
                    new_txt = f"{prev_txt} {curr_txt}".strip()
                    prev["x1"] = max(prev["x1"], elem["x1"])
                    prev["y0"] = min(prev["y0"], elem["y0"])
                    prev["y1"] = max(prev["y1"], elem["y1"])
                    prev["cx"] = (prev["x0"] + prev["x1"]) / 2.0
                    prev["cy"] = (prev["y0"] + prev["y1"]) / 2.0
                    if isinstance(prev["item"], dict):
                        prev["item"]["text"] = new_txt
                        prev["item"]["clean_text"] = new_txt
                        prev["item"]["bbox_normalized"] = [prev["x0"], prev["y0"], prev["x1"], prev["y1"]]
                else:
                    merged_r.append(elem)
            merged_rows.append(merged_r)
        rows = merged_rows

        if not rows:
            return None

        # 4. Agrupación en Columnas por coordenada X considerando textos y símbolos
        col_centers: List[float] = []
        col_tol = 0.040 # 4.0% tolerancia horizontal

        for r in rows:
            for elem in r:
                cx = elem["cx"]
                placed = False
                for i, col_cx in enumerate(col_centers):
                    if abs(cx - col_cx) <= col_tol:
                        col_centers[i] = (col_centers[i] + cx) / 2.0
                        placed = True
                        break
                if not placed:
                    col_centers.append(cx)

        col_centers.sort()

        # 5. Detección jerárquica de cuadrícula física (Vector -> Raster -> Alineamiento Lógico)
        col_bounds, row_bounds, grid_source, grid_confidence, physical_grid_detected, classified_segments = self._detect_table_grid(
            rx0=rx0,
            ry0=ry0,
            rx1=rx1,
            ry1=ry1,
            page=page,
            image_path=image_path,
            image_bytes=image_bytes,
            drawings=drawings,
            col_centers=col_centers,
            rows_data=rows
        )

        num_cols = max(1, len(col_bounds) - 1)
        num_rows = max(1, len(row_bounds) - 1)
        pw = float(page.rect.width) if page else float(self.width_px)
        ph = float(page.rect.height) if page else float(self.height_px)
        page_drawings = drawings if drawings is not None else (page.get_drawings() if page else [])

        # Matriz de celdas tipo Excel con soporte explícito de tipos y extracción visual
        cells_dto: List[ExtractedCellDTO] = []
        headers_list: List[str] = ["" for _ in range(num_cols)]
        confidences: List[float] = []
        extracted_symbols_list: List[ExtractedSymbolCandidateDTO] = []

        all_table_text_bboxes = [
            (t.get("bbox_normalized") if isinstance(t, dict) else getattr(t, "bbox_normalized", None))
            for t in region_texts
            if (isinstance(t, dict) and t.get("bbox_normalized")) or hasattr(t, "bbox_normalized")
        ]

        for r_idx in range(num_rows):
            is_header_row = (r_idx == 0)
            c_y0 = row_bounds[r_idx]
            c_y1 = row_bounds[r_idx + 1]

            for c_idx in range(num_cols):
                c_x0 = col_bounds[c_idx]
                c_x1 = col_bounds[c_idx + 1]

                cell_bbox_norm = [round(c_x0, 4), round(c_y0, 4), round(c_x1, 4), round(c_y1, 4)]
                cell_bbox_px = [
                    round(c_x0 * self.width_px, 1),
                    round(c_y0 * self.height_px, 1),
                    round(c_x1 * self.width_px, 1),
                    round(c_y1 * self.height_px, 1),
                ]

                # Determinar spans si existen celdas combinadas sin divisor físico interior
                row_span, col_span = self._calculate_cell_spans(
                    r_idx=r_idx,
                    c_idx=c_idx,
                    grid_x=col_bounds,
                    grid_y=row_bounds,
                    page_drawings=page_drawings,
                    pw=pw,
                    ph=ph
                )

                # Elementos cuyo centro cae dentro de este compartimento de celda
                matched = [
                    m for m in all_row_items
                    if (c_x0 - 0.005) <= m["cx"] <= (c_x1 + 0.005) and (c_y0 - 0.005) <= m["cy"] <= (c_y1 + 0.005)
                ]
                matched_texts = [m["item"] for m in matched if m["type"] == "text"]
                matched_symbols = [m["item"] for m in matched if m["type"] == "symbol"]

                has_pre_sym = len(matched_symbols) > 0
                sym_obj = matched_symbols[0] if has_pre_sym else None
                pre_sym_id = getattr(sym_obj, "id", None) or (sym_obj.get("id") if isinstance(sym_obj, dict) else None)
                pre_crop_path = getattr(sym_obj, "crop_image_path", None) or (sym_obj.get("crop_image_path") if isinstance(sym_obj, dict) else None)

                def _get_t_str(t, key):
                    if isinstance(t, dict):
                        return str(t.get(key, "") or "").strip()
                    return str(getattr(t, key, "") or "").strip()

                def _get_t_clean(t):
                    if isinstance(t, dict):
                        return str(t.get("clean_text") or t.get("text") or "").strip()
                    return str(getattr(t, "clean_text", None) or getattr(t, "text", "") or "").strip()

                def _get_t_conf(t):
                    if isinstance(t, dict):
                        return float(t.get("confidence", 0.9))
                    return float(getattr(t, "confidence", 0.9))

                def _get_t_id(t):
                    if isinstance(t, dict):
                        return str(t.get("id", "text"))
                    return str(getattr(t, "id", "text"))

                raw_cell_text = " ".join(_get_t_str(t, "text") for t in matched_texts).strip()
                clean_cell_text = " ".join(_get_t_clean(t) for t in matched_texts).strip()
                has_text = bool(raw_cell_text and len(clean_cell_text) > 0)
                cell_conf = sum(_get_t_conf(t) for t in matched_texts) / len(matched_texts) if matched_texts else 0.85
                src_refs = [_get_t_id(t) for t in matched_texts]

                # Evaluación de evidencia geométrica visual obligatoria
                # Regla principal: GEOMETRÍA VISUAL VÁLIDA -> símbolo candidato -> OCR/contexto
                geo_eval: Optional[CellGeometricEvaluation] = None
                has_visual_source = (page is not None or image_path or image_bytes or drawings)

                if not is_header_row and has_visual_source:
                    geo_eval = self.geometric_validator.evaluate_cell(
                        cell_bbox_norm=cell_bbox_norm,
                        cell_text=raw_cell_text,
                        known_text_bboxes_norm=all_table_text_bboxes,
                        page=page,
                        image_path=image_path,
                        image_bytes=image_bytes,
                        drawings=drawings,
                        crops_dir=actual_crops_dir,
                        doc_uid=doc_uid,
                        row_index=r_idx,
                        col_index=c_idx
                    )

                # Calcular evidencia física de fronteras y cobertura de la celda
                boundary_evidence, border_cov = self._compute_cell_boundary_evidence(
                    cell_bbox_norm=cell_bbox_norm,
                    classified_segments=classified_segments,
                    grid_source=grid_source
                )

                if is_header_row:
                    content_class = "text_only" if has_text else "empty"
                    cell_type = "text_cell" if has_text else "empty"
                    has_symbol = False
                    graphic_classification = "not_symbol"
                    visual_crop_path = None
                    inner_drawing_bbox = None
                    symbol_crop_bbox = None
                    crop_margin_mm = 3.0
                    crop_err_reason = "Fila de encabezado"
                    needs_crop = False
                    geo_evidence = False
                    geo_confidence = 0.0
                    evidence_sources = []
                    shape_features = {}
                    text_mask_overlap = 1.0 if has_text else 0.0
                    rejection_reason = "Fila de encabezado"
                elif geo_eval is not None:
                    cell_type = geo_eval.cell_type
                    has_symbol = geo_eval.has_real_geometry
                    visual_crop_path = geo_eval.crop_image_path
                    inner_drawing_bbox = geo_eval.inner_drawing_bbox
                    symbol_crop_bbox = geo_eval.symbol_crop_bbox
                    crop_margin_mm = geo_eval.crop_margin_mm
                    graphic_classification = geo_eval.graphic_classification
                    crop_err_reason = geo_eval.rejection_reason
                    needs_crop = geo_eval.needs_visual_crop
                    geo_evidence = geo_eval.has_real_geometry
                    geo_confidence = geo_eval.geometric_confidence
                    evidence_sources = geo_eval.evidence_sources
                    shape_features = geo_eval.shape_features
                    text_mask_overlap = geo_eval.text_mask_overlap_ratio
                    rejection_reason = geo_eval.rejection_reason

                    if geo_eval.graphic_classification in ["figure", "table_graphic"] or geo_eval.cell_type == "figure":
                        content_class = geo_eval.graphic_classification if geo_eval.graphic_classification in ["figure", "table_graphic"] else "figure"
                        has_symbol = False
                        graphic_classification = content_class
                    elif not geo_eval.has_real_geometry:
                        content_class = "text_only" if has_text else "empty"
                        has_symbol = False
                        graphic_classification = "not_symbol"
                    else:
                        if geo_eval.graphic_classification == "symbol":
                            content_class = "mixed" if has_text else "symbol_only"
                            has_symbol = True
                            graphic_classification = "symbol"
                        else:
                            content_class = geo_eval.graphic_classification
                            has_symbol = (content_class in ["symbol_only", "mixed"])
                            graphic_classification = content_class
                elif has_pre_sym and not has_visual_source:
                    cell_type = "mixed_cell" if has_text else "symbol_cell"
                    content_class = "mixed" if has_text else "symbol_only"
                    has_symbol = True
                    graphic_classification = "symbol"
                    visual_crop_path = pre_crop_path
                    inner_drawing_bbox = getattr(sym_obj, "inner_drawing_bbox", None) if not isinstance(sym_obj, dict) else sym_obj.get("inner_drawing_bbox")
                    symbol_crop_bbox = getattr(sym_obj, "symbol_crop_bbox", None) if not isinstance(sym_obj, dict) else sym_obj.get("symbol_crop_bbox")
                    crop_margin_mm = 3.0
                    crop_err_reason = None
                    needs_crop = False
                    geo_evidence = True
                    geo_confidence = getattr(sym_obj, "confidence_score", 0.90) if not isinstance(sym_obj, dict) else sym_obj.get("confidence_score", 0.90)
                    evidence_sources = ["pre_extracted_symbol_input"]
                    shape_features = {}
                    text_mask_overlap = 0.0
                    rejection_reason = None
                else:
                    cell_type = "text_cell" if (has_text and not has_visual_source) else ("text_only" if has_text else "empty")
                    content_class = "text_only" if has_text else "empty"
                    has_symbol = False
                    visual_crop_path = None
                    inner_drawing_bbox = None
                    symbol_crop_bbox = None
                    crop_margin_mm = 3.0
                    graphic_classification = "not_symbol"
                    crop_err_reason = None
                    needs_crop = False
                    geo_evidence = False
                    geo_confidence = 0.0
                    evidence_sources = []
                    shape_features = {}
                    text_mask_overlap = 1.0 if has_text else 0.0
                    rejection_reason = "Sin geometría técnica visual"

                # Enforce: figure, table_graphic, text_only, empty, not_symbol generate zero symbols
                if content_class in ["figure", "table_graphic", "text_only", "empty", "not_symbol"]:
                    has_symbol = False

                if has_pre_sym and sym_obj:
                    row_bbox_val = [round(rx0, 4), round(cell_bbox_norm[1], 4), round(rx1, 4), round(cell_bbox_norm[3], 4)]
                    if isinstance(sym_obj, dict):
                        sym_obj["row_index"] = r_idx
                        sym_obj["col_index"] = c_idx
                        sym_obj["cell_bbox"] = cell_bbox_norm
                        sym_obj["row_bbox"] = row_bbox_val
                        sym_obj["layout_context"] = "inside_table"
                    else:
                        setattr(sym_obj, "row_index", r_idx)
                        setattr(sym_obj, "col_index", c_idx)
                        setattr(sym_obj, "cell_bbox", cell_bbox_norm)
                        setattr(sym_obj, "row_bbox", row_bbox_val)
                        setattr(sym_obj, "layout_context", "inside_table")

                sym_id = (pre_sym_id or f"sym_{uuid.uuid4().hex[:10]}") if has_symbol else None
                if has_symbol and sym_id and sym_id not in src_refs:
                    src_refs.append(sym_id)

                confidences.append(cell_conf)

                if is_header_row and raw_cell_text and c_idx < len(headers_list):
                    headers_list[c_idx] = raw_cell_text

                # Crear Celda DTO con auditoría geométrica obligatoria y spans
                cell_dto = ExtractedCellDTO(
                    row_index=r_idx,
                    column_index=c_idx,
                    text=raw_cell_text,
                    normalized_text=clean_cell_text,
                    confidence=round(cell_conf, 3),
                    bbox=cell_bbox_px,
                    bbox_normalized=cell_bbox_norm,
                    is_header=is_header_row,
                    source_text_refs=src_refs,
                    cell_type=cell_type,
                    symbol_id=sym_id,
                    has_symbol=has_symbol,
                    symbol_name=None,
                    crop_image_path=visual_crop_path,
                    inner_drawing_bbox=inner_drawing_bbox,
                    symbol_crop_bbox=symbol_crop_bbox,
                    crop_margin_mm=crop_margin_mm,
                    row_span=row_span,
                    col_span=col_span,
                    graphic_classification=graphic_classification,
                    content_class=content_class,
                    needs_visual_crop=needs_crop,
                    crop_error_reason=crop_err_reason,
                    geometric_evidence=geo_evidence,
                    geometric_confidence=geo_confidence,
                    evidence_sources=evidence_sources,
                    shape_features=shape_features,
                    text_mask_overlap_ratio=text_mask_overlap,
                    rejection_reason=rejection_reason,
                    boundary_evidence=boundary_evidence,
                    border_coverage_ratio=border_cov
                )
                cells_dto.append(cell_dto)

        table_conf = sum(confidences) / len(confidences) if confidences else 0.50
        status = "extracted" if table_conf >= 0.70 else "low_confidence"

        bbox_px = [
            round(rx0 * self.width_px, 1),
            round(ry0 * self.height_px, 1),
            round(rx1 * self.width_px, 1),
            round(ry1 * self.height_px, 1),
        ]

        # =========================================================================
        # FASE 2: DETECCIÓN DE ORIENTACIÓN & EXCLUSIÓN DE TABLAS DE SOLO TEXTO
        # =========================================================================
        symbol_cells = [
            c for c in cells_dto
            if c.has_symbol and c.graphic_classification == "symbol" and c.content_class in {"symbol_only", "mixed"}
        ]

        # Si no existe ningún símbolo en la tabla: descarte estricto del pipeline de simbología
        if not symbol_cells:
            raw_struct = {
                "title": title,
                "headers": headers_list,
                "row_count": num_rows,
                "column_count": num_cols,
                "non_empty_cells": len([c for c in cells_dto if c.text or c.has_symbol]),
                "symbol_cells": 0,
                "total_cells": len(cells_dto),
                "reading_orientation": "none",
                "orientation_confidence": 1.0,
                "orientation_reason": "Tabla puramente textual sin celdas de simbología gráfica detectadas.",
                "grid_source": grid_source,
                "grid_confidence": grid_confidence,
                "physical_grid_detected": physical_grid_detected,
                "x_boundaries": col_bounds,
                "y_boundaries": row_bounds,
                "table_bbox": [round(rx0, 4), round(ry0, 4), round(rx1, 4), round(ry1, 4)]
            }
            return ExtractedTableDTO(
                title=title,
                bbox=bbox_px,
                bbox_normalized=[round(rx0, 4), round(ry0, 4), round(rx1, 4), round(ry1, 4)],
                row_count=num_rows,
                column_count=num_cols,
                confidence=round(table_conf, 3),
                extraction_status=status,
                headers=headers_list,
                cells=cells_dto,
                raw_structure=raw_struct,
                extracted_symbols=[],
                has_symbols=False,
                reading_orientation="none",
                orientation_confidence=1.0,
                orientation_reason="Tabla puramente textual sin celdas de simbología gráfica detectadas.",
                grid_source=grid_source,
                grid_confidence=grid_confidence,
                physical_grid_detected=physical_grid_detected,
                x_boundaries=col_bounds,
                y_boundaries=row_bounds,
                table_bbox=[round(rx0, 4), round(ry0, 4), round(rx1, 4), round(ry1, 4)]
            )

        # Si la tabla contiene símbolos: detectar sentido dominante
        orientation_res = detect_table_reading_orientation(cells_dto, num_rows, num_cols)
        reading_orientation = orientation_res.orientation
        orientation_conf = orientation_res.orientation_confidence
        orientation_reason = orientation_res.orientation_reason

        cells_by_row: Dict[int, List[ExtractedCellDTO]] = defaultdict(list)
        cells_by_col: Dict[int, List[ExtractedCellDTO]] = defaultdict(list)
        for c in cells_dto:
            cells_by_row[c.row_index].append(c)
            cells_by_col[c.column_index].append(c)

        for sym_cell in symbol_cells:
            r_idx = sym_cell.row_index
            c_idx = sym_cell.column_index

            # Recopilar celdas adyacentes según el sentido detectado
            if reading_orientation == "row_major":
                adj_cells = [other for other in cells_by_row[r_idx] if other.column_index > c_idx and other.text.strip()]
                adjacent_dominant_texts = [other.text.strip() for other in adj_cells]
            elif reading_orientation == "col_major":
                adj_cells = [other for other in cells_by_col[c_idx] if other.row_index > r_idx and other.text.strip()]
                adjacent_dominant_texts = [other.text.strip() for other in adj_cells]
            elif reading_orientation == "mixed":
                row_adjs = [other.text.strip() for other in cells_by_row[r_idx] if other.column_index > c_idx and other.text.strip()]
                col_adjs = [other.text.strip() for other in cells_by_col[c_idx] if other.row_index > r_idx and other.text.strip()]
                adjacent_dominant_texts = row_adjs + col_adjs
            else: # undetermined
                adjacent_dominant_texts = []

            col_hdr = headers_list[c_idx] if c_idx < len(headers_list) else ""
            row_hdr = ""

            semantic_data = associate_symbol_semantics_directional(
                dominant_orientation=reading_orientation,
                adjacent_dominant_texts=adjacent_dominant_texts,
                col_header=col_hdr,
                row_header=row_hdr,
                table_subtitles=[],
                table_title=title,
                row_index=r_idx,
                col_index=c_idx,
                category_hint=None,
                orientation_confidence=orientation_conf,
                raw_symbol_text=sym_cell.text
            )

            sym_name = semantic_data["symbol_name"]
            sym_cell.symbol_name = sym_name

            crop_p = sym_cell.crop_image_path
            is_crop_valid = bool(crop_p and (
                os.path.isabs(crop_p) and os.path.exists(crop_p) or
                os.path.exists(os.path.join(actual_crops_dir, os.path.basename(crop_p)))
            ))

            target_crop_box = sym_cell.symbol_crop_bbox or sym_cell.bbox_normalized
            crop_w_mm = round((target_crop_box[2] - target_crop_box[0]) * self.width_px * (25.4 / 150.0), 2)
            crop_h_mm = round((target_crop_box[3] - target_crop_box[1]) * self.height_px * (25.4 / 150.0), 2)

            is_logical_low_conf = (grid_source == "logical_alignment" and grid_confidence < 0.60)
            req_review = semantic_data.get("requires_human_review", False) or is_logical_low_conf
            conf_score = 0.90 if (is_crop_valid and not req_review) else (0.50 if req_review else 0.65)
            validation_notes = (
                "Grilla detectada por alineamiento lógico con baja confianza (<60%); requiere revisión humana obligatoria."
                if is_logical_low_conf
                else (
                    "Orientación de tabla no determinada con suficiente confianza (<60%); requiere revisión y validación humana."
                    if req_review
                    else f"Extraído desde celda tabular (Fila {r_idx}, Col {c_idx}, Sentido: {reading_orientation}, Grilla: {grid_source})"
                )
            )

            sym_dto = ExtractedSymbolCandidateDTO(
                id=sym_cell.symbol_id or f"sym_{uuid.uuid4().hex[:10]}",
                symbol_name=sym_name,
                canonical_symbol_family=semantic_data["canonical_symbol_family"],
                standard_reference=semantic_data["standard_reference"],
                discipline=semantic_data["discipline"],
                category=semantic_data["category"],
                source_render_mode="vector" if any("vector" in s for s in sym_cell.evidence_sources) else "raster",
                layout_context="inside_table",
                context_association_mode=f"directional_{reading_orientation}",
                bbox_normalized=target_crop_box, # Recorte ajustado estrictamente a symbol_crop_bbox (inner_drawing + 3mm)
                estimated_physical_size_mm={
                    "width_mm": crop_w_mm,
                    "height_mm": crop_h_mm,
                    "aspect_ratio": round(crop_w_mm / max(0.1, crop_h_mm), 2)
                },
                crop_image_path=crop_p,
                technical_function=semantic_data["technical_function"],
                aliases=semantic_data["aliases"],
                confidence_score=conf_score,
                human_validation_notes=validation_notes,
                visual_variant_group_id=str(uuid.uuid4()),
                source_table_id=None,
                row_index=r_idx,
                col_index=c_idx,
                cell_bbox=sym_cell.bbox_normalized, # Límite físico completo de la celda
                inner_drawing_bbox=sym_cell.inner_drawing_bbox, # BBox interior del trazo si existe
                symbol_crop_bbox=sym_cell.symbol_crop_bbox or sym_cell.bbox_normalized,
                crop_margin_mm=sym_cell.crop_margin_mm or 3.0,
                row_span=sym_cell.row_span or 1,
                col_span=sym_cell.col_span or 1,
                graphic_classification=sym_cell.graphic_classification or "symbol",
                grid_source=grid_source,
                grid_confidence=grid_confidence,
                physical_grid_detected=physical_grid_detected,
                x_boundaries=col_bounds,
                y_boundaries=row_bounds,
                table_bbox=[round(rx0, 4), round(ry0, 4), round(rx1, 4), round(ry1, 4)],
                row_bbox=[round(rx0, 4), round(sym_cell.bbox_normalized[1], 4), round(rx1, 4), round(sym_cell.bbox_normalized[3], 4)],
                tag_or_code=semantic_data["tag_or_code"],
                symbol_description=semantic_data["symbol_description"],
                needs_visual_crop=not is_crop_valid,
                crop_error_reason=sym_cell.crop_error_reason,
                reading_orientation=reading_orientation,
                orientation_confidence=orientation_conf,
                orientation_reason=orientation_reason,
                requires_human_review=req_review or (sym_cell.text_mask_overlap_ratio > 0.70 and bool(sym_cell.text.strip())) or is_logical_low_conf,
                geometric_evidence=sym_cell.geometric_evidence,
                geometric_confidence=sym_cell.geometric_confidence,
                evidence_sources=sym_cell.evidence_sources,
                shape_features=sym_cell.shape_features,
                text_mask_overlap_ratio=sym_cell.text_mask_overlap_ratio,
                rejection_reason=sym_cell.rejection_reason,
                content_class=sym_cell.content_class,
                boundary_evidence=sym_cell.boundary_evidence,
                border_coverage_ratio=sym_cell.border_coverage_ratio
            )
            extracted_symbols_list.append(sym_dto)

        raw_struct = {
            "title": title,
            "headers": headers_list,
            "row_count": num_rows,
            "column_count": num_cols,
            "non_empty_cells": len([c for c in cells_dto if c.text or c.has_symbol]),
            "symbol_cells": len(extracted_symbols_list),
            "total_cells": len(cells_dto),
            "reading_orientation": reading_orientation,
            "orientation_confidence": orientation_conf,
            "orientation_reason": orientation_reason,
            "grid_source": grid_source,
            "grid_confidence": grid_confidence,
            "physical_grid_detected": physical_grid_detected,
            "x_boundaries": col_bounds,
            "y_boundaries": row_bounds,
            "table_bbox": [round(rx0, 4), round(ry0, 4), round(rx1, 4), round(ry1, 4)]
        }

        return ExtractedTableDTO(
            title=title,
            bbox=bbox_px,
            bbox_normalized=[round(rx0, 4), round(ry0, 4), round(rx1, 4), round(ry1, 4)],
            row_count=num_rows,
            column_count=num_cols,
            confidence=round(table_conf, 3),
            extraction_status=status,
            headers=headers_list,
            cells=cells_dto,
            raw_structure=raw_struct,
            extracted_symbols=extracted_symbols_list,
            has_symbols=True,
            reading_orientation=reading_orientation,
            orientation_confidence=orientation_conf,
            orientation_reason=orientation_reason,
            grid_source=grid_source,
            grid_confidence=grid_confidence,
            physical_grid_detected=physical_grid_detected,
            x_boundaries=col_bounds,
            y_boundaries=row_bounds,
            table_bbox=[round(rx0, 4), round(ry0, 4), round(rx1, 4), round(ry1, 4)]
        )

    def _inspect_and_crop_cell_visual(
        self,
        page: Optional[Any],
        image_path: Optional[str],
        image_bytes: Optional[bytes],
        drawings: Optional[List[Any]],
        cell_bbox_norm: List[float],
        crops_dir: str,
        doc_uid: str,
        r_idx: int,
        c_idx: int,
        has_text: bool = False,
        cell_text: str = ""
    ) -> Tuple[bool, Optional[str], Optional[str], str, Optional[List[float]]]:
        """
        Inspecciona si una celda contiene contenido gráfico real usando GeometricEvidenceValidator.
        Retorna (has_real_geometry, crop_path, rejection_reason, render_mode, inner_drawing_bbox).
        """
        eval_res = self.geometric_validator.evaluate_cell(
            cell_bbox_norm=cell_bbox_norm,
            cell_text=cell_text,
            page=page,
            image_path=image_path,
            image_bytes=image_bytes,
            drawings=drawings,
            crops_dir=crops_dir,
            doc_uid=doc_uid,
            row_index=r_idx,
            col_index=c_idx
        )
        mode = "vector" if any("vector" in s for s in eval_res.evidence_sources) else ("raster" if eval_res.has_real_geometry else "none")
        return (
            eval_res.has_real_geometry,
            eval_res.crop_image_path,
            eval_res.rejection_reason,
            mode,
            eval_res.inner_drawing_bbox
        )
