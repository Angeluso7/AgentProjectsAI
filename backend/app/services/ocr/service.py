import time
import os
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.db.models.document_memory import ExtractedText, DocumentSheet, Document
from app.db.repositories.document_repository import DocumentRepository
from app.services.ocr.engines import (
    BaseOcrEngine,
    PaddleOcrEngine,
    TesseractOcrEngine,
    VectorPdfOcrEngine,
    OcrRawBlock
)
from app.core.logging import logger

class OcrService:
    """Servicio orquestador de OCR espacial para láminas técnicas de arquitectura e ingeniería."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = DocumentRepository(db)
        self._engines: Dict[str, BaseOcrEngine] = {
            "paddleocr": PaddleOcrEngine(),
            "tesseract": TesseractOcrEngine(),
            "vector_pdf": VectorPdfOcrEngine(),
        }

    def get_available_engines(self) -> Dict[str, bool]:
        """Consulta el estado de disponibilidad de cada motor de OCR en el sistema."""
        return {name: engine.is_available() for name, engine in self._engines.items()}

    def _select_engine(self, preferred_engine: Optional[str] = None, has_pdf: bool = False) -> BaseOcrEngine:
        """Selecciona el motor de OCR adecuado según preferencia y disponibilidad."""
        if preferred_engine:
            if preferred_engine in self._engines:
                eng = self._engines[preferred_engine]
                if eng.is_available():
                    return eng
                logger.warning(f"Motor preferido '{preferred_engine}' no está disponible. Buscando fallback automático.")

        # Estrategia inteligente:
        # 1. Si hay PDF vectorial y está disponible, usar vector_pdf (precisión 100% y 0 CER)
        if has_pdf and self._engines["vector_pdf"].is_available():
            return self._engines["vector_pdf"]

        # 2. Si no, usar Tesseract (probado y disponible en contenedor) o PaddleOCR
        for name in ["tesseract", "paddleocr", "vector_pdf"]:
            eng = self._engines[name]
            if eng.is_available():
                return eng

        raise RuntimeError(
            "Ningún motor de OCR está disponible. Verifique la instalación de 'tesseract-ocr' o 'pymupdf'."
        )

    def process_sheet_ocr(
        self,
        sheet_id: str,
        force_reprocess: bool = False,
        preferred_engine: Optional[str] = None,
        engine: Optional[str] = None
    ) -> List[ExtractedText]:
        preferred_engine = preferred_engine or engine
        """Ejecuta OCR sobre una lámina rasterizada, persiste los bloques de texto con coordenadas
        normalizadas y maneja la idempotencia mediante eliminación de textos previos si se fuerza el reproceso.
        """
        sheet = self.repo.get_sheet_by_id(sheet_id)
        if not sheet:
            raise ValueError(f"Lámina con ID '{sheet_id}' no encontrada.")

        # Idempotencia: Si ya existen textos y no se fuerza el reproceso, retornar existentes
        existing_texts = self.repo.list_texts_by_sheet(sheet_id)
        if existing_texts and not force_reprocess:
            logger.info(
                f"Lámina {sheet_id} ya posee {len(existing_texts)} bloques de texto. Retornando existentes."
            )
            return existing_texts

        # Si se fuerza el reprocesamiento, limpiar registros anteriores
        if existing_texts and force_reprocess:
            deleted_count = self.repo.delete_texts_by_sheet(sheet_id)
            logger.info(f"Reprocesamiento forzado: Eliminados {deleted_count} bloques de texto previos para sheet {sheet_id}.")

        # Validar existencia de imagen raster o PDF original
        image_path = sheet.raster_image_path
        has_raster = bool(image_path and os.path.exists(image_path))

        doc = self.repo.get_by_id(sheet.document_id)
        pdf_path = doc.file_path if doc else None
        page_index = max(0, sheet.sheet_number - 1)
        has_pdf = bool(pdf_path and os.path.exists(pdf_path))

        if not has_raster and not has_pdf:
            logger.warning(
                f"Lámina {sheet_id} no posee imagen raster válida ni archivo PDF en disco. Retornando 0 textos OCR."
            )
            return []

        engine = self._select_engine(preferred_engine, has_pdf=has_pdf)
        logger.info(
            f"Iniciando OCR en hoja #{sheet.sheet_number} ({sheet.id}) usando motor '{engine.name}'"
        )

        start_time = time.time()
        raw_blocks: List[OcrRawBlock] = engine.extract(
            image_path=image_path,
            width_px=sheet.width_px,
            height_px=sheet.height_px,
            pdf_path=pdf_path,
            page_index=page_index
        )
        elapsed = time.time() - start_time

        # Convertir a entidades ORM
        extracted_entities: List[ExtractedText] = []
        for block in raw_blocks:
            extracted_entities.append(
                ExtractedText(
                    sheet_id=sheet.id,
                    text=block.text,
                    clean_text=block.clean_text,
                    bbox=block.bbox,
                    bbox_normalized=block.bbox_normalized,
                    confidence=block.confidence,
                    angle=block.angle,
                    source=block.source
                )
            )

        # Persistir en base de datos
        persisted = self.repo.add_extracted_texts(extracted_entities)
        logger.info(
            f"OCR completado para hoja #{sheet.sheet_number}: {len(persisted)} bloques extraídos en {elapsed:.2f}s."
        )
        return persisted

    def process_document_ocr(
        self,
        document_id: str,
        force_reprocess: bool = False,
        preferred_engine: Optional[str] = None,
        engine: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        preferred_engine = preferred_engine or engine
        """Ejecuta OCR sobre todas las hojas rasterizadas de un documento."""
        doc = self.repo.get_by_id(document_id)
        if not doc:
            raise ValueError(f"Documento con ID '{document_id}' no encontrado.")

        sheets = self.repo.list_sheets_by_document(document_id)
        if not sheets:
            raise ValueError(f"El documento '{document_id}' no tiene láminas rasterizadas.")

        summaries: List[Dict[str, Any]] = []
        for sheet in sheets:
            start_t = time.time()
            texts = self.process_sheet_ocr(
                sheet_id=sheet.id,
                force_reprocess=force_reprocess,
                preferred_engine=preferred_engine
            )
            elapsed = time.time() - start_t
            
            avg_conf = (
                sum(t.confidence for t in texts) / len(texts) if texts else 1.0
            )
            engine_used = texts[0].source if texts else (preferred_engine or "none")

            summaries.append({
                "sheet_id": sheet.id,
                "sheet_number": sheet.sheet_number,
                "texts_count": len(texts),
                "avg_confidence": round(avg_conf, 4),
                "engine_used": engine_used,
                "execution_time_sec": round(elapsed, 3)
            })

        return summaries
