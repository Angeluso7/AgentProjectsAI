import os
import uuid
import math
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
import fitz  # PyMuPDF

from app.core.settings import settings
from app.core.logging import logger

# Factor de conversión estándar PDF point a milímetro: 1 pt = 1/72 pulgada = 25.4 / 72 mm
PT_TO_MM = 25.4 / 72.0


@dataclass
class VectorSymbolCandidateDTO:
    """Candidato a símbolo extraído desde geometría vectorial nativa."""
    id: str
    bbox_pt: List[float]               # [x0, y0, x1, y1] en puntos PDF
    bbox_normalized: List[float]       # [x0, y0, x1, y1] relativo 0.0 - 1.0
    estimated_physical_size_mm: Dict[str, Any]
    stroke_count: int
    source_render_mode: str = "vector" # vector, raster, mixed
    confidence_score: float = 0.85
    crop_image_path: Optional[str] = None
    svg_data: Optional[str] = None
    canonical_family_hint: str = "valves"
    drawing_count: int = 1

@dataclass
class PipingLineCandidateDTO:
    """Candidato a segmento de línea de tubería (piping) extraído de la geometría vectorial."""
    polyline_points: List[List[float]]      # [[x0, y0], [x1, y1], ...] coordenadas normalizadas 0.0 - 1.0
    bbox_normalized: List[float]            # [x0, y0, x1, y1] normalizado 0.0 - 1.0
    line_style: str                         # "solid", "dashed", "dotted"
    length_mm: float
    stroke_width_pt: float
    color: Optional[Tuple] = None
    is_main_process_line: bool = True
    attributes: Dict[str, Any] = field(default_factory=dict)


class VectorSymbolExtractor:
    """
    Extractor especializado en geometría vectorial nativa para planos y documentos PDF.
    Utiliza PyMuPDF page.get_drawings() para:
    1. Extraer trazos vectoriales (rectángulos, curvas bezier, líneas y polígonos).
    2. Filtrar líneas infinitas de proceso/tubería o marcos de lámina (> 50 mm).
    3. Agrupar espacialmente trazos cercanos o conexos que forman un símbolo único.
    4. Calcular tamaño físico exacto en milímetros y métricas geométricas.
    5. Renderizar recorte nítido de alta resolución (300 DPI).
    """

    def __init__(self, crops_dir: Optional[str] = None):
        self.crops_dir = crops_dir or os.path.join(settings.STORAGE_LOCAL_ROOT, "crops", "symbols")
        os.makedirs(self.crops_dir, exist_ok=True)

    def extract_candidates_from_page(
        self,
        page: fitz.Page,
        page_number: int = 1,
        doc_uid: str = "doc",
        region_rect: Optional[fitz.Rect] = None,
        min_size_mm: float = 3.0,
        max_size_mm: float = 35.0,
        cluster_distance_mm: float = 2.0,
        known_text_bboxes_norm: Optional[List[List[float]]] = None
    ) -> List[VectorSymbolCandidateDTO]:
        """
        Extrae candidatos a símbolo agrupando trazos vectoriales dentro de la página o región.
        """
        rect = page.rect
        pw, ph = rect.width, rect.height
        if pw <= 0 or ph <= 0:
            return []

        drawings = page.get_drawings()
        if not drawings:
            logger.debug(f"Pág {page_number}: no se detectaron trazos vectoriales en get_drawings().")
            return []

        # 1. Filtrar trazos individuales candidatos
        valid_paths = []
        cluster_dist_pt = cluster_distance_mm / PT_TO_MM

        for d in drawings:
            r = d.get("rect")
            if not r:
                continue

            # Si se especificó región de interés, verificar intersección
            if region_rect and not r.intersects(region_rect):
                continue

            w_mm = r.width * PT_TO_MM
            h_mm = r.height * PT_TO_MM

            # Filtrar líneas continuas excesivamente largas (tuberías, bordes de lámina)
            if w_mm > max_size_mm * 2.5 or h_mm > max_size_mm * 2.5:
                continue

            # Filtrar puntos minúsculos de ruido (< 0.5 mm)
            if w_mm < 0.5 and h_mm < 0.5:
                continue

            # Contar número de primitivas dentro del dibujo
            items = d.get("items", [])
            valid_paths.append({
                "rect": r,
                "items_count": len(items),
                "fill": d.get("fill"),
                "color": d.get("color"),
                "width": d.get("width", 1.0)
            })

        if not valid_paths:
            return []

        # 2. Agrupamiento espacial (Clustering de Bounding Boxes cercanos)
        clusters = self._cluster_paths(valid_paths, margin_pt=cluster_dist_pt)

        # 3. Construir y calificar candidatos
        candidates: List[VectorSymbolCandidateDTO] = []

        for idx, cluster in enumerate(clusters):
            c_rect = cluster["rect"]
            w_mm = round(c_rect.width * PT_TO_MM, 2)
            h_mm = round(c_rect.height * PT_TO_MM, 2)
            max_dim = max(w_mm, h_mm)
            min_dim = min(w_mm, h_mm)

            # Filtro blando de dimensiones físicas
            if max_dim < min_size_mm or max_dim > max_size_mm:
                continue

            aspect_ratio = round(w_mm / max(0.1, h_mm), 2)
            # Filtro de relación de aspecto (no debe ser una línea alargada aislada)
            if aspect_ratio > 4.0 or aspect_ratio < 0.25:
                continue

            tight_norm_box = [
                round(c_rect.x0 / pw, 4),
                round(c_rect.y0 / ph, 4),
                round(c_rect.x1 / pw, 4),
                round(c_rect.y1 / ph, 4)
            ]

            # Descarte contra cajas de texto conocidas (>=50% solapamiento)
            if known_text_bboxes_norm and self._overlaps_with_text(tight_norm_box, known_text_bboxes_norm):
                continue

            # Calcular Score Ponderado Blando (S_sym)
            confidence = self._compute_soft_confidence(w_mm, h_mm, cluster["stroke_count"], cluster["paths_count"])

            # Inferencia de familia orientativa según forma
            family_hint = self._infer_family_hint(w_mm, h_mm, aspect_ratio, cluster["stroke_count"])

            # Margen fijo de 3mm convertido a puntos según la geometría del PDF
            margin_pt = 3.0 / PT_TO_MM
            mx0 = max(0.0, c_rect.x0 - margin_pt)
            my0 = max(0.0, c_rect.y0 - margin_pt)
            mx1 = min(pw, c_rect.x1 + margin_pt)
            my1 = min(ph, c_rect.y1 + margin_pt)

            norm_box = [
                round(mx0 / pw, 4),
                round(my0 / ph, 4),
                round(mx1 / pw, 4),
                round(my1 / ph, 4)
            ]

            # Renderizar Crop en alta resolución (300 DPI) con margen de 3mm
            crop_path = None
            try:
                clip_r = fitz.Rect(mx0, my0, mx1, my1)
                pix = page.get_pixmap(clip=clip_r, dpi=300)
                crop_name = f"sym_vec_{doc_uid}_p{page_number}_{idx + 1}.png"
                full_crop_path = os.path.join(self.crops_dir, crop_name)
                pix.save(full_crop_path)
                crop_path = f"/data/crops/symbols/{crop_name}"
            except Exception as ce:
                logger.debug(f"Aviso generando crop vectorial pág {page_number}: {ce}")

            candidate = VectorSymbolCandidateDTO(
                id=str(uuid.uuid4()),
                bbox_pt=[round(mx0, 1), round(my0, 1), round(mx1, 1), round(my1, 1)],
                bbox_normalized=norm_box,
                estimated_physical_size_mm={
                    "width_mm": w_mm,
                    "height_mm": h_mm,
                    "aspect_ratio": aspect_ratio,
                    "max_dimension_mm": max_dim,
                    "min_dimension_mm": min_dim,
                    "stroke_count": cluster["stroke_count"],
                    "paths_count": cluster["paths_count"]
                },
                stroke_count=cluster["stroke_count"],
                source_render_mode="vector",
                confidence_score=round(confidence, 3),
                crop_image_path=crop_path,
                canonical_family_hint=family_hint,
                drawing_count=cluster["paths_count"]
            )
            candidates.append(candidate)

        logger.info(f"Pág {page_number}: {len(candidates)} candidatos vectoriales extraídos de {len(valid_paths)} trazos.")
        return candidates

    def _cluster_paths(self, paths: List[Dict[str, Any]], margin_pt: float) -> List[Dict[str, Any]]:
        """
        Agrupa trazos vectoriales cuyas cajas envolventes expandidas se intersectan o tocan.
        """
        if not paths:
            return []

        # Inicializar cada path como un cluster individual
        active_clusters = []
        for p in paths:
            active_clusters.append({
                "rect": fitz.Rect(p["rect"]),
                "stroke_count": p["items_count"],
                "paths_count": 1
            })

        merged = True
        while merged:
            merged = False
            new_clusters = []
            skip_indices = set()

            for i in range(len(active_clusters)):
                if i in skip_indices:
                    continue
                current = active_clusters[i]
                c_rect = current["rect"]
                expanded = fitz.Rect(
                    c_rect.x0 - margin_pt,
                    c_rect.y0 - margin_pt,
                    c_rect.x1 + margin_pt,
                    c_rect.y1 + margin_pt
                )

                for j in range(i + 1, len(active_clusters)):
                    if j in skip_indices:
                        continue
                    other = active_clusters[j]
                    if expanded.intersects(other["rect"]):
                        # Fusionar cluster j dentro de current
                        current["rect"] = current["rect"] | other["rect"]
                        current["stroke_count"] += other["stroke_count"]
                        current["paths_count"] += other["paths_count"]
                        skip_indices.add(j)
                        merged = True

                new_clusters.append(current)

            active_clusters = new_clusters

        return active_clusters

    def _compute_soft_confidence(self, w_mm: float, h_mm: float, strokes: int, paths: int) -> float:
        """
        Calcula una confianza continua (soft score) ponderando tamaño físico ideal (5-10 mm)
        y densidad de trazos estructurales.
        """
        max_dim = max(w_mm, h_mm)

        # Señal 1: Proximidad al rango canónico (5 a 10 mm)
        # Función campana gaussiana centrada en 7.5 mm con dispersión
        diff = abs(max_dim - 7.5)
        size_score = max(0.2, math.exp(-0.5 * (diff / 4.0) ** 2))

        # Señal 2: Complejidad de trazos (un símbolo de piping suele tener entre 2 y 25 trazos)
        if 2 <= strokes <= 30:
            stroke_score = 0.95
        elif strokes == 1:
            stroke_score = 0.60
        else:
            stroke_score = 0.70

        # Ponderación
        final_score = 0.60 * size_score + 0.40 * stroke_score
        return min(0.98, max(0.50, final_score))

    def _infer_family_hint(self, w_mm: float, h_mm: float, ar: float, strokes: int) -> str:
        """Infiere una sugerencia inicial de familia canónica para piping."""
        if 0.8 <= ar <= 1.2 and (6.0 <= w_mm <= 14.0):
            # Círculo o cuadrado balanceado: típicamente burbuja de instrumento ISA 5.1
            return "instruments"
        elif (1.2 <= ar <= 2.5 or 0.4 <= ar <= 0.8) and (4.0 <= w_mm <= 15.0):
            # Silueta horizontal o vertical simétrica: típicamente válvula
            return "valves"
        elif strokes > 15 and max(w_mm, h_mm) > 12.0:
            # Componente de alta complejidad: equipo o bomba
            return "pumps"
        else:
            return "fittings"

    def _overlaps_with_text(self, box: List[float], text_boxes: List[List[float]]) -> bool:
        """Determina si la caja del candidato tiene solapamiento significativo (>=50%) con texto OCR."""
        bx0, by0, bx1, by1 = box
        b_area = max(1e-6, (bx1 - bx0) * (by1 - by0))

        for tb in text_boxes:
            tx0, ty0, tx1, ty1 = tb
            ix0 = max(bx0, tx0)
            iy0 = max(by0, ty0)
            ix1 = min(bx1, tx1)
            iy1 = min(by1, ty1)

            if ix1 > ix0 and iy1 > iy0:
                inter_area = (ix1 - ix0) * (iy1 - iy0)
                # Si el 50% o más de la caja del símbolo está dentro de una caja de texto, es texto
                if (inter_area / b_area) >= 0.50:
                    return True
        return False

    def extract_piping_lines_from_page(
        self,
        page: fitz.Page,
        page_number: int = 1,
        region_rect: Optional[fitz.Rect] = None,
        min_length_mm: float = 40.0
    ) -> List[PipingLineCandidateDTO]:
        """
        Extrae trazos vectoriales largos correspondientes a líneas de tubería / proceso.
        Filtra marcos de lámina perimetrales y cajas rectangulares cerradas (viñetas/tablas).
        """
        rect = page.rect
        pw, ph = rect.width, rect.height
        if pw <= 0 or ph <= 0:
            return []

        drawings = page.get_drawings()
        if not drawings:
            return []

        line_candidates: List[PipingLineCandidateDTO] = []

        for d in drawings:
            r = d.get("rect")
            if not r:
                continue

            if region_rect and not r.intersects(region_rect):
                continue

            # 1. Descartar marco perimetral general de lámina
            if r.width > 0.90 * pw and r.height > 0.90 * ph:
                continue
            if r.x0 < 0.02 * pw and r.y0 < 0.02 * ph and r.x1 > 0.98 * pw and r.y1 > 0.98 * ph:
                continue

            w_mm = r.width * PT_TO_MM
            h_mm = r.height * PT_TO_MM

            # 2. Descartar cajas cerradas anchas (cuadros de viñeta, tablas o leyendas)
            if d.get("closePath") and min(w_mm, h_mm) > 25.0:
                continue

            # 3. Extraer puntos y calcular longitud acumulada
            items = d.get("items", [])
            polyline_pts: List[List[float]] = []
            total_len_pt = 0.0

            for itm in items:
                cmd = itm[0]
                if cmd == "l":
                    p1, p2 = itm[1], itm[2]
                    seg_len = math.hypot(p2.x - p1.x, p2.y - p1.y)
                    total_len_pt += seg_len
                    if not polyline_pts:
                        polyline_pts.append([round(p1.x / pw, 5), round(p1.y / ph, 5)])
                    polyline_pts.append([round(p2.x / pw, 5), round(p2.y / ph, 5)])
                elif cmd == "c":
                    p1, p4 = itm[1], itm[4]
                    seg_len = math.hypot(p4.x - p1.x, p4.y - p1.y)
                    total_len_pt += seg_len
                    if not polyline_pts:
                        polyline_pts.append([round(p1.x / pw, 5), round(p1.y / ph, 5)])
                    polyline_pts.append([round(p4.x / pw, 5), round(p4.y / ph, 5)])
                elif cmd == "re":
                    rbox = itm[1]
                    rw_mm = rbox.width * PT_TO_MM
                    rh_mm = rbox.height * PT_TO_MM
                    if min(rw_mm, rh_mm) <= 3.0 and max(rw_mm, rh_mm) >= min_length_mm:
                        if rbox.width >= rbox.height:
                            ym = (rbox.y0 + rbox.y1) / (2.0 * ph)
                            polyline_pts = [
                                [round(rbox.x0 / pw, 5), round(ym, 5)],
                                [round(rbox.x1 / pw, 5), round(ym, 5)]
                            ]
                            total_len_pt = rbox.width
                        else:
                            xm = (rbox.x0 + rbox.x1) / (2.0 * pw)
                            polyline_pts = [
                                [round(xm, 5), round(rbox.y0 / ph, 5)],
                                [round(xm, 5), round(rbox.y1 / ph, 5)]
                            ]
                            total_len_pt = rbox.height

            length_mm = round(total_len_pt * PT_TO_MM, 2)
            if length_mm < min_length_mm:
                # Si los items individuales no sumaron pero el rect es una línea alargada recta
                if max(w_mm, h_mm) >= min_length_mm and min(w_mm, h_mm) <= 3.0:
                    length_mm = round(max(w_mm, h_mm), 2)
                    if w_mm >= h_mm:
                        ym = (r.y0 + r.y1) / (2.0 * ph)
                        polyline_pts = [
                            [round(r.x0 / pw, 5), round(ym, 5)],
                            [round(r.x1 / pw, 5), round(ym, 5)]
                        ]
                    else:
                        xm = (r.x0 + r.x1) / (2.0 * pw)
                        polyline_pts = [
                            [round(xm, 5), round(r.y0 / ph, 5)],
                            [round(xm, 5), round(r.y1 / ph, 5)]
                        ]
                else:
                    continue

            if not polyline_pts or len(polyline_pts) < 2:
                continue

            dashes = d.get("dashes")
            is_dashed = False
            if dashes:
                if isinstance(dashes, str):
                    inner = dashes.split("]")[0].replace("[", "").strip()
                    is_dashed = bool(inner)
                elif isinstance(dashes, (list, tuple)):
                    is_dashed = len(dashes) > 0 and any(x > 0 for x in dashes)

            line_style = "dashed" if is_dashed else "solid"
            stroke_width = round(float(d.get("width", 1.0)), 2)
            is_main = bool(line_style == "solid" and stroke_width >= 1.0)

            norm_box = [
                round(r.x0 / pw, 5),
                round(r.y0 / ph, 5),
                round(r.x1 / pw, 5),
                round(r.y1 / ph, 5)
            ]

            line_candidates.append(PipingLineCandidateDTO(
                polyline_points=polyline_pts,
                bbox_normalized=norm_box,
                line_style=line_style,
                length_mm=length_mm,
                stroke_width_pt=stroke_width,
                color=d.get("color"),
                is_main_process_line=is_main,
                attributes={
                    "page_number": page_number,
                    "items_count": len(items),
                    "is_closed": bool(d.get("closePath"))
                }
            ))

        return line_candidates

    def check_symbol_intersects_line(
        self,
        symbol_bbox_norm: List[float],
        polyline_points: List[List[float]],
        tolerance_norm: float = 0.005
    ) -> bool:
        """
        Determina si el bounding box normalizado de un símbolo intersecta o toca
        una polilínea de tubería dada.
        """
        if not symbol_bbox_norm or len(symbol_bbox_norm) != 4 or not polyline_points or len(polyline_points) < 2:
            return False

        bx0 = symbol_bbox_norm[0] - tolerance_norm
        by0 = symbol_bbox_norm[1] - tolerance_norm
        bx1 = symbol_bbox_norm[2] + tolerance_norm
        by1 = symbol_bbox_norm[3] + tolerance_norm

        def ccw(A, B, C):
            return (C[1] - A[1]) * (B[0] - A[0]) > (B[1] - A[1]) * (C[0] - A[0])

        def segments_intersect(A, B, C, D):
            return ccw(A, C, D) != ccw(B, C, D) and ccw(A, B, C) != ccw(A, B, D)

        box_edges = [
            ([bx0, by0], [bx1, by0]),
            ([bx1, by0], [bx1, by1]),
            ([bx1, by1], [bx0, by1]),
            ([bx0, by1], [bx0, by0]),
        ]

        for i in range(len(polyline_points) - 1):
            pa = polyline_points[i]
            pb = polyline_points[i + 1]

            # 1. Alguno de los vértices dentro de la caja
            if (bx0 <= pa[0] <= bx1 and by0 <= pa[1] <= by1) or (bx0 <= pb[0] <= bx1 and by0 <= pb[1] <= by1):
                return True

            # 2. El segmento cruza alguna de las 4 aristas de la caja
            for edge_a, edge_b in box_edges:
                if segments_intersect(pa, pb, edge_a, edge_b):
                    return True

        return False

    def compute_symbol_projection_t(
        self,
        symbol_bbox_norm: List[float],
        polyline_points: List[List[float]],
    ) -> float:
        """
        Calcula la proyección normalizada t (0.0 -> 1.0) del centro del símbolo
        a lo largo de la polilínea de tubería.
        """
        if not symbol_bbox_norm or len(symbol_bbox_norm) != 4 or not polyline_points or len(polyline_points) < 2:
            return 0.0

        cx = (symbol_bbox_norm[0] + symbol_bbox_norm[2]) / 2.0
        cy = (symbol_bbox_norm[1] + symbol_bbox_norm[3]) / 2.0

        seg_lengths = []
        total_len = 0.0
        for i in range(len(polyline_points) - 1):
            pa = polyline_points[i]
            pb = polyline_points[i + 1]
            sl = math.hypot(pb[0] - pa[0], pb[1] - pa[1])
            seg_lengths.append(sl)
            total_len += sl

        if total_len <= 1e-9:
            return 0.0

        min_dist_sq = float("inf")
        best_t_global = 0.0
        accum_len = 0.0

        for i in range(len(polyline_points) - 1):
            pa = polyline_points[i]
            pb = polyline_points[i + 1]
            sl = seg_lengths[i]
            if sl <= 1e-9:
                continue

            dx = pb[0] - pa[0]
            dy = pb[1] - pa[1]
            t_local = ((cx - pa[0]) * dx + (cy - pa[1]) * dy) / (sl * sl)
            t_local_clamped = max(0.0, min(1.0, t_local))

            proj_x = pa[0] + t_local_clamped * dx
            proj_y = pa[1] + t_local_clamped * dy

            dist_sq = (cx - proj_x) ** 2 + (cy - proj_y) ** 2
            if dist_sq < min_dist_sq:
                min_dist_sq = dist_sq
                t_global = (accum_len + t_local_clamped * sl) / total_len
                best_t_global = max(0.0, min(1.0, t_global))

            accum_len += sl

        return round(best_t_global, 4)
