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
        cluster_distance_mm: float = 2.0
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

            # Calcular Score Ponderado Blando (S_sym)
            confidence = self._compute_soft_confidence(w_mm, h_mm, cluster["stroke_count"], cluster["paths_count"])

            norm_box = [
                round(c_rect.x0 / pw, 4),
                round(c_rect.y0 / ph, 4),
                round(c_rect.x1 / pw, 4),
                round(c_rect.y1 / ph, 4)
            ]

            # Inferencia de familia orientativa según forma
            family_hint = self._infer_family_hint(w_mm, h_mm, aspect_ratio, cluster["stroke_count"])

            # Renderizar Crop en alta resolución (300 DPI)
            crop_path = None
            try:
                pad = 4 # 4 pt de padding
                clip_r = fitz.Rect(
                    max(0, c_rect.x0 - pad),
                    max(0, c_rect.y0 - pad),
                    min(pw, c_rect.x1 + pad),
                    min(ph, c_rect.y1 + pad)
                )
                pix = page.get_pixmap(clip=clip_r, dpi=300)
                crop_name = f"sym_vec_{doc_uid}_p{page_number}_{idx + 1}.png"
                full_crop_path = os.path.join(self.crops_dir, crop_name)
                pix.save(full_crop_path)
                crop_path = f"/data/crops/symbols/{crop_name}"
            except Exception as ce:
                logger.debug(f"Aviso generando crop vectorial pág {page_number}: {ce}")

            candidate = VectorSymbolCandidateDTO(
                id=str(uuid.uuid4()),
                bbox_pt=[round(c_rect.x0, 1), round(c_rect.y0, 1), round(c_rect.x1, 1), round(c_rect.y1, 1)],
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
