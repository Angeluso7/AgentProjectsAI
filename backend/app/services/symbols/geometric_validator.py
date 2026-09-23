import os
import re
import math
import uuid
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from PIL import Image
import numpy as np

from app.core.settings import settings
from app.core.logging import logger

try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False

# Factor estándar: 1 pt (PDF) = 25.4 / 72 mm = 0.352777 mm
PT_TO_MM = 25.4 / 72.0

# Expresión regular para patrones estrictamente alfanuméricos cortos (glifos tipográficos aislados)
ALPHANUMERIC_TOKEN_REGEX = re.compile(
    r"^(?:[A-Z0-9]{1,4}|[A-Z]\d|\d[A-Z]|[A-Z]\-[0-9]{1,2}|SI|NO|OK|N\/A|\-|\-\-|\—|\—\—|\*|\#|\?)$",
    re.IGNORECASE
)


@dataclass
class CellGeometricEvaluation:
    """Resultado de la evaluación geométrica exhaustiva de una celda o región técnica."""
    has_real_geometry: bool
    cell_type: str                        # "text_only", "symbol_only", "mixed", "empty", "figure"
    geometric_confidence: float          # 0.0 a 1.0
    evidence_sources: List[str]          # ["vector_curves", "vector_circles", "raster_contours", etc.]
    shape_features: Dict[str, Any]       # Métricas geométricas extraídas
    text_mask_overlap_ratio: float       # 0.0 a 1.0 (1.0 = 100% de la tinta coincide con texto OCR)
    cell_bbox: List[float]               # [x0, y0, x1, y1] normalizado
    inner_drawing_bbox: Optional[List[float]] = None
    symbol_crop_bbox: Optional[List[float]] = None
    crop_margin_mm: float = 3.0
    graphic_classification: str = "symbol"  # "symbol", "figure", "table_graphic", "not_symbol", "requires_human_review"
    crop_image_path: Optional[str] = None
    rejection_reason: Optional[str] = None
    needs_visual_crop: bool = False
    requires_human_review: bool = False


class GeometricEvidenceValidator:
    """
    Validador estricto de evidencia geométrica visual para simbología de ingeniería.
    Regla fundamental del sistema:
    GEOMETRÍA VISUAL VÁLIDA -> símbolo candidato -> OCR/contexto para enriquecimiento.
    NUNCA operar como: OCR breve o posición de celda -> símbolo candidato.

    Verifica:
    1. Evidencia local a la celda (NUNCA a la página completa).
    2. Separación vectorial y raster de texto vs gráfico:
       - Eliminación de líneas perimetrales de cuadrícula de la tabla.
       - Eliminación de fondos rectangulares uniformes.
       - Enmascaramiento de regiones de texto OCR (text mask).
       - Descarte de glifos alfanuméricos aislados (A/B/C/X/O/1/0, códigos, palabras).
    3. Detección positiva de curvas, arcos, círculos, polígonos, flechas y trazos conectados.
    """


def compute_symbol_crop_bbox(
    cell_bbox_norm: List[float],
    inner_drawing_bbox: Optional[List[float]],
    margin_mm: float = 3.0,
    pw: float = 800.0,
    ph: float = 600.0
) -> List[float]:
    """
    Calcula symbol_crop_bbox = inner_drawing_bbox + 3 mm,
    limitado siempre al interior de cell_bbox para no invadir celdas contiguas.
    Conversión: 3 mm = 3 * 72 / 25.4 = 8.50394 pt.
    """
    if not inner_drawing_bbox or len(inner_drawing_bbox) < 4:
        return list(cell_bbox_norm)

    c_x0, c_y0, c_x1, c_y1 = cell_bbox_norm
    i_x0, i_y0, i_x1, i_y1 = inner_drawing_bbox

    margin_pt = margin_mm * (72.0 / 25.4)
    dx = margin_pt / max(1.0, pw)
    dy = margin_pt / max(1.0, ph)

    s_x0 = max(c_x0, i_x0 - dx)
    s_y0 = max(c_y0, i_y0 - dy)
    s_x1 = min(c_x1, i_x1 + dx)
    s_y1 = min(c_y1, i_y1 + dy)

    return [round(s_x0, 4), round(s_y0, 4), round(s_x1, 4), round(s_y1, 4)]


def compute_occurrence_context_crop_bbox(
    symbol_crop_bbox_norm: List[float],
    margin_mm: float = 15.0,
    page_bbox_norm: Optional[List[float]] = None,
    pw: float = 800.0,
    ph: float = 600.0
) -> List[float]:
    """
    Calcula occurrence_context_crop_bbox = symbol_crop_bbox + 15 mm,
    limitado siempre a page_bbox ([0.0, 0.0, 1.0, 1.0] normalizado) para no salirse de la lámina.
    Conversión: 15 mm = 15 * 72 / 25.4 = 42.5197 pt.
    """
    if not symbol_crop_bbox_norm or len(symbol_crop_bbox_norm) < 4:
        return [0.0, 0.0, 1.0, 1.0]

    p_limit = page_bbox_norm or [0.0, 0.0, 1.0, 1.0]
    p_x0, p_y0, p_x1, p_y1 = p_limit
    s_x0, s_y0, s_x1, s_y1 = symbol_crop_bbox_norm

    margin_pt = margin_mm * (72.0 / 25.4)
    dx = margin_pt / max(1.0, pw)
    dy = margin_pt / max(1.0, ph)

    ctx_x0 = max(p_x0, s_x0 - dx)
    ctx_y0 = max(p_y0, s_y0 - dy)
    ctx_x1 = min(p_x1, s_x1 + dx)
    ctx_y1 = min(p_y1, s_y1 + dy)

    return [round(ctx_x0, 4), round(ctx_y0, 4), round(ctx_x1, 4), round(ctx_y1, 4)]


class GeometricEvidenceValidator:
    """
    Validador de Evidencia Geométrica Visual para Extracción de Simbología.
    """

    def __init__(self, width_px: int = 8000, height_px: int = 6000):
        self.width_px = width_px
        self.height_px = height_px

    compute_symbol_crop_bbox = staticmethod(compute_symbol_crop_bbox)
    compute_occurrence_context_crop_bbox = staticmethod(compute_occurrence_context_crop_bbox)

    def evaluate_cell(
        self,
        cell_bbox_norm: List[float],
        cell_text: str = "",
        page: Optional[Any] = None,
        image_path: Optional[str] = None,
        image_bytes: Optional[bytes] = None,
        drawings: Optional[List[Any]] = None,
        known_text_bboxes_norm: Optional[List[List[float]]] = None,
        crops_dir: Optional[str] = None,
        doc_uid: str = "doc",
        row_index: int = 0,
        col_index: int = 0
    ) -> CellGeometricEvaluation:
        """
        Evalúa localmente si una celda contiene geometría visual real compatible con simbología.
        """
        c_x0, c_y0, c_x1, c_y1 = cell_bbox_norm
        cell_w_norm = max(0.0001, c_x1 - c_x0)
        cell_h_norm = max(0.0001, c_y1 - c_y0)

        # Sanitizar texto de celda
        clean_text = " ".join(cell_text.split()).strip()
        has_text = bool(clean_text)

        # 0. Dimensiones mínimas requeridas para que una celda contenga algo
        if cell_w_norm < 0.003 or cell_h_norm < 0.003:
            return CellGeometricEvaluation(
                has_real_geometry=False,
                cell_type="empty",
                geometric_confidence=0.0,
                evidence_sources=[],
                shape_features={"reason": "cell_too_small"},
                text_mask_overlap_ratio=1.0 if has_text else 0.0,
                cell_bbox=cell_bbox_norm,
                rejection_reason="Dimensiones de celda insuficientes (<0.3%)",
                needs_visual_crop=False
            )

        # 1. Evaluación Vectorial Local (si page o drawings está disponible)
        vector_result = self._evaluate_vector_geometry(
            page=page,
            drawings=drawings,
            cell_bbox_norm=cell_bbox_norm,
            clean_text=clean_text,
            known_text_bboxes=known_text_bboxes_norm
        )

        # 2. Evaluación Raster / Píxeles Local
        raster_result = self._evaluate_raster_geometry(
            page=page,
            image_path=image_path,
            image_bytes=image_bytes,
            cell_bbox_norm=cell_bbox_norm,
            clean_text=clean_text,
            known_text_bboxes=known_text_bboxes_norm,
            crops_dir=crops_dir,
            doc_uid=doc_uid,
            row_index=row_index,
            col_index=col_index
        )

        # Integrar evidencias vectoriales y raster locales
        has_vector_geo = vector_result["has_real_geometry"]
        has_raster_geo = raster_result["has_real_geometry"]
        has_real_geometry = has_vector_geo or has_raster_geo

        # Si vectorialmente se detectó como puro glifo alfanumérico o borde de grilla,
        # y no hay evidencia de imagen raster incrustada localmente en la celda
        if vector_result.get("is_strictly_text_or_grid") and not raster_result.get("has_local_embedded_image"):
            has_real_geometry = False

        # Si el raster confirma que la tinta corresponde a texto OCR o celda vacía,
        # y no hay geometría vectorial válida independiente
        if raster_result.get("is_strictly_text_or_empty") and not has_vector_geo:
            has_real_geometry = False

        # Si el texto de la celda es un token alfanumérico corto (A, B, C, X, O, 1, 0, códigos breves)
        # y no hay componentes gráficos independientes de tamaño técnico
        if has_text and ALPHANUMERIC_TOKEN_REGEX.match(clean_text) and not has_vector_geo and not raster_result.get("has_local_embedded_image"):
            has_real_geometry = False

        # Fusionar fuentes de evidencia
        evidence_sources = list(set(vector_result["evidence_sources"] + raster_result["evidence_sources"]))
        shape_features = {
            **vector_result["shape_features"],
            **raster_result["shape_features"],
            "has_vector_geometry": has_vector_geo,
            "has_raster_geometry": has_raster_geo
        }
        text_mask_overlap = raster_result.get("text_mask_overlap_ratio", 1.0 if has_text else 0.0)

        # Calcular confianza geométrica
        if has_real_geometry:
            conf_vector = vector_result.get("confidence", 0.0)
            conf_raster = raster_result.get("confidence", 0.0)
            if has_vector_geo and has_raster_geo:
                geometric_conf = round(min(0.98, max(conf_vector, conf_raster) + 0.05), 3)
            else:
                geometric_conf = round(max(conf_vector, conf_raster), 3)
        else:
            geometric_conf = 0.0

        # Calcular inner_drawing_bbox: preferir vectorial sobre raster
        inner_drawing_bbox = vector_result.get("inner_drawing_bbox") or raster_result.get("inner_drawing_bbox")

        # Calcular symbol_crop_bbox si hay geometría
        pw = float(page.rect.width) if page else float(self.width_px)
        ph = float(page.rect.height) if page else float(self.height_px)
        symbol_crop_bbox = None
        if has_real_geometry and inner_drawing_bbox:
            symbol_crop_bbox = self.compute_symbol_crop_bbox(
                cell_bbox_norm=cell_bbox_norm,
                inner_drawing_bbox=inner_drawing_bbox,
                margin_mm=3.0,
                pw=pw,
                ph=ph
            )

        # Clasificación gráfica: symbol, figure, table_graphic, not_symbol, requires_human_review
        graphic_classification = "not_symbol"
        rejection_reason = None
        is_waveform = (
            shape_features.get("is_waveform_or_chart", False)
            or "vector_waveform_or_chart" in evidence_sources
            or "raster_waveform_or_chart" in evidence_sources
        )

        if has_real_geometry:
            if is_waveform:
                graphic_classification = "figure"
                cell_type = "figure"
                rejection_reason = "Gráfico técnico tipo forma de onda o diagrama, clasificado como figura"
                has_real_geometry = False
            elif geometric_conf < 0.60:
                graphic_classification = "requires_human_review"
                cell_type = "symbol_only" if not has_text else "mixed"
            else:
                graphic_classification = "symbol"
                cell_type = "symbol_only" if not has_text else "mixed"
        else:
            cell_type = "text_only" if has_text else "empty"

        # Razón de rechazo si no hay geometría
        if not has_real_geometry and not rejection_reason:
            if has_text:
                if ALPHANUMERIC_TOKEN_REGEX.match(clean_text):
                    rejection_reason = f"Celda alfanumérica pura ('{clean_text}') sin geometría técnica"
                else:
                    rejection_reason = vector_result.get("rejection_reason") or raster_result.get("rejection_reason") or "Celda puramente textual"
            else:
                rejection_reason = vector_result.get("rejection_reason") or raster_result.get("rejection_reason") or "Celda vacía sin trazos gráficos"

        # Generar crop visual ajustado a symbol_crop_bbox (inner_drawing_bbox + 3mm)
        crop_path = None
        needs_crop = False
        target_crop_bbox = symbol_crop_bbox or cell_bbox_norm

        can_generate_crop = has_real_geometry or (graphic_classification in ["figure", "table_graphic"] and bool(inner_drawing_bbox))
        if can_generate_crop and crops_dir:
            os.makedirs(crops_dir, exist_ok=True)
            prefix = "fig_crop" if graphic_classification == "figure" else "sym_crop"
            crop_filename = f"{prefix}_{doc_uid}_r{row_index}_c{col_index}_{uuid.uuid4().hex[:6]}.png"
            full_crop_path = os.path.join(crops_dir, crop_filename)
            s_x0, s_y0, s_x1, s_y1 = target_crop_bbox

            if page is not None:
                try:
                    import fitz
                    clip_rect = fitz.Rect(s_x0 * pw, s_y0 * ph, s_x1 * pw, s_y1 * ph)
                    pix = page.get_pixmap(dpi=150, clip=clip_rect)
                    pix.save(full_crop_path)
                    crop_path = f"/data/crops/symbols/{crop_filename}"
                except Exception:
                    crop_path = None
            elif image_path and os.path.exists(image_path):
                try:
                    from PIL import Image
                    full_img = Image.open(image_path)
                    w_px, h_px = full_img.size
                    crop_pil = full_img.crop((int(s_x0 * w_px), int(s_y0 * h_px), int(s_x1 * w_px), int(s_y1 * h_px)))
                    crop_pil.save(full_crop_path, format="PNG")
                    crop_path = f"/data/crops/symbols/{crop_filename}"
                except Exception:
                    crop_path = None
            elif image_bytes:
                try:
                    import io
                    from PIL import Image
                    full_img = Image.open(io.BytesIO(image_bytes))
                    w_px, h_px = full_img.size
                    crop_pil = full_img.crop((int(s_x0 * w_px), int(s_y0 * h_px), int(s_x1 * w_px), int(s_y1 * h_px)))
                    crop_pil.save(full_crop_path, format="PNG")
                    crop_path = f"/data/crops/symbols/{crop_filename}"
                except Exception:
                    crop_path = None

        if has_real_geometry and not crop_path:
            needs_crop = True

        requires_review = (has_real_geometry and geometric_conf < 0.60) or (
            has_text and has_real_geometry and text_mask_overlap > 0.70
        ) or (graphic_classification == "requires_human_review")

        return CellGeometricEvaluation(
            has_real_geometry=has_real_geometry,
            cell_type=cell_type,
            geometric_confidence=geometric_conf,
            evidence_sources=evidence_sources,
            shape_features=shape_features,
            text_mask_overlap_ratio=round(text_mask_overlap, 3),
            cell_bbox=cell_bbox_norm,
            inner_drawing_bbox=inner_drawing_bbox,
            symbol_crop_bbox=symbol_crop_bbox,
            crop_margin_mm=3.0,
            graphic_classification=graphic_classification,
            crop_image_path=crop_path,
            rejection_reason=rejection_reason,
            needs_visual_crop=needs_crop,
            requires_human_review=requires_review
        )

    def _evaluate_vector_geometry(
        self,
        page: Optional[Any],
        drawings: Optional[List[Any]],
        cell_bbox_norm: List[float],
        clean_text: str,
        known_text_bboxes: Optional[List[List[float]]]
    ) -> Dict[str, Any]:
        """
        Inspecciona trazos vectoriales locales a la celda en PyMuPDF:
        - Descarta líneas de grilla perimetrales.
        - Descarta rectángulos de fondo uniforme de celda.
        - Descarta glifos vectoriales que coinciden exactamente con texto tipográfico.
        - Detecta curvas, arcos, círculos, polígonos, flechas y líneas no perimetrales.
        """
        c_x0, c_y0, c_x1, c_y1 = cell_bbox_norm
        has_text = bool(clean_text)

        if not page and drawings is None:
            return {
                "has_real_geometry": False,
                "confidence": 0.0,
                "evidence_sources": [],
                "shape_features": {},
                "inner_drawing_bbox": None,
                "rejection_reason": "Sin datos vectoriales",
                "is_strictly_text_or_grid": False
            }

        try:
            pw = page.rect.width if page else self.width_px
            ph = page.rect.height if page else self.height_px

            x0 = max(0.0, c_x0 * pw)
            y0 = max(0.0, c_y0 * ph)
            x1 = min(pw, c_x1 * pw)
            y1 = min(ph, c_y1 * ph)
            cell_w = max(1.0, x1 - x0)
            cell_h = max(1.0, y1 - y0)

            # Margen interior estricto para ignorar líneas divisorias de la cuadrícula
            pad_x = max(2.5, min(6.0, cell_w * 0.08))
            pad_y = max(2.5, min(6.0, cell_h * 0.08))

            import fitz
            cell_rect = fitz.Rect(x0, y0, x1, y1)
            inner_rect = fitz.Rect(x0 + pad_x, y0 + pad_y, x1 - pad_x, y1 - pad_y)

            page_drawings = drawings if drawings is not None else (page.get_drawings() if page else [])
            if not page_drawings:
                return {
                    "has_real_geometry": False,
                    "confidence": 0.0,
                    "evidence_sources": [],
                    "shape_features": {"vector_paths_count": 0},
                    "inner_drawing_bbox": None,
                    "rejection_reason": "Página sin trazos vectoriales",
                    "is_strictly_text_or_grid": False
                }

            # Filtrar trazos que intersecten el interior de la celda
            inner_drawings = []
            for d in page_drawings:
                dr = d.get("rect")
                if not dr:
                    continue
                # Las líneas horizontales o verticales tienen width==0 o height==0 (is_empty)
                # Expandir con un pequeño margen para que intersects funcione correctamente en PyMuPDF
                eff_dr = fitz.Rect(dr.x0 - 0.75, dr.y0 - 0.75, dr.x1 + 0.75, dr.y1 + 0.75)
                if not eff_dr.intersects(inner_rect):
                    continue

                # 1. Filtro de Líneas Perimetrales de Grilla (incluso gruesas, hasta 10 pt)
                is_grid_line = False
                max_grid_thickness = max(10.0, pad_x * 2.5)
                if dr.width >= cell_w * 0.45 and dr.height <= max_grid_thickness:
                    if abs(dr.y0 - y0) <= pad_y * 2.5 or abs(dr.y1 - y1) <= pad_y * 2.5 or dr.y0 <= y0 + 1.5 or dr.y1 >= y1 - 1.5:
                        is_grid_line = True
                elif dr.height >= cell_h * 0.45 and dr.width <= max_grid_thickness:
                    if abs(dr.x0 - x0) <= pad_x * 2.5 or abs(dr.x1 - x1) <= pad_x * 2.5 or dr.x0 <= x0 + 1.5 or dr.x1 >= x1 - 1.5:
                        is_grid_line = True

                # 2. Filtro de Fondo de Celda
                is_cell_background = False
                if d.get("fill") is not None and dr.width >= cell_w * 0.80 and dr.height >= cell_h * 0.80:
                    is_cell_background = True

                # 3. Filtro de Líneas Globales de Continuidad o que se extienden fuera de la celda
                is_continuity_or_infinite = (
                    dr.x0 < (cell_rect.x0 - 2.5) or dr.x1 > (cell_rect.x1 + 2.5) or
                    dr.y0 < (cell_rect.y0 - 2.5) or dr.y1 > (cell_rect.y1 + 2.5) or
                    dr.width > cell_w * 1.2 or dr.height > cell_h * 1.2
                )

                if is_grid_line or is_cell_background or is_continuity_or_infinite:
                    continue

                inner_drawings.append(d)

            if not inner_drawings:
                return {
                    "has_real_geometry": False,
                    "confidence": 0.0,
                    "evidence_sources": [],
                    "shape_features": {"inner_drawings_count": 0},
                    "inner_drawing_bbox": None,
                    "rejection_reason": "Solo líneas de grilla o fondo de celda",
                    "is_strictly_text_or_grid": True
                }

            # Analizar los trazos internos encontrados
            curve_count = 0
            line_count = 0
            rect_count = 0
            circle_count = 0
            total_items = 0
            valid_geom_rects = []

            for d in inner_drawings:
                dr = d.get("rect")
                if not dr:
                    continue

                items = d.get("items", [])
                total_items += len(items)
                has_curve_in_d = False

                for it in items:
                    it_type = it[0]
                    if it_type == "c":
                        curve_count += 1
                        has_curve_in_d = True
                    elif it_type == "l":
                        line_count += 1
                    elif it_type in ("re", "qu"):
                        rect_count += 1

                aspect = dr.width / max(0.1, dr.height)
                if has_curve_in_d and 0.7 <= aspect <= 1.4 and (dr.width >= 4.0 or dr.height >= 4.0):
                    circle_count += 1

                valid_geom_rects.append(dr)

            u_x0 = min(r.x0 for r in valid_geom_rects)
            u_y0 = min(r.y0 for r in valid_geom_rects)
            u_x1 = max(r.x1 for r in valid_geom_rects)
            u_y1 = max(r.y1 for r in valid_geom_rects)
            geom_w_pt = u_x1 - u_x0
            geom_h_pt = u_y1 - u_y0
            geom_w_mm = geom_w_pt * PT_TO_MM
            geom_h_mm = geom_h_pt * PT_TO_MM
            geom_max_mm = max(geom_w_mm, geom_h_mm)

            # 4. FILTRO ESTRICTO ANTI-GLIFOS TIPOGRÁFICOS ALFANUMÉRICOS
            is_font_glyph = False
            glyph_reason = ""

            if has_text and ALPHANUMERIC_TOKEN_REGEX.match(clean_text):
                if geom_h_mm <= 5.5 and geom_w_mm <= 8.0:
                    is_font_glyph = True
                    glyph_reason = f"Glifo vectorial alfanumérico coincide con '{clean_text}' ({geom_h_mm:.1f} mm altura)"

            if not has_text and geom_h_mm <= 3.8 and geom_w_mm <= 3.8 and total_items <= 4:
                is_font_glyph = True
                glyph_reason = f"Trazo vectorial diminuto aislado de tamaño tipográfico ({geom_h_mm:.1f} mm)"

            if has_text and not is_font_glyph and len(clean_text) > 4:
                if circle_count == 0 and curve_count == 0 and geom_h_mm <= 4.5:
                    is_font_glyph = True
                    glyph_reason = "Trazos vectoriales corresponden a renglón de texto tipográfico"

            if is_font_glyph:
                return {
                    "has_real_geometry": False,
                    "confidence": 0.0,
                    "evidence_sources": [],
                    "shape_features": {
                        "curve_count": curve_count,
                        "line_count": line_count,
                        "circle_count": circle_count,
                        "geom_w_mm": round(geom_w_mm, 2),
                        "geom_h_mm": round(geom_h_mm, 2)
                    },
                    "inner_drawing_bbox": None,
                    "rejection_reason": glyph_reason,
                    "is_strictly_text_or_grid": True
                }

            # 5. VERIFICACIÓN POSITIVA DE GEOMETRÍA SIMBÓLICA TÉCNICA
            has_symbolic_geometry = False
            evidence_sources = []

            if circle_count >= 1:
                has_symbolic_geometry = True
                evidence_sources.append("vector_circle_or_arc")
            elif curve_count >= 2 and geom_max_mm >= 3.0:
                has_symbolic_geometry = True
                evidence_sources.append("vector_bezier_curves")
            elif line_count >= 2 and geom_max_mm >= 3.5:
                has_symbolic_geometry = True
                evidence_sources.append("vector_multi_stroke_structure")
            elif rect_count >= 1 and (line_count >= 1 or curve_count >= 1) and geom_max_mm >= 3.5:
                has_symbolic_geometry = True
                evidence_sources.append("vector_composite_fixture")
            elif rect_count >= 1 and geom_max_mm >= 4.0 and geom_max_mm <= max(cell_w, cell_h) * 0.70 * PT_TO_MM:
                has_symbolic_geometry = True
                evidence_sources.append("vector_fixture_polygon")

            conf = 0.0
            if has_symbolic_geometry:
                if circle_count >= 1 or (curve_count >= 2 and line_count >= 1):
                    conf = 0.94
                elif line_count >= 3:
                    conf = 0.88
                else:
                    conf = 0.78

            inner_norm = [
                round(u_x0 / pw, 4),
                round(u_y0 / ph, 4),
                round(u_x1 / pw, 4),
                round(u_y1 / ph, 4)
            ]

            # Detección de gráfico técnico tipo forma de onda / diagrama
            is_waveform_or_chart = False
            aspect = round(geom_w_pt / max(0.1, geom_h_pt), 2)
            if curve_count >= 5 and geom_w_pt >= cell_w * 0.55 and aspect >= 2.2:
                is_waveform_or_chart = True
                evidence_sources.append("vector_waveform_or_chart")
            elif line_count >= 8 and total_items >= 10 and geom_w_pt >= cell_w * 0.65 and aspect >= 2.0:
                is_waveform_or_chart = True
                evidence_sources.append("vector_waveform_or_chart")

            return {
                "has_real_geometry": has_symbolic_geometry or is_waveform_or_chart,
                "confidence": conf,
                "evidence_sources": evidence_sources,
                "shape_features": {
                    "curve_count": curve_count,
                    "line_count": line_count,
                    "rect_count": rect_count,
                    "circle_count": circle_count,
                    "total_vector_items": total_items,
                    "geom_width_mm": round(geom_w_mm, 2),
                    "geom_height_mm": round(geom_h_mm, 2),
                    "aspect_ratio": aspect,
                    "is_waveform_or_chart": is_waveform_or_chart
                },
                "inner_drawing_bbox": inner_norm if (has_symbolic_geometry or is_waveform_or_chart) else None,
                "rejection_reason": None if (has_symbolic_geometry or is_waveform_or_chart) else "Trazos insuficientes para constituir símbolo técnico",
                "is_strictly_text_or_grid": False
            }

        except Exception as e:
            logger.warning(f"Error evaluando geometría vectorial en celda: {e}")
            return {
                "has_real_geometry": False,
                "confidence": 0.0,
                "evidence_sources": [],
                "shape_features": {"error": str(e)},
                "inner_drawing_bbox": None,
                "rejection_reason": f"Fallo vectorial: {e}",
                "is_strictly_text_or_grid": False
            }

    def _evaluate_raster_geometry(
        self,
        page: Optional[Any],
        image_path: Optional[str],
        image_bytes: Optional[bytes],
        cell_bbox_norm: List[float],
        clean_text: str,
        known_text_bboxes: Optional[List[List[float]]],
        crops_dir: Optional[str],
        doc_uid: str,
        row_index: int,
        col_index: int
    ) -> Dict[str, Any]:
        """
        Inspecciona los píxeles raster locales a la celda (100% independiente de page.get_images global).
        """
        c_x0, c_y0, c_x1, c_y1 = cell_bbox_norm
        has_text = bool(clean_text)

        actual_crops_dir = crops_dir or os.path.join(settings.STORAGE_LOCAL_ROOT, "crops", "symbols")
        os.makedirs(actual_crops_dir, exist_ok=True)

        # 0. Detección de PDF digital e inspección de imágenes incrustadas locales (Requisito 2)
        has_local_embedded_image = False
        is_digital_pdf = False
        cell_rect_fitz = None
        pw = float(self.width_px)
        ph = float(self.height_px)

        if page is not None:
            try:
                import fitz
                pw, ph = float(page.rect.width), float(page.rect.height)
                x0_pt = max(0.0, c_x0 * pw)
                y0_pt = max(0.0, c_y0 * ph)
                x1_pt = min(pw, c_x1 * pw)
                y1_pt = min(ph, c_y1 * ph)
                cell_rect_fitz = fitz.Rect(x0_pt, y0_pt, x1_pt, y1_pt)

                # Un PDF es digital si tiene texto nativo o trazos vectoriales en la página
                page_drawings = page.get_drawings()
                page_text = page.get_text()
                if (page_drawings and len(page_drawings) > 0) or (page_text and len(page_text.strip()) > 0):
                    is_digital_pdf = True

                # Validar evidencia de imagen LOCAL a la celda (NO usar page.get_images() global)
                for img_info in page.get_image_info(xrefs=True):
                    img_bbox = img_info.get("bbox")
                    if not img_bbox:
                        continue
                    img_rect = fitz.Rect(img_bbox)
                    # Descartar imagen de fondo de página completa (> 80% ancho y alto)
                    if img_rect.width >= pw * 0.80 and img_rect.height >= ph * 0.80:
                        continue
                    if img_rect.intersects(cell_rect_fitz):
                        has_local_embedded_image = True
                        break
            except Exception as pe:
                logger.debug(f"Aviso inspeccionando imágenes en fitz.Page: {pe}")

        img_pil = None

        # 1. Obtener imagen de la celda: Preferir renderizar fitz.Page en la región de la celda
        if page is not None and cell_rect_fitz is not None:
            try:
                import fitz
                pix = page.get_pixmap(clip=cell_rect_fitz, dpi=200)
                import io
                img_pil = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
            except Exception as pe:
                logger.debug(f"Aviso extrayendo píxeles de fitz.Page: {pe}")
                img_pil = None

        if img_pil is None:
            if image_path and os.path.exists(image_path):
                try:
                    full_img = Image.open(image_path).convert("RGB")
                    w_px, h_px = full_img.size
                    x0 = int(c_x0 * w_px)
                    y0 = int(c_y0 * h_px)
                    x1 = int(c_x1 * w_px)
                    y1 = int(c_y1 * h_px)
                    img_pil = full_img.crop((x0, y0, x1, y1))
                except Exception:
                    img_pil = None
            elif image_bytes:
                try:
                    import io
                    full_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
                    w_px, h_px = full_img.size
                    x0 = int(c_x0 * w_px)
                    y0 = int(c_y0 * h_px)
                    x1 = int(c_x1 * w_px)
                    y1 = int(c_y1 * h_px)
                    img_pil = full_img.crop((x0, y0, x1, y1))
                except Exception:
                    img_pil = None

        if img_pil is None:
            return {
                "has_real_geometry": False,
                "has_local_embedded_image": False,
                "confidence": 0.0,
                "evidence_sources": [],
                "shape_features": {},
                "text_mask_overlap_ratio": 1.0 if has_text else 0.0,
                "inner_drawing_bbox": None,
                "crop_image_path": None,
                "rejection_reason": "No se pudo obtener imagen de la celda",
                "is_strictly_text_or_empty": True
            }

        crop_w, crop_h = img_pil.size
        if crop_w < 5 or crop_h < 5:
            return {
                "has_real_geometry": False,
                "has_local_embedded_image": False,
                "confidence": 0.0,
                "evidence_sources": [],
                "shape_features": {"crop_w": crop_w, "crop_h": crop_h},
                "text_mask_overlap_ratio": 1.0 if has_text else 0.0,
                "inner_drawing_bbox": None,
                "crop_image_path": None,
                "rejection_reason": "Recorte de celda diminuto",
                "is_strictly_text_or_empty": True
            }

        gray = np.array(img_pil.convert("L"))
        binary = (gray < 205).astype(np.uint8) * 255

        # 3. Eliminar líneas de grilla perimetrales en los 4 bordes del recorte de la celda
        pad_px_x = max(6, int(crop_w * 0.08))
        pad_px_y = max(6, int(crop_h * 0.08))

        inner_mask = np.zeros_like(binary)
        inner_mask[pad_px_y:crop_h - pad_px_y, pad_px_x:crop_w - pad_px_x] = 255
        inner_binary = cv2.bitwise_and(binary, inner_mask) if OPENCV_AVAILABLE else (binary * (inner_mask > 0))

        total_inner_pixels = max(1, (crop_w - 2 * pad_px_x) * (crop_h - 2 * pad_px_y))
        dark_pixel_count = int(np.sum(inner_binary > 0))
        dark_ratio = dark_pixel_count / total_inner_pixels

        # Si el interior está vacío de píxeles oscuros (< 15 píxeles o < 0.3%)
        if dark_pixel_count < 15 or dark_ratio < 0.003:
            return {
                "has_real_geometry": False,
                "has_local_embedded_image": False,
                "confidence": 0.0,
                "evidence_sources": [],
                "shape_features": {"dark_pixel_count": dark_pixel_count, "dark_ratio": round(dark_ratio, 4)},
                "text_mask_overlap_ratio": 0.0,
                "inner_drawing_bbox": None,
                "crop_image_path": None,
                "rejection_reason": "Celda vacía (sin tinta oscura en región interior)",
                "is_strictly_text_or_empty": True
            }

        # 4. Máscara de Texto OCR / Text Mask obligatoria (Requisito 3)
        text_mask = np.zeros_like(inner_binary)
        text_rects_to_mask = []
        cell_x0_pt = c_x0 * pw
        cell_y0_pt = c_y0 * ph
        cell_w_pt = max(1.0, (c_x1 - c_x0) * pw)
        cell_h_pt = max(1.0, (c_y1 - c_y0) * ph)

        if page is not None and cell_rect_fitz is not None:
            try:
                words = page.get_text("words", clip=cell_rect_fitz)
                for w in words:
                    text_rects_to_mask.append((w[0], w[1], w[2], w[3]))
            except Exception:
                pass

        if known_text_bboxes:
            import fitz
            for tb in known_text_bboxes:
                tb_x0 = tb[0] * pw
                tb_y0 = tb[1] * ph
                tb_x1 = tb[2] * pw
                tb_y1 = tb[3] * ph
                if cell_rect_fitz and fitz.Rect(tb_x0, tb_y0, tb_x1, tb_y1).intersects(cell_rect_fitz):
                    text_rects_to_mask.append((tb_x0, tb_y0, tb_x1, tb_y1))

        for (tx0, ty0, tx1, ty1) in text_rects_to_mask:
            px0 = max(0, int((tx0 - cell_x0_pt) / cell_w_pt * crop_w) - 2)
            py0 = max(0, int((ty0 - cell_y0_pt) / cell_h_pt * crop_h) - 2)
            px1 = min(crop_w, int((tx1 - cell_x0_pt) / cell_w_pt * crop_w) + 2)
            py1 = min(crop_h, int((ty1 - cell_y0_pt) / cell_h_pt * crop_h) + 2)
            text_mask[py0:py1, px0:px1] = 255

        dark_in_text = int(np.sum((inner_binary > 0) & (text_mask > 0)))
        text_mask_overlap = dark_in_text / max(1, dark_pixel_count)

        # Si el texto de la celda es un token alfanumérico corto o la tinta es predominantemente texto
        if has_text and ALPHANUMERIC_TOKEN_REGEX.match(clean_text) and not has_local_embedded_image:
            return {
                "has_real_geometry": False,
                "has_local_embedded_image": False,
                "confidence": 0.0,
                "evidence_sources": [],
                "shape_features": {
                    "alphanumeric_token": clean_text,
                    "dark_pixel_count": dark_pixel_count,
                    "text_mask_overlap_ratio": round(text_mask_overlap, 3)
                },
                "text_mask_overlap_ratio": 1.0,
                "inner_drawing_bbox": None,
                "crop_image_path": None,
                "rejection_reason": f"Celda alfanumérica pura ('{clean_text}') sin componentes gráficos independientes",
                "is_strictly_text_or_empty": True
            }

        # En un PDF digital sin imagen incrustada local, no puede haber geometría raster independiente
        if is_digital_pdf and not has_local_embedded_image:
            return {
                "has_real_geometry": False,
                "has_local_embedded_image": False,
                "confidence": 0.0,
                "evidence_sources": [],
                "shape_features": {
                    "is_digital_pdf": True,
                    "has_local_embedded_image": False,
                    "dark_pixel_count": dark_pixel_count,
                    "text_mask_overlap_ratio": round(text_mask_overlap, 3)
                },
                "text_mask_overlap_ratio": round(text_mask_overlap, 3) if has_text else 0.0,
                "inner_drawing_bbox": None,
                "crop_image_path": None,
                "rejection_reason": "PDF digital sin imagen incrustada local (trazos evaluados en capa vectorial)",
                "is_strictly_text_or_empty": True
            }

        if text_mask_overlap >= 0.75:
            return {
                "has_real_geometry": False,
                "has_local_embedded_image": has_local_embedded_image,
                "confidence": 0.0,
                "evidence_sources": [],
                "shape_features": {
                    "dark_pixel_count": dark_pixel_count,
                    "text_mask_overlap_ratio": round(text_mask_overlap, 3)
                },
                "text_mask_overlap_ratio": round(text_mask_overlap, 3),
                "inner_drawing_bbox": None,
                "crop_image_path": None,
                "rejection_reason": f"El {text_mask_overlap*100:.1f}% de la tinta corresponde a texto OCR/palabras",
                "is_strictly_text_or_empty": True
            }

        # Restar máscara de texto para analizar exclusivamente la geometría gráfica restante
        inner_binary_geo = cv2.bitwise_and(inner_binary, cv2.bitwise_not(text_mask)) if OPENCV_AVAILABLE else inner_binary
        geo_dark_count = int(np.sum(inner_binary_geo > 0))
        if geo_dark_count < 15:
            return {
                "has_real_geometry": False,
                "has_local_embedded_image": has_local_embedded_image,
                "confidence": 0.0,
                "evidence_sources": [],
                "shape_features": {"geo_dark_count": geo_dark_count, "text_mask_overlap_ratio": round(text_mask_overlap, 3)},
                "text_mask_overlap_ratio": round(text_mask_overlap, 3),
                "inner_drawing_bbox": None,
                "crop_image_path": None,
                "rejection_reason": "Sin tinta gráfica remanente tras enmascarar texto OCR",
                "is_strictly_text_or_empty": True
            }

        # 5. Análisis de Componentes Conectados (Connected Components) sobre tinta gráfica pura
        has_real_shape = False
        evidence_sources = []
        shape_features = {}
        inner_norm = None

        if OPENCV_AVAILABLE:
            num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(inner_binary_geo, connectivity=8)
            valid_comps = []
            for i in range(1, num_labels):
                comp_w = stats[i, cv2.CC_STAT_WIDTH]
                comp_h = stats[i, cv2.CC_STAT_HEIGHT]
                comp_area = stats[i, cv2.CC_STAT_AREA]
                comp_x = stats[i, cv2.CC_STAT_LEFT]
                comp_y = stats[i, cv2.CC_STAT_TOP]

                if comp_area < 8 or (comp_w < 3 and comp_h < 3):
                    continue

                valid_comps.append({
                    "x": comp_x, "y": comp_y, "w": comp_w, "h": comp_h, "area": comp_area
                })

            if valid_comps:
                min_x = min(c["x"] for c in valid_comps)
                min_y = min(c["y"] for c in valid_comps)
                max_x = max(c["x"] + c["w"] for c in valid_comps)
                max_y = max(c["y"] + c["h"] for c in valid_comps)

                span_w = max_x - min_x
                span_h = max_y - min_y
                span_aspect = span_w / max(1.0, span_h)

                contours, hierarchy = cv2.findContours(inner_binary_geo, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
                circle_hits = 0
                has_holes = False

                for c_idx, cnt in enumerate(contours):
                    area = cv2.contourArea(cnt)
                    perimeter = cv2.arcLength(cnt, True)
                    if perimeter <= 0:
                        continue
                    circularity = 4 * math.pi * (area / (perimeter ** 2))
                    bx, by, bw, bh = cv2.boundingRect(cnt)
                    aspect = bw / max(1.0, bh)

                    if circularity >= 0.65 and 0.75 <= aspect <= 1.35 and bw >= 12 and bh >= 12:
                        circle_hits += 1

                    if hierarchy is not None and len(hierarchy) > 0:
                        if hierarchy[0][c_idx][2] != -1:
                            has_holes = True

                lines = cv2.HoughLinesP(inner_binary_geo, 1, np.pi / 180, threshold=20, minLineLength=12, maxLineGap=4)
                line_count = len(lines) if lines is not None else 0

                is_text_line_pattern = False
                if has_text and span_h <= 30 and span_w >= 30 and circle_hits == 0:
                    is_text_line_pattern = True

                if not is_text_line_pattern:
                    if circle_hits >= 1:
                        has_real_shape = True
                        evidence_sources.append("raster_hough_circles")
                    elif line_count >= 3 and span_w >= 18 and span_h >= 18:
                        has_real_shape = True
                        evidence_sources.append("raster_connected_lines")
                    elif has_holes and span_w >= 16 and span_h >= 16:
                        has_real_shape = True
                        evidence_sources.append("raster_compound_symbol")
                    elif len(valid_comps) >= 2 and span_w >= 20 and span_h >= 20 and dark_ratio >= 0.015:
                        has_real_shape = True
                        evidence_sources.append("raster_connected_components")

                inner_norm = [
                    round(c_x0 + (min_x / crop_w) * (c_x1 - c_x0), 4),
                    round(c_y0 + (min_y / crop_h) * (c_y1 - c_y0), 4),
                    round(c_x0 + (max_x / crop_w) * (c_x1 - c_x0), 4),
                    round(c_y0 + (max_y / crop_h) * (c_y1 - c_y0), 4)
                ]

                shape_features = {
                    "valid_components_count": len(valid_comps),
                    "circle_hits": circle_hits,
                    "hough_lines_count": line_count,
                    "has_holes": has_holes,
                    "span_w_px": span_w,
                    "span_h_px": span_h,
                    "span_aspect_ratio": round(span_aspect, 2),
                    "dark_pixel_ratio": round(dark_ratio, 4)
                }

        is_waveform_or_chart = False
        if has_real_shape:
            # Detección de forma de onda / diagrama que ocupa la mayor parte de la celda horizontalmente
            if span_aspect >= 3.2 and span_w >= int(crop_w * 0.65) and circle_hits == 0:
                is_waveform_or_chart = True
                evidence_sources.append("raster_waveform_or_chart")
                shape_features["is_waveform_or_chart"] = True

        raster_conf = 0.85 if has_real_shape else 0.0
        if "raster_hough_circles" in evidence_sources:
            raster_conf = 0.92

        return {
            "has_real_geometry": has_real_shape,
            "has_local_embedded_image": has_local_embedded_image,
            "confidence": raster_conf,
            "evidence_sources": evidence_sources,
            "shape_features": shape_features,
            "text_mask_overlap_ratio": round(text_mask_overlap, 3),
            "inner_drawing_bbox": inner_norm if has_real_shape else None,
            "crop_image_path": None,
            "rejection_reason": None if has_real_shape else "No se detectaron círculos, polígonos ni líneas conectadas en raster",
            "is_strictly_text_or_empty": not has_real_shape
        }
