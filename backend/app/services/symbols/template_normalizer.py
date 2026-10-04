"""
template_normalizer.py

Servicio de normalización geométrica para SymbolTemplate:
- Binarización adaptativa / Otsu.
- Supresión de fondo y centrado de centroide en lienzo cuadrado 128x128 px.
- Extracción de los 7 Momentos de Hu invariantes a rotación y escala en escala logarítmica.
- Firma de contorno exterior (perfil de distancias radiales de 128 puntos).
- Conteo y detección de primitivas vectoriales/raster (arcos, círculos, líneas ortogonales).
- Cálculo de SHA-256 de la máscara para versionado e idempotencia.
"""

import os
import hashlib
import logging
from typing import Dict, Any, Optional, Tuple, List
import numpy as np
import cv2

logger = logging.getLogger(__name__)

CANONICAL_MASK_SIZE = 128  # 128 x 128 px


class TemplateNormalizer:
    """Normaliza recortes de símbolos técnicos a máscaras canónicas y descriptores de forma."""

    def __init__(self, target_size: int = CANONICAL_MASK_SIZE):
        self.target_size = target_size

    def normalize_from_path(self, image_path: str, output_mask_path: Optional[str] = None) -> Dict[str, Any]:
        """Carga imagen desde ruta de disco y genera la máscara y descriptores normalizados."""
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"No existe el archivo de imagen en {image_path}")

        img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
        if img is None:
            raise ValueError(f"OpenCV no pudo decodificar la imagen {image_path}")

        return self.normalize_image(img, output_mask_path=output_mask_path)

    def normalize_from_bytes(self, image_bytes: bytes, output_mask_path: Optional[str] = None) -> Dict[str, Any]:
        """Decodifica bytes de imagen en memoria y produce la máscara canónica."""
        np_arr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_UNCHANGED)
        if img is None:
            raise ValueError("No se pudieron decodificar los bytes de imagen provistos")

        return self.normalize_image(img, output_mask_path=output_mask_path)

    def normalize_image(self, img: np.ndarray, output_mask_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Ejecuta el pipeline completo de normalización geométrica:
        1. Manejo de canal alfa o conversión a escala de grises.
        2. Binarización de Otsu (primer plano = 255 blanco, fondo = 0 negro).
        3. Recorte ajustado al bounding box del símbolo y centrado en canvas 128x128.
        4. Extracción de momentos de Hu y perfil de contorno radial.
        5. Firma de primitivas geométricas.
        6. Persistencia opcional de la máscara normalizada.
        """
        # 1. Escala de grises y extracción de primer plano
        if len(img.shape) == 3 and img.shape[2] == 4:
            # Canal alfa presente
            alpha = img[:, :, 3]
            gray = cv2.cvtColor(img[:, :, :3], cv2.COLOR_BGR2GRAY)
            # Donde el alfa sea casi transparente (< 30), forzar fondo blanco
            gray[alpha < 30] = 255
        elif len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img.copy()

        # 2. Inversión si el fondo es claro (común en planos de ingeniería y PDFs)
        # Calculamos la mediana del marco exterior (bordes)
        border_pixels = np.concatenate([gray[0, :], gray[-1, :], gray[:, 0], gray[:, -1]])
        is_light_bg = np.median(border_pixels) > 127

        if is_light_bg:
            # Fondo blanco -> invertimos para que las líneas sean 255 (blancas)
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        else:
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # 3. Limpieza de ruido periférico muy pequeño (ruido de escaneo)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        binary_cleaned = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)

        # 4. Encontrar contornos principales
        contours, _ = cv2.findContours(binary_cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            # Si la limpieza eliminó todo, usar binary original
            contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            # Imagen vacía
            mask_128 = np.zeros((self.target_size, self.target_size), dtype=np.uint8)
            return self._empty_result(mask_128, output_mask_path)

        # Bounding box que engloba todos los contornos significativos
        # Descartamos componentes con área < 10 px si hay más contornos
        valid_contours = [c for c in contours if cv2.contourArea(c) >= 8] or contours
        all_pts = np.vstack(valid_contours)
        x, y, w, h = cv2.boundingRect(all_pts)

        # Aspect ratio canónico
        aspect_ratio = float(w / h) if h > 0 else 1.0

        # Recorte del objeto
        cropped_obj = binary_cleaned[y:y+h, x:x+w]

        # 5. Escalar manteniendo aspect ratio con padding para caber en (target_size - 16)
        usable_size = self.target_size - 16  # 112 px con 8 px de margen de resguardo
        scale = min(usable_size / w, usable_size / h)
        new_w = max(1, int(round(w * scale)))
        new_h = max(1, int(round(h * scale)))

        resized_obj = cv2.resize(cropped_obj, (new_w, new_h), interpolation=cv2.INTER_AREA)
        # Re-binarizar tras resize
        _, resized_obj = cv2.threshold(resized_obj, 127, 255, cv2.THRESH_BINARY)

        # Crear canvas cuadrado 128x128 con fondo negro (0)
        canvas = np.zeros((self.target_size, self.target_size), dtype=np.uint8)

        # Calcular coordenadas para centrar el centroide o la caja
        M = cv2.moments(resized_obj)
        if M["m00"] > 0:
            cx_local = int(M["m10"] / M["m00"])
            cy_local = int(M["m01"] / M["m00"])
            target_center = self.target_size // 2
            offset_x = target_center - cx_local
            offset_y = target_center - cy_local
            # Clamping para no salir de los bordes del canvas
            offset_x = max(2, min(self.target_size - new_w - 2, offset_x))
            offset_y = max(2, min(self.target_size - new_h - 2, offset_y))
        else:
            offset_x = (self.target_size - new_w) // 2
            offset_y = (self.target_size - new_h) // 2

        canvas[offset_y:offset_y+new_h, offset_x:offset_x+new_w] = resized_obj

        # 6. Descriptores de Forma: 7 Momentos de Hu en escala logarítmica con signo
        hu_moments_list = self._compute_hu_moments(canvas)

        # 7. Descriptores de Forma: Perfil de contorno radial (128 puntos equidistantes)
        contour_sig = self._compute_contour_signature(canvas)

        # 8. Firma de Primitivas Geométricas
        primitives = self._extract_primitive_signature(canvas)

        # 9. Hash canónico SHA-256 de la máscara binarizada
        mask_bytes = canvas.tobytes()
        mask_hash = hashlib.sha256(mask_bytes).hexdigest()

        # 10. Persistencia física si se proveyó ruta de salida
        if output_mask_path:
            os.makedirs(os.path.dirname(output_mask_path), exist_ok=True)
            cv2.imwrite(output_mask_path, canvas)

        return {
            "normalized_mask": canvas,
            "mask_hash": mask_hash,
            "hu_moments": hu_moments_list,
            "contour_signature": contour_sig,
            "canonical_width_px": w,
            "canonical_height_px": h,
            "aspect_ratio": round(aspect_ratio, 3),
            "primitive_signature": primitives,
            "normalized_mask_path": output_mask_path
        }

    def _compute_hu_moments(self, mask: np.ndarray) -> List[float]:
        """Calcula los 7 Momentos de Hu en escala logarítmica con signo: sign(h) * log10(|h|)."""
        moments = cv2.moments(mask)
        hu = cv2.HuMoments(moments).flatten()
        log_hu = []
        for val in hu:
            if abs(val) < 1e-15:
                log_hu.append(0.0)
            else:
                sign = 1.0 if val > 0 else -1.0
                log_hu.append(float(round(sign * np.log10(abs(val)), 4)))
        return log_hu

    def _compute_contour_signature(self, mask: np.ndarray, num_points: int = 128) -> List[float]:
        """Calcula el perfil de distancia radial del contorno exterior principal desde el centroide."""
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        if not contours:
            return [0.0] * num_points

        # Contorno con mayor área
        main_contour = max(contours, key=cv2.contourArea)
        M = cv2.moments(main_contour)
        if M["m00"] > 0:
            cx = M["m10"] / M["m00"]
            cy = M["m01"] / M["m00"]
        else:
            cx, cy = self.target_size / 2, self.target_size / 2

        pts = main_contour.reshape(-1, 2)
        if len(pts) < 4:
            return [0.0] * num_points

        # Distancias radiales
        dists = np.sqrt((pts[:, 0] - cx) ** 2 + (pts[:, 1] - cy) ** 2)
        max_d = np.max(dists) if np.max(dists) > 0 else 1.0
        normalized_dists = dists / max_d

        # Remuestrear a exactamente `num_points` equidistantes
        orig_indices = np.linspace(0, 1, len(normalized_dists))
        target_indices = np.linspace(0, 1, num_points)
        resampled = np.interp(target_indices, orig_indices, normalized_dists)

        return [float(round(v, 4)) for v in resampled]

    def _extract_primitive_signature(self, mask: np.ndarray) -> Dict[str, Any]:
        """Extrae características elementales de primitivas (círculos, líneas rectas, densidad)."""
        total_pixels = float(mask.shape[0] * mask.shape[1])
        foreground_pixels = float(np.count_nonzero(mask))
        fill_density = round(foreground_pixels / total_pixels, 4)

        # Detección de líneas rectas mediante HoughLinesP
        lines = cv2.HoughLinesP(mask, 1, np.pi / 180, threshold=20, minLineLength=15, maxLineGap=4)
        num_lines = len(lines) if lines is not None else 0

        # Detección de círculos mediante HoughCircles
        circles = cv2.HoughCircles(
            mask,
            cv2.HOUGH_GRADIENT,
            dp=1.2,
            minDist=20,
            param1=50,
            param2=22,
            minRadius=8,
            maxRadius=int(self.target_size // 2)
        )
        num_circles = len(circles[0]) if circles is not None else 0

        return {
            "fill_density": fill_density,
            "detected_straight_lines": num_lines,
            "detected_circles": num_circles,
            "has_circular_features": bool(num_circles > 0)
        }

    def _empty_result(self, mask: np.ndarray, output_path: Optional[str]) -> Dict[str, Any]:
        return {
            "normalized_mask": mask,
            "mask_hash": hashlib.sha256(mask.tobytes()).hexdigest(),
            "hu_moments": [0.0] * 7,
            "contour_signature": [0.0] * 128,
            "canonical_width_px": 0,
            "canonical_height_px": 0,
            "aspect_ratio": 1.0,
            "primitive_signature": {"fill_density": 0.0, "detected_straight_lines": 0, "detected_circles": 0, "has_circular_features": False},
            "normalized_mask_path": output_path
        }
