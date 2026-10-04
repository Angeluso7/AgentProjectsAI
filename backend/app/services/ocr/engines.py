import os
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple
from app.core.logging import logger

@dataclass
class OcrRawBlock:
    text: str
    clean_text: str
    bbox: List[float]               # [x0, y0, x1, y1] en píxeles absolutos
    bbox_normalized: List[float]    # [x0, y0, x1, y1] normalizado 0.0 - 1.0
    confidence: float               # 0.0 - 1.0
    angle: float                    # 0.0, 90.0, 180.0, 270.0
    source: str                     # paddleocr, tesseract, vector_pdf

def clean_text_string(raw_text: str) -> str:
    """Normaliza espacios en blanco y remueve caracteres no imprimibles o ruido."""
    if not raw_text:
        return ""
    # Reemplazar saltos de línea y múltiples espacios por un único espacio
    text = re.sub(r"\s+", " ", raw_text).strip()
    return text

def normalize_and_clamp_bbox(
    x0: float, y0: float, x1: float, y1: float,
    width_px: int, height_px: int
) -> Tuple[List[float], List[float]]:
    """Calcula la caja en píxeles y la caja normalizada [0.0 - 1.0], asegurando límites válidos."""
    # Asegurar orden min/max
    min_x = min(x0, x1)
    max_x = max(x0, x1)
    min_y = min(y0, y1)
    max_y = max(y0, y1)

    # Pixel bbox
    px_bbox = [round(min_x, 2), round(min_y, 2), round(max_x, 2), round(max_y, 2)]

    # Normalized bbox (Top-Left 0.0, 0.0 -> Bottom-Right 1.0, 1.0)
    w = max(width_px, 1)
    h = max(height_px, 1)
    
    norm_x0 = max(0.0, min(1.0, min_x / w))
    norm_y0 = max(0.0, min(1.0, min_y / h))
    norm_x1 = max(norm_x0, min(1.0, max_x / w))
    norm_y1 = max(norm_y0, min(1.0, max_y / h))

    norm_bbox = [
        round(norm_x0, 5),
        round(norm_y0, 5),
        round(norm_x1, 5),
        round(norm_y1, 5)
    ]
    return px_bbox, norm_bbox

def estimate_polygon_rotation(points: List[List[float]]) -> float:
    """Estima el ángulo dominante (0, 90, 180, 270) de una caja de 4 puntos."""
    if len(points) < 2:
        return 0.0
    dx = points[1][0] - points[0][0]
    dy = points[1][1] - points[0][1]
    
    # Tolerancia angular para clasificar en cuadrantes principales
    if abs(dx) >= abs(dy):
        return 180.0 if dx < 0 else 0.0
    else:
        return 270.0 if dy < 0 else 90.0


class BaseOcrEngine:
    name: str = "base"

    def is_available(self) -> bool:
        raise NotImplementedError

    def extract(
        self,
        image_path: str,
        width_px: int,
        height_px: int,
        pdf_path: Optional[str] = None,
        page_index: int = 0
    ) -> List[OcrRawBlock]:
        raise NotImplementedError


class PaddleOcrEngine(BaseOcrEngine):
    """Motor de OCR basado en PaddleOCR con clasificación de orientación automática."""
    name: str = "paddleocr"

    def __init__(self):
        self._ocr_instance = None

    def is_available(self) -> bool:
        try:
            import paddleocr
            import paddle  # PaddlePaddle runtime must be present
            return True
        except (ImportError, Exception):
            return False

    def _get_ocr(self):
        if self._ocr_instance is None:
            os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
            from paddleocr import PaddleOCR
            try:
                self._ocr_instance = PaddleOCR(use_angle_cls=True, lang="es")
            except TypeError:
                try:
                    self._ocr_instance = PaddleOCR(use_textline_orientation=True, lang="es")
                except TypeError:
                    self._ocr_instance = PaddleOCR(lang="es")
        return self._ocr_instance

    def extract(
        self,
        image_path: str,
        width_px: int,
        height_px: int,
        pdf_path: Optional[str] = None,
        page_index: int = 0
    ) -> List[OcrRawBlock]:
        if not self.is_available():
            raise RuntimeError("PaddleOCR / PaddlePaddle no está instalado o disponible en este entorno.")

        ocr = self._get_ocr()
        results = ocr.ocr(image_path, cls=True)
        blocks: List[OcrRawBlock] = []

        if not results or not results[0]:
            return blocks

        for line in results[0]:
            if not line or len(line) < 2:
                continue
            poly_points, (raw_text, confidence) = line
            clean_text = clean_text_string(raw_text)
            if not clean_text:
                continue

            xs = [pt[0] for pt in poly_points]
            ys = [pt[1] for pt in poly_points]
            px_bbox, norm_bbox = normalize_and_clamp_bbox(
                min(xs), min(ys), max(xs), max(ys), width_px, height_px
            )
            angle = estimate_polygon_rotation(poly_points)

            blocks.append(
                OcrRawBlock(
                    text=raw_text,
                    clean_text=clean_text,
                    bbox=px_bbox,
                    bbox_normalized=norm_bbox,
                    confidence=round(float(confidence), 4),
                    angle=angle,
                    source=self.name
                )
            )
        return blocks


class TesseractOcrEngine(BaseOcrEngine):
    """Motor de OCR de fallback basado en Tesseract con segmentación dispersa (PSM 11)."""
    name: str = "tesseract"

    def is_available(self) -> bool:
        try:
            import pytesseract
            from PIL import Image
            pytesseract.get_tesseract_version()
            return True
        except (ImportError, Exception):
            return False

    def extract(
        self,
        image_path: str,
        width_px: int,
        height_px: int,
        pdf_path: Optional[str] = None,
        page_index: int = 0
    ) -> List[OcrRawBlock]:
        if not self.is_available():
            raise RuntimeError("Pytesseract no está instalado en este entorno.")

        import pytesseract
        from PIL import Image

        image = Image.open(image_path)
        # PSM 11 = Sparse text (ideal para planos con textos distribuidos)
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT, config="--psm 11")
        blocks: List[OcrRawBlock] = []

        n_boxes = len(data["text"])
        for i in range(n_boxes):
            raw_text = data["text"][i]
            clean_text = clean_text_string(raw_text)
            if not clean_text:
                continue

            conf = float(data["conf"][i])
            if conf < 0:
                continue  # Bloques de estructura sin texto

            x = float(data["left"][i])
            y = float(data["top"][i])
            w = float(data["width"][i])
            h = float(data["height"][i])

            px_bbox, norm_bbox = normalize_and_clamp_bbox(x, y, x + w, y + h, width_px, height_px)

            blocks.append(
                OcrRawBlock(
                    text=raw_text,
                    clean_text=clean_text,
                    bbox=px_bbox,
                    bbox_normalized=norm_bbox,
                    confidence=round(conf / 100.0, 4),
                    angle=0.0,
                    source=self.name
                )
            )
        return blocks


class VectorPdfOcrEngine(BaseOcrEngine):
    """Motor de extracción directa de capas de texto vectorial del PDF (PyMuPDF).
    Ideal para planos vectoriales exportados directamente de AutoCAD, Revit o ArchiCAD.
    """
    name: str = "vector_pdf"

    def is_available(self) -> bool:
        try:
            import fitz
            return True
        except ImportError:
            return False

    def extract(
        self,
        image_path: str,
        width_px: int,
        height_px: int,
        pdf_path: Optional[str] = None,
        page_index: int = 0
    ) -> List[OcrRawBlock]:
        if not self.is_available():
            raise RuntimeError("PyMuPDF (fitz) no disponible para extracción vectorial.")
        if not pdf_path or not os.path.exists(pdf_path):
            return []

        import fitz
        doc = fitz.open(pdf_path)
        if page_index >= len(doc):
            doc.close()
            return []

        page = doc[page_index]
        page_rect = page.rect
        scale_x = width_px / page_rect.width if page_rect.width > 0 else 1.0
        scale_y = height_px / page_rect.height if page_rect.height > 0 else 1.0

        # get_text("blocks") -> (x0, y0, x1, y1, "lines", block_no, block_type)
        # block_type 0 = texto
        raw_blocks = page.get_text("blocks")
        blocks: List[OcrRawBlock] = []

        for b in raw_blocks:
            if len(b) < 6 or b[5] != 0:
                continue  # Ignorar bloques no textuales (ej: imágenes embebidas)
            x0, y0, x1, y1, raw_text = b[0], b[1], b[2], b[3], b[4]
            clean_text = clean_text_string(raw_text)
            if not clean_text:
                continue

            # Escalar a píxeles de la imagen raster
            px_x0 = x0 * scale_x
            px_y0 = y0 * scale_y
            px_x1 = x1 * scale_x
            px_y1 = y1 * scale_y

            px_bbox, norm_bbox = normalize_and_clamp_bbox(
                px_x0, px_y0, px_x1, px_y1, width_px, height_px
            )

            blocks.append(
                OcrRawBlock(
                    text=raw_text.strip(),
                    clean_text=clean_text,
                    bbox=px_bbox,
                    bbox_normalized=norm_bbox,
                    confidence=1.0,
                    angle=float(page.rotation),
                    source=self.name
                )
            )

        doc.close()
        return blocks
