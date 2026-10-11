import os
import math
from typing import List, Dict, Any, Optional, Union
import numpy as np

try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False

from app.core.logging import logger


def classify_primitive_shape(candidate: Any) -> str:
    """
    Determina la forma geométrica primitiva de un candidato:
    - 'circle'
    - 'square'
    - 'hexagon'
    - 'triangle'
    - 'irregular_closed'
    - 'open_stroke'
    - 'text_like'

    Persiste el resultado en candidate.attributes['primitive_shape'] si el objeto lo permite.
    Acepta tanto DTOs de candidatos (VectorSymbolCandidateDTO, RasterSymbolCandidateDTO)
    como imágenes NumPy o contornos directos para tests unitarios.
    """
    shape_result = "irregular_closed"

    if not OPENCV_AVAILABLE:
        _store_shape_in_candidate(candidate, shape_result)
        return shape_result

    # 1. Extraer imagen o contorno según tipo de candidate
    cnt = None
    img_gray = None

    if isinstance(candidate, np.ndarray):
        # Puede ser un contorno (N, 1, 2) / (N, 2) o una imagen (H, W) / (H, W, C)
        if candidate.ndim == 3 and candidate.shape[1] == 1 and candidate.shape[2] == 2:
            cnt = candidate
        elif candidate.ndim == 2 and candidate.shape[1] == 2 and candidate.shape[0] > 2:
            cnt = candidate.reshape((-1, 1, 2)).astype(np.int32)
        elif candidate.ndim == 2:
            img_gray = candidate
        elif candidate.ndim == 3:
            img_gray = cv2.cvtColor(candidate, cv2.COLOR_BGR2GRAY) if candidate.shape[2] == 3 else candidate[:, :, 0]
    else:
        # Es un DTO o dict con crop_image_path
        crop_path = getattr(candidate, "crop_image_path", None)
        if isinstance(candidate, dict):
            crop_path = candidate.get("crop_image_path")

        if crop_path and os.path.exists(crop_path):
            img = cv2.imread(crop_path, cv2.IMREAD_UNCHANGED)
            if img is not None:
                if img.ndim == 3 and img.shape[2] == 4:
                    # Imagen RGBA: usar máscara alfa combinada con escala de grises
                    alpha = img[:, :, 3]
                    gray = cv2.cvtColor(img[:, :, :3], cv2.COLOR_BGR2GRAY)
                    img_gray = np.where(alpha > 30, gray, 255)
                elif img.ndim == 3:
                    img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                else:
                    img_gray = img

    # 2. Si tenemos imagen pero no contorno, binarizar y extraer contorno principal
    if cnt is None and img_gray is not None:
        try:
            # Otsu invertido para que trazo negro sea 255 y fondo sea 0
            if img_gray.dtype != np.uint8:
                img_gray = (img_gray * 255).astype(np.uint8) if img_gray.max() <= 1.0 else img_gray.astype(np.uint8)
            
            # Si la imagen tiene fondo blanco
            if np.mean(img_gray) > 127:
                _, binary = cv2.threshold(img_gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            else:
                _, binary = cv2.threshold(img_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

            contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                # Tomar el contorno con mayor área o longitud
                cnt = max(contours, key=cv2.contourArea)
                if cv2.contourArea(cnt) < 4:
                    cnt = max(contours, key=lambda c: cv2.arcLength(c, False))
        except Exception as e:
            logger.debug(f"Aviso extrayendo contorno para clasificación de forma: {e}")

    # 3. Si no hay contorno disponible, inferir con metadatos del candidato
    if cnt is None or len(cnt) < 3:
        # Inspeccionar stroke_count / dimensiones si están disponibles
        size_mm = getattr(candidate, "estimated_physical_size_mm", {})
        if isinstance(candidate, dict):
            size_mm = candidate.get("estimated_physical_size_mm", {})
        h_mm = size_mm.get("height_mm", 0.0) if isinstance(size_mm, dict) else 0.0
        w_mm = size_mm.get("width_mm", 0.0) if isinstance(size_mm, dict) else 0.0
        
        if h_mm > 0 and h_mm < 3.0 and w_mm < 3.0:
            shape_result = "text_like"
        else:
            shape_result = "open_stroke"
        _store_shape_in_candidate(candidate, shape_result)
        return shape_result

    # 4. Métricas geométricas sobre el contorno
    area = cv2.contourArea(cnt)
    perimeter = cv2.arcLength(cnt, closed=True)
    if perimeter <= 0:
        shape_result = "open_stroke"
        _store_shape_in_candidate(candidate, shape_result)
        return shape_result

    bx, by, bw, bh = cv2.boundingRect(cnt)
    aspect_ratio = float(bw) / max(1.0, float(bh))
    hull = cv2.convexHull(cnt)
    hull_area = cv2.contourArea(hull)
    solidity = float(area) / max(1.0, hull_area)

    # 5. Descarte de trazo abierto o filamento
    if area < 15 and perimeter > 35:
        shape_result = "open_stroke"
        _store_shape_in_candidate(candidate, shape_result)
        return shape_result

    if (area / max(1.0, float(bw * bh))) < 0.05 and solidity < 0.20:
        shape_result = "open_stroke"
        _store_shape_in_candidate(candidate, shape_result)
        return shape_result

    # 6. Aproximación poligonal con cv2.approxPolyDP
    epsilon = 0.032 * perimeter
    approx = cv2.approxPolyDP(cnt, epsilon, closed=True)
    n_vertices = len(approx)

    if n_vertices == 3:
        shape_result = "triangle"
        _store_shape_in_candidate(candidate, shape_result)
        return shape_result
    elif n_vertices == 4:
        if 0.65 <= aspect_ratio <= 1.50 and solidity >= 0.75:
            shape_result = "square"
            _store_shape_in_candidate(candidate, shape_result)
            return shape_result
    elif n_vertices == 6:
        shape_result = "hexagon"
        _store_shape_in_candidate(candidate, shape_result)
        return shape_result
    else:
        # Intentar con epsilon fino para hexágonos
        approx_fine = cv2.approxPolyDP(cnt, 0.025 * perimeter, closed=True)
        if len(approx_fine) == 6 and solidity >= 0.80:
            shape_result = "hexagon"
            _store_shape_in_candidate(candidate, shape_result)
            return shape_result

    # 7. Detección de Círculo (circularidad isoperimétrica y minEnclosingCircle)
    circularity = (4.0 * math.pi * area) / (perimeter * perimeter)
    (cx, cy), radius = cv2.minEnclosingCircle(cnt)
    circle_area = math.pi * (radius ** 2)
    circle_fill = area / max(1.0, circle_area)

    if 0.72 <= aspect_ratio <= 1.38 and circularity >= 0.75 and circle_fill >= 0.65:
        shape_result = "circle"
        _store_shape_in_candidate(candidate, shape_result)
        return shape_result

    # Detección adicional de círculo mediante HoughCircles si hay imagen rasterizada
    if img_gray is not None and 0.75 <= aspect_ratio <= 1.33:
        try:
            blurred = cv2.GaussianBlur(img_gray, (5, 5), 1.5)
            circles = cv2.HoughCircles(
                blurred,
                cv2.HOUGH_GRADIENT,
                dp=1.2,
                minDist=min(bw, bh) // 2,
                param1=50,
                param2=28,
                minRadius=int(min(bw, bh) * 0.3),
                maxRadius=int(max(bw, bh) * 0.6)
            )
            if circles is not None and len(circles[0]) > 0:
                shape_result = "circle"
                _store_shape_in_candidate(candidate, shape_result)
                return shape_result
        except Exception:
            pass

    shape_result = "irregular_closed"
    _store_shape_in_candidate(candidate, shape_result)
    return shape_result


def is_text_like_cluster(
    candidate: Any,
    nearby_candidates: List[Any],
    max_height_mm: float = 6.0,
    max_cluster_gap_ratio: float = 2.5
) -> bool:
    """
    Detecta el patrón característico de texto vectorizado en CAD/PDF:
    Varios trazos pequeños de altura similar, alineados horizontal o verticalmente,
    muy próximos entre sí (equivalente a las letras o caracteres de una palabra/etiqueta).

    Si un candidato cumple este patrón, retorna True y lo clasifica como 'text_like'.
    """
    c_box = _get_candidate_bbox_norm(candidate)
    c_size_mm = _get_candidate_size_mm(candidate)
    if not c_box:
        return False

    cx0, cy0, cx1, cy1 = c_box
    c_w = cx1 - cx0
    c_h = cy1 - cy0
    c_h_mm = c_size_mm.get("height_mm", c_h * 500.0)
    c_w_mm = c_size_mm.get("width_mm", c_w * 500.0)

    # Si es un objeto grande (ej. válvula de 10mm o tanque de 25mm), no es letra
    if c_h_mm > max_height_mm and c_w_mm > max_height_mm:
        return False

    c_center_x = (cx0 + cx1) / 2.0
    c_center_y = (cy0 + cy1) / 2.0

    aligned_horizontal_count = 0
    aligned_vertical_count = 0

    c_id = getattr(candidate, "id", None) or (candidate.get("id") if isinstance(candidate, dict) else None)

    for other in nearby_candidates:
        o_id = getattr(other, "id", None) or (other.get("id") if isinstance(other, dict) else None)
        if c_id and o_id and c_id == o_id:
            continue

        o_box = _get_candidate_bbox_norm(other)
        if not o_box:
            continue

        ox0, oy0, ox1, oy1 = o_box
        # Evitar comparar consigo mismo si no hay id
        if abs(ox0 - cx0) < 1e-5 and abs(oy0 - cy0) < 1e-5:
            continue

        o_w = ox1 - ox0
        o_h = oy1 - oy0
        o_size_mm = _get_candidate_size_mm(other)
        o_h_mm = o_size_mm.get("height_mm", o_h * 500.0)
        o_w_mm = o_size_mm.get("width_mm", o_w * 500.0)

        # La vecina también debe ser de escala similar (tamaño letra)
        if o_h_mm > max_height_mm * 1.5 and o_w_mm > max_height_mm * 1.5:
            continue

        o_center_x = (ox0 + ox1) / 2.0
        o_center_y = (oy0 + oy1) / 2.0

        # Caso A: Alineación Horizontal (típico texto horizontal 'L-01', 'TAG')
        h_ratio = abs(c_h - o_h) / max(1e-5, max(c_h, o_h))
        dy_center = abs(c_center_y - o_center_y)
        dx_gap = max(0.0, max(cx0, ox0) - min(cx1, ox1))

        if h_ratio <= 0.45 and dy_center <= max(0.008, 0.45 * c_h) and dx_gap <= max_cluster_gap_ratio * c_w:
            aligned_horizontal_count += 1

        # Caso B: Alineación Vertical (texto vertical de líneas o notas)
        w_ratio = abs(c_w - o_w) / max(1e-5, max(c_w, o_w))
        dx_center = abs(c_center_x - o_center_x)
        dy_gap = max(0.0, max(cy0, oy0) - min(cy1, oy1))

        if w_ratio <= 0.45 and dx_center <= max(0.008, 0.45 * c_w) and dy_gap <= max_cluster_gap_ratio * c_h:
            aligned_vertical_count += 1

    # Si encontramos al menos 1 vecino estrechamente alineado simulando letras consecutivas
    if aligned_horizontal_count >= 1 or aligned_vertical_count >= 1:
        _store_shape_in_candidate(candidate, "text_like")
        return True

    return False


def _store_shape_in_candidate(candidate: Any, shape: str) -> None:
    """Guarda primitive_shape en candidate.attributes de forma segura."""
    if hasattr(candidate, "attributes") and isinstance(candidate.attributes, dict):
        candidate.attributes["primitive_shape"] = shape
    elif isinstance(candidate, dict):
        if "attributes" not in candidate or not isinstance(candidate["attributes"], dict):
            candidate["attributes"] = {}
        candidate["attributes"]["primitive_shape"] = shape


def _get_candidate_bbox_norm(candidate: Any) -> Optional[List[float]]:
    """Extrae el bbox normalizado [x0, y0, x1, y1] del candidato."""
    if hasattr(candidate, "bbox_normalized") and candidate.bbox_normalized:
        return candidate.bbox_normalized
    if isinstance(candidate, dict):
        if "bbox_normalized" in candidate and candidate["bbox_normalized"]:
            return candidate["bbox_normalized"]
        if "bbox" in candidate and candidate["bbox"]:
            return candidate["bbox"]
    return None


def _get_candidate_size_mm(candidate: Any) -> Dict[str, Any]:
    """Extrae estimated_physical_size_mm del candidato."""
    if hasattr(candidate, "estimated_physical_size_mm") and isinstance(candidate.estimated_physical_size_mm, dict):
        return candidate.estimated_physical_size_mm
    if isinstance(candidate, dict) and isinstance(candidate.get("estimated_physical_size_mm"), dict):
        return candidate["estimated_physical_size_mm"]
    return {}
