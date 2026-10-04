import os
import uuid
import math
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

import numpy as np
from PIL import Image

from app.core.settings import settings
from app.core.logging import logger

try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False
    logger.warning("OpenCV no disponible; RasterSymbolExtractor usará fallback con PIL/NumPy.")


@dataclass
class RasterSymbolCandidateDTO:
    """Candidato a símbolo extraído desde imagen raster / documento escaneado."""
    id: str
    bbox_pixel: List[int]              # [x0, y0, x1, y1] en píxeles de la imagen
    bbox_normalized: List[float]       # [x0, y0, x1, y1] relativo 0.0 - 1.0
    estimated_physical_size_mm: Dict[str, Any]
    stroke_density: float
    black_white_ratio: float
    source_render_mode: str = "raster" # raster, vector, mixed
    confidence_score: float = 0.75
    crop_image_path: Optional[str] = None
    canonical_family_hint: str = "valves"


class RasterSymbolExtractor:
    """
    Extractor especializado en documentos escaneados, imágenes y rasterizados a 300 DPI.
    Aplica visión por computador (OpenCV / NumPy):
    1. Binarización adaptativa (Otsu invertido: trazos negros = 255, fondo = 0).
    2. Análisis de componentes conexos (8-conectividad con estadísticas).
    3. Filtrado no rígido por tamaño físico blando (calibrable por familia, núcleo 5-10 mm).
    4. Evaluación de densidad de trazo (0.05 a 0.38) y relación de aspecto (0.3 a 3.0).
    5. Exclusión de cajas de texto OCR para evitar confundir caracteres con símbolos.
    6. Generación de recortes PNG transparentes.
    """

    def __init__(self, crops_dir: Optional[str] = None):
        self.crops_dir = crops_dir or os.path.join(settings.STORAGE_LOCAL_ROOT, "crops", "symbols")
        os.makedirs(self.crops_dir, exist_ok=True)

    def extract_candidates_from_image(
        self,
        image_input: Any, # np.ndarray, PIL.Image o ruta str
        dpi: int = 300,
        page_number: int = 1,
        doc_uid: str = "doc",
        known_text_bboxes_norm: Optional[List[List[float]]] = None,
        min_size_mm: float = 3.0,
        max_size_mm: float = 35.0,
        family_target: str = "valves"
    ) -> List[RasterSymbolCandidateDTO]:
        """
        Procesa una imagen y retorna los candidatos a símbolo detectados en el raster.
        """
        # 1. Cargar imagen como array NumPy en escala de grises
        img_gray, img_rgb = self._load_image_arrays(image_input)
        if img_gray is None:
            return []

        h_px, w_px = img_gray.shape[:2]
        if w_px <= 0 or h_px <= 0:
            return []

        # 2. Binarización adaptativa y componentes conexos
        components = []
        if OPENCV_AVAILABLE:
            try:
                _, binary = cv2.threshold(img_gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
                num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(binary, connectivity=8)
                for i in range(1, num_labels):
                    components.append({
                        "x": int(stats[i, cv2.CC_STAT_LEFT]),
                        "y": int(stats[i, cv2.CC_STAT_TOP]),
                        "w": int(stats[i, cv2.CC_STAT_WIDTH]),
                        "h": int(stats[i, cv2.CC_STAT_HEIGHT]),
                        "area": int(stats[i, cv2.CC_STAT_AREA])
                    })
            except Exception as ce:
                logger.warning(f"cv2.connectedComponentsWithStats aviso ({ce}), activando fallback SciPy.")
                components = []

        if not components:
            try:
                from scipy import ndimage
                thresh = int(np.mean(img_gray) * 0.85)
                binary = (img_gray < thresh)
                structure = ndimage.generate_binary_structure(2, 2)
                labels, num_labels = ndimage.label(binary, structure=structure)
                slices = ndimage.find_objects(labels)
                for idx, sl in enumerate(slices):
                    if sl is None:
                        continue
                    sy, sx = sl
                    x, y = sx.start, sy.start
                    w, h = sx.stop - x, sy.stop - y
                    area = int(np.sum(labels[sy, sx] == (idx + 1)))
                    components.append({"x": x, "y": y, "w": w, "h": h, "area": area})
            except Exception as se:
                logger.warning(f"Error en fallback SciPy de componentes conexos: {se}")
                return []


        candidates: List[RasterSymbolCandidateDTO] = []
        px_per_mm = dpi / 25.4

        # Recorrer componentes conexos
        for comp in components:
            x = comp["x"]
            y = comp["y"]
            w = comp["w"]
            h = comp["h"]
            area = comp["area"]


            # Dimensiones físicas en mm
            w_mm = round(w / px_per_mm, 2)
            h_mm = round(h / px_per_mm, 2)
            max_dim = max(w_mm, h_mm)
            min_dim = min(w_mm, h_mm)

            # Filtro blando dimensional
            if max_dim < min_size_mm or max_dim > max_size_mm:
                continue

            # Relación de aspecto
            aspect_ratio = round(w / max(1, h), 2)
            if aspect_ratio > 3.8 or aspect_ratio < 0.26:
                continue

            # Densidad de trazo dentro de la caja envolvente
            bbox_area = max(1, w * h)
            stroke_density = round(area / bbox_area, 3)

            # Símbolos de piping típicamente tienen trazos huecos o rellenos moderados (0.02 a 0.70)
            if stroke_density < 0.02 or stroke_density > 0.70:
                continue

            norm_box = [
                round(x / w_px, 4),
                round(y / h_px, 4),
                round((x + w) / w_px, 4),
                round((y + h) / h_px, 4)
            ]

            # 3. Descarte contra cajas de texto OCR conocidas
            if known_text_bboxes_norm:
                if self._overlaps_with_text(norm_box, known_text_bboxes_norm):
                    continue

            # 4. Cálculo de confianza suave
            conf = self._compute_raster_confidence(w_mm, h_mm, stroke_density, aspect_ratio, family_target)
            if conf < 0.45:
                continue


            # Inferencia de familia
            family_hint = "instruments" if (0.8 <= aspect_ratio <= 1.25 and 6.0 <= max_dim <= 14.0) else "valves"

            # 5. Generar y guardar Recorte PNG
            crop_path = None
            try:
                pad = int(4 * (dpi / 150))
                rx0 = max(0, x - pad)
                ry0 = max(0, y - pad)
                rx1 = min(w_px, x + w + pad)
                ry1 = min(h_px, y + h + pad)

                crop_np = img_rgb[ry0:ry1, rx0:rx1]
                crop_pil = Image.fromarray(crop_np)
                crop_name = f"sym_ras_{doc_uid}_p{page_number}_{len(candidates)+1}.png"
                full_crop_path = os.path.join(self.crops_dir, crop_name)
                crop_pil.save(full_crop_path, format="PNG")
                crop_path = f"/data/crops/symbols/{crop_name}"
            except Exception as ce:
                logger.debug(f"Aviso guardando crop raster pág {page_number}: {ce}")

            candidate = RasterSymbolCandidateDTO(
                id=str(uuid.uuid4()),
                bbox_pixel=[x, y, x + w, y + h],
                bbox_normalized=norm_box,
                estimated_physical_size_mm={
                    "width_mm": w_mm,
                    "height_mm": h_mm,
                    "aspect_ratio": aspect_ratio,
                    "max_dimension_mm": max_dim,
                    "min_dimension_mm": min_dim,
                    "stroke_density": stroke_density,
                    "area_px": area
                },
                stroke_density=stroke_density,
                black_white_ratio=stroke_density,
                source_render_mode="raster",
                confidence_score=round(conf, 3),
                crop_image_path=crop_path,
                canonical_family_hint=family_hint
            )
            candidates.append(candidate)

        logger.info(f"Pág {page_number}: {len(candidates)} candidatos raster extraídos mediante OpenCV.")
        return candidates

    def _load_image_arrays(self, img_input: Any) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """Normaliza la entrada a arreglos NumPy gray y RGB."""
        try:
            if isinstance(img_input, str) and os.path.exists(img_input):
                pil_img = Image.open(img_input).convert("RGB")
                rgb = np.array(pil_img)
                gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY) if OPENCV_AVAILABLE else np.array(pil_img.convert("L"))
                return gray, rgb
            elif isinstance(img_input, np.ndarray):
                if len(img_input.shape) == 2:
                    rgb = np.stack([img_input]*3, axis=-1)
                    return img_input, rgb
                else:
                    gray = cv2.cvtColor(img_input, cv2.COLOR_RGB2GRAY) if OPENCV_AVAILABLE else np.mean(img_input, axis=2).astype(np.uint8)
                    return gray, img_input
            elif isinstance(img_input, (bytes, bytearray)):
                import io
                pil_img = Image.open(io.BytesIO(img_input)).convert("RGB")
                rgb = np.array(pil_img)
                gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY) if OPENCV_AVAILABLE else np.array(pil_img.convert("L"))
                return gray, rgb
            elif isinstance(img_input, Image.Image):
                rgb = np.array(img_input.convert("RGB"))
                gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY) if OPENCV_AVAILABLE else np.array(img_input.convert("L"))
                return gray, rgb

        except Exception as e:
            logger.error(f"Error cargando imagen en RasterSymbolExtractor: {e}")
        return None, None

    def _overlaps_with_text(self, box: List[float], text_boxes: List[List[float]]) -> bool:
        """Determina si la caja del candidato tiene solapamiento significativo con texto OCR."""
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
                if (inter_area / b_area) > 0.50:
                    return True
        return False

    def _compute_raster_confidence(self, w_mm: float, h_mm: float, density: float, ar: float, target_family: str) -> float:
        """Función de scoring multiseñal blando continuo."""
        max_dim = max(w_mm, h_mm)

        # Señal 1: Tamaño (rango blando centrado en 7.5 mm)
        target_center = 8.5 if target_family == "instruments" else 7.5
        diff = abs(max_dim - target_center)
        size_score = max(0.35, math.exp(-0.5 * (diff / 6.5) ** 2))

        # Señal 2: Densidad (debe ser hueca o trazo técnico)
        diff_dens = abs(density - 0.22)
        density_score = max(0.30, math.exp(-0.5 * (diff_dens / 0.18) ** 2))

        # Señal 3: Aspecto balanceado
        aspect_score = 0.90 if (0.4 <= ar <= 2.5) else 0.65

        final = 0.45 * size_score + 0.35 * density_score + 0.20 * aspect_score
        return min(0.95, max(0.40, final))

