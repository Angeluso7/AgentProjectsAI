import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from app.db.models.document_memory import ExtractedText, DocumentSheet
from app.db.models.template_memory import TitleBlockTemplate

@dataclass
class LayoutSegment:
    region_type: str                    # title_block, drawing_area, notes_area, legend_area, table_candidate
    bbox: List[float]                   # [x0, y0, x1, y1] en píxeles
    bbox_normalized: List[float]        # [x0, y0, x1, y1] normalizado 0.0 - 1.0
    polygon_points: List[List[float]]   # [[x0,y0], [x1,y1], [x2,y2], [x3,y3]]
    confidence: float                   # 0.0 - 1.0
    detection_method: str               # hybrid_heuristic, anchor_clustering, corner_fallback
    attributes: Dict[str, Any] = field(default_factory=dict)

TITLE_BLOCK_PATTERNS = {
    "sheet_code": [
        r"plano\s*(?:n[°o\.]?|num|c[oó]d(?:igo)?)\s*[:\s]?\s*([a-zA-Z0-9\-_/]+)",
        r"l[aá]mina\s*(?:n[°o\.]?)?\s*[:\s]?\s*([a-zA-Z0-9\-_/]+)",
        r"\b([A-Z]{2,4}-\d{1,3})\b",
        r"\b(PL-\d{1,3})\b"
    ],
    "scale_text": [
        r"esc(?:ala)?\.?\s*[:\s]?\s*(1\s*[:/]\s*\d+|indicadas|s/e|sin escala)",
        r"\b(1\s*[:/]\s*(?:20|25|50|75|100|125|200|250|500))\b"
    ],
    "revision": [
        r"rev(?:isi[oó]n)?\.?\s*[:\s]?\s*([a-zA-Z0-9])\b",
        r"versi[oó]n\s*[:\s]?\s*([a-zA-Z0-9])\b"
    ],
    "date_text": [
        r"fecha\s*[:\s]?\s*([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4}|[a-zA-Z]+\s+[0-9]{4})",
        r"\b([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4})\b"
    ],
    "project_name": [
        r"proyecto\s*[:\s]?\s*([^\n\r]+)",
        r"obra\s*[:\s]?\s*([^\n\r]+)",
        r"edificio\s*[:\s]?\s*([^\n\r]+)"
    ],
    "sheet_title": [
        r"(?:nombre\s*del\s*plano|contenido|t[ií]tulo)\s*[:\s]?\s*([^\n\r]+)",
        r"\b(planta\s+(?:primer|segundo|tercer|cuarto|piso|tipo|general|techumbre|subterr[aá]neo|arquitectura|emplazamiento|accesos)[^\n\r]*)",
        r"\b(elevaci[oó]n\s+[^\n\r]+)",
        r"\b(corte\s+[^\n\r]+)"
    ],
    "discipline": [
        r"\b(arquitectura|estructura[s]?|instalaciones|electricidad|sanitario|climatizaci[oó]n|gas|mep|urbanismo)\b"
    ],
    "drawn_by": [
        r"dibuj(?:o|ante|ó)?\.?\s*[:\s]?\s*([a-zA-Z\.\s]+)",
        r"dib\.?\s*[:\s]?\s*([a-zA-Z\.\s]+)"
    ],
    "checked_by": [
        r"revis(?:o|ó|ado)?\.?\s*[:\s]?\s*([a-zA-Z\.\s]+)",
        r"rev\.?\s*[:\s]?\s*([a-zA-Z\.\s]+)",
        r"calc(?:uló)?\.?\s*[:\s]?\s*([a-zA-Z\.\s]+)"
    ],
    "approved_by": [
        r"aprob(?:o|ó|ado)?\.?\s*[:\s]?\s*([a-zA-Z\.\s]+)",
        r"apr\.?\s*[:\s]?\s*([a-zA-Z\.\s]+)",
        r"v[°o]\s*b[°o]\.?\s*[:\s]?\s*([a-zA-Z\.\s]+)"
    ]
}

NOTES_KEYWORDS = ["notas generales", "notas:", "especificaciones", "notas tecnicas", "notas técnicas", "observaciones", "criterios de diseño"]
LEGEND_KEYWORDS = ["simbologia", "simbología", "leyenda", "abreviaturas", "cuadro de simbolos", "convenciones"]
TABLE_KEYWORDS = ["cuadro de vanos", "cuadro de puertas", "cuadro de ventanas", "cuadro de cargas", "cuadro de superficies", "tabla de", "resumen de"]

def bbox_to_polygon(bbox_norm: List[float]) -> List[List[float]]:
    x0, y0, x1, y1 = bbox_norm
    return [
        [round(x0, 4), round(y0, 4)],
        [round(x1, 4), round(y0, 4)],
        [round(x1, 4), round(y1, 4)],
        [round(x0, 4), round(y1, 4)]
    ]

def normalize_to_pixels(bbox_norm: List[float], width_px: int, height_px: int) -> List[float]:
    x0, y0, x1, y1 = bbox_norm
    return [
        round(x0 * width_px, 2),
        round(y0 * height_px, 2),
        round(x1 * width_px, 2),
        round(y1 * height_px, 2)
    ]

class LayoutAnalyzer:
    """Analizador híbrido de macro-regiones y extractor de metadatos de viñetas."""

    def __init__(self, width_px: int, height_px: int):
        self.width_px = width_px
        self.height_px = height_px

    def segment_layout(self, texts: List[ExtractedText]) -> List[LayoutSegment]:
        """Segmenta la lámina en macro-regiones: title_block, drawing_area, notes_area, legend_area, table_candidate."""
        segments: List[LayoutSegment] = []

        # 1. Detección de Viñeta (Title Block)
        tb_segment = self._detect_title_block_region(texts)
        segments.append(tb_segment)

        # 2. Detección de Notas Generales
        notes_segment = self._detect_keyword_region(texts, NOTES_KEYWORDS, "notes_area")
        if notes_segment:
            segments.append(notes_segment)

        # 3. Detección de Leyendas / Simbología
        legend_segment = self._detect_keyword_region(texts, LEGEND_KEYWORDS, "legend_area")
        if legend_segment:
            segments.append(legend_segment)

        # 4. Detección de Cuadros / Tablas candidatas
        table_segment = self._detect_keyword_region(texts, TABLE_KEYWORDS, "table_candidate")
        if table_segment:
            segments.append(table_segment)

        # 5. Área Principal de Dibujo (Área complementaria dominante)
        drawing_segment = self._compute_drawing_area(segments)
        segments.append(drawing_segment)

        return segments

    def _detect_title_block_region(self, texts: List[ExtractedText]) -> LayoutSegment:
        """Detecta la región de la viñeta buscando clusters de anchors léxicos en el cuadrante inferior derecho."""
        matched_texts: List[ExtractedText] = []
        matched_anchors: List[str] = []

        # Buscar textos en la zona inferior derecha (x >= 0.50, y >= 0.50) o barras perimetrales
        for t in texts:
            if not t.bbox_normalized or len(t.bbox_normalized) < 4:
                continue
            x0, y0, x1, y1 = t.bbox_normalized
            # Zona candidata: Cuadrante inferior derecho o franja inferior
            if (x0 >= 0.50 and y0 >= 0.50) or y0 >= 0.82 or x0 >= 0.75:
                text_lower = (t.text or "").lower()
                for cat, patterns in TITLE_BLOCK_PATTERNS.items():
                    if any(re.search(p, text_lower) for p in patterns):
                        matched_texts.append(t)
                        if cat not in matched_anchors:
                            matched_anchors.append(cat)
                        break

        # Si encontramos al menos 2 anchors agrupados, calculamos la envolvente
        if len(matched_texts) >= 2:
            min_x = min(t.bbox_normalized[0] for t in matched_texts)
            min_y = min(t.bbox_normalized[1] for t in matched_texts)
            max_x = max(t.bbox_normalized[2] for t in matched_texts)
            max_y = max(t.bbox_normalized[3] for t in matched_texts)

            # Agregar margen de resguardo
            pad_x = 0.03
            pad_y = 0.03
            norm_bbox = [
                max(0.0, min_x - pad_x),
                max(0.0, min_y - pad_y),
                min(1.0, max(max_x + pad_x, 0.98)),
                min(1.0, max(max_y + pad_y, 0.98))
            ]
            confidence = min(1.0, 0.60 + 0.08 * len(matched_anchors))
            method = "anchor_clustering"
        else:
            # Fallback a posición geométrica estándar en esquina inferior derecha
            norm_bbox = [0.70, 0.70, 0.98, 0.98]
            confidence = 0.50
            method = "corner_fallback"

        px_bbox = normalize_to_pixels(norm_bbox, self.width_px, self.height_px)
        poly = bbox_to_polygon(norm_bbox)

        return LayoutSegment(
            region_type="title_block",
            bbox=px_bbox,
            bbox_normalized=norm_bbox,
            polygon_points=poly,
            confidence=round(confidence, 3),
            detection_method=method,
            attributes={"matched_anchors": matched_anchors, "anchors_count": len(matched_anchors)}
        )

    def _detect_keyword_region(
        self, texts: List[ExtractedText], keywords: List[str], region_type: str
    ) -> Optional[LayoutSegment]:
        """Detecta una región identificando una cabecera temática y sus elementos adyacentes."""
        header_text: Optional[ExtractedText] = None
        for t in texts:
            t_lower = (t.text or "").lower()
            if any(kw in t_lower for kw in keywords):
                header_text = t
                break

        if not header_text or not header_text.bbox_normalized:
            return None

        hx0, hy0, hx1, hy1 = header_text.bbox_normalized
        # Buscar textos debajo de la cabecera en la misma columna
        related_texts = [
            t for t in texts
            if t.bbox_normalized and t.bbox_normalized[1] >= hy0 and abs(t.bbox_normalized[0] - hx0) <= 0.20
        ]

        if not related_texts:
            norm_bbox = [hx0 - 0.01, hy0 - 0.01, min(1.0, hx1 + 0.15), min(1.0, hy1 + 0.25)]
        else:
            min_x = min(t.bbox_normalized[0] for t in related_texts)
            min_y = min(t.bbox_normalized[1] for t in related_texts)
            max_x = max(t.bbox_normalized[2] for t in related_texts)
            max_y = max(t.bbox_normalized[3] for t in related_texts)
            norm_bbox = [
                max(0.0, min_x - 0.01),
                max(0.0, min_y - 0.01),
                min(1.0, max_x + 0.02),
                min(1.0, max_y + 0.02)
            ]

        px_bbox = normalize_to_pixels(norm_bbox, self.width_px, self.height_px)
        return LayoutSegment(
            region_type=region_type,
            bbox=px_bbox,
            bbox_normalized=norm_bbox,
            polygon_points=bbox_to_polygon(norm_bbox),
            confidence=0.85,
            detection_method="header_keyword",
            attributes={"keyword_detected": header_text.text}
        )

    def _compute_drawing_area(self, existing_segments: List[LayoutSegment]) -> LayoutSegment:
        """Calcula el área principal de dibujo como el espacio central dominante de la lámina."""
        norm_bbox = [0.03, 0.03, 0.97, 0.97]
        px_bbox = normalize_to_pixels(norm_bbox, self.width_px, self.height_px)
        return LayoutSegment(
            region_type="drawing_area",
            bbox=px_bbox,
            bbox_normalized=norm_bbox,
            polygon_points=bbox_to_polygon(norm_bbox),
            confidence=0.95,
            detection_method="sheet_envelope",
            attributes={"description": "Espacio de trabajo gráfico central"}
        )

    def extract_title_block_fields(
        self,
        tb_region: LayoutSegment,
        texts: List[ExtractedText],
        template: Optional[TitleBlockTemplate] = None
    ) -> Dict[str, Any]:
        """Extrae campos estructurados de la viñeta utilizando regex contextual y proximidad espacial."""
        tb_x0, tb_y0, tb_x1, tb_y1 = tb_region.bbox_normalized

        # Filtrar textos dentro o tocando la región de la viñeta
        tb_texts = [
            t for t in texts
            if t.bbox_normalized and
            t.bbox_normalized[2] >= tb_x0 and t.bbox_normalized[0] <= tb_x1 and
            t.bbox_normalized[3] >= tb_y0 and t.bbox_normalized[1] <= tb_y1
        ]

        extracted: Dict[str, Any] = {
            "sheet_code": None,
            "sheet_title": None,
            "revision": None,
            "scale_text": None,
            "date_text": None,
            "project_name": None,
            "discipline": None,
            "drawn_by": None,
            "checked_by": None,
            "approved_by": None,
        }
        matched_anchors: List[str] = []
        raw_fields: Dict[str, str] = {}

        # 1. Extracción por Regex Inline sobre cada texto en la viñeta
        for t in tb_texts:
            text_str = (t.text or "").strip()
            text_clean = (t.clean_text or text_str).strip()

            for field_name, patterns in TITLE_BLOCK_PATTERNS.items():
                if extracted[field_name] is not None:
                    continue  # Ya extraído

                for pat in patterns:
                    m = re.search(pat, text_clean, re.IGNORECASE)
                    if m:
                        val = m.group(1).strip() if m.groups() else text_clean
                        val = re.sub(r"^[:\s\-]+", "", val).strip()
                        if val:
                            extracted[field_name] = val
                            raw_fields[field_name] = text_str
                            if field_name not in matched_anchors:
                                matched_anchors.append(field_name)
                            break

        # 2. Extracción por Adyacencia Espacial (Si el anchor estaba solo en una celda y el valor al lado)
        for t in tb_texts:
            t_str = (t.text or "").lower().strip()
            # Si encontramos etiquetas clave sin valor inline
            for field_name in ["scale_text", "revision", "sheet_code", "date_text"]:
                if extracted[field_name] is not None:
                    continue
                
                is_label = False
                if field_name == "scale_text" and t_str in ["escala", "esc.", "esc:"]:
                    is_label = True
                elif field_name == "revision" and t_str in ["rev", "rev.", "revision", "revisión"]:
                    is_label = True
                elif field_name == "sheet_code" and t_str in ["plano n°", "lamina", "código", "plano:"]:
                    is_label = True
                elif field_name == "date_text" and t_str in ["fecha", "date", "fecha:"]:
                    is_label = True

                if is_label:
                    ax0, ay0, ax1, ay1 = t.bbox_normalized
                    # Buscar vecino derecho o inferior inmediato
                    candidates = [
                        c for c in tb_texts
                        if c.id != t.id and c.bbox_normalized and (
                            (c.bbox_normalized[0] >= ax0 and abs(c.bbox_normalized[1] - ay0) <= 0.03) or
                            (c.bbox_normalized[1] >= ay0 and abs(c.bbox_normalized[0] - ax0) <= 0.06)
                        )
                    ]
                    if candidates:
                        best = candidates[0]
                        val = re.sub(r"^[:\s\-]+", "", best.text or "").strip()
                        if val:
                            extracted[field_name] = val
                            raw_fields[field_name] = f"{t.text} -> {best.text}"
                            if field_name not in matched_anchors:
                                matched_anchors.append(field_name)

        # 3. Normalización y Limpieza de Campos Clave
        if extracted["scale_text"]:
            extracted["scale_text"] = extracted["scale_text"].upper().replace(" ", "")
        if extracted["revision"]:
            extracted["revision"] = extracted["revision"].upper()
        if extracted["discipline"]:
            extracted["discipline"] = extracted["discipline"].lower()

        # 4. Cálculo del Score de Matching
        required_fields = ["sheet_code", "scale_text", "revision"]
        unmatched_req = [f for f in required_fields if not extracted.get(f)]

        # Score ponderado: 0.50 por anchors detectados + 0.30 por campos clave + 0.20 por ubicación
        anchors_ratio = len(matched_anchors) / len(TITLE_BLOCK_PATTERNS)
        keys_ratio = (len(required_fields) - len(unmatched_req)) / len(required_fields)
        match_score = round(0.40 * anchors_ratio + 0.40 * keys_ratio + 0.20, 3)

        status_str = "extracted" if len(unmatched_req) == 0 else "partial" if matched_anchors else "not_found"

        return {
            "fields": extracted,
            "matched_anchors": matched_anchors,
            "unmatched_required_fields": unmatched_req,
            "raw_fields": raw_fields,
            "match_score": match_score,
            "extraction_status": status_str
        }
