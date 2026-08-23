import os
import time
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.db.models.document_memory import (
    DocumentSheet, SheetRegion, TitleBlockExtraction, ExtractedText
)
from app.db.models.template_memory import TitleBlockTemplate
from app.db.repositories.document_repository import DocumentRepository
from app.services.ocr.service import OcrService
from app.services.layout.analyzer import LayoutAnalyzer, LayoutSegment
from app.core.logging import logger

class LayoutService:
    """Servicio de segmentación de layout macro-regional y extracción estructurada de viñetas."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = DocumentRepository(db)

    def segment_sheet_layout(
        self,
        sheet_id: str,
        force_reprocess: bool = False
    ) -> List[SheetRegion]:
        """Segmenta la lámina en macro-regiones y las persiste en sheet_regions."""
        sheet = self.repo.get_sheet_by_id(sheet_id)
        if not sheet:
            raise ValueError(f"Lámina '{sheet_id}' no encontrada.")

        # Idempotencia: Si ya existen regiones y no se fuerza el reproceso, retornar existentes
        existing_regions = self.repo.list_regions_by_sheet(sheet_id)
        if existing_regions and not force_reprocess:
            logger.info(f"Lámina {sheet_id} ya posee {len(existing_regions)} regiones de layout. Retornando existentes.")
            return existing_regions

        # Asegurar que existan textos OCR para la hoja
        texts = self.repo.list_texts_by_sheet(sheet_id)
        if not texts:
            logger.info(f"Hoja {sheet_id} sin OCR previo. Ejecutando extracción OCR automática.")
            ocr_svc = OcrService(self.db)
            texts = ocr_svc.process_sheet_ocr(sheet_id=sheet.id, force_reprocess=False)

        # Si se fuerza el reproceso, limpiar regiones previas
        if existing_regions and force_reprocess:
            self.repo.delete_regions_by_sheet(sheet_id)

        analyzer = LayoutAnalyzer(width_px=sheet.width_px, height_px=sheet.height_px)
        segments: List[LayoutSegment] = analyzer.segment_layout(texts)

        # Persistir regiones en base de datos
        db_regions: List[SheetRegion] = []
        for seg in segments:
            db_regions.append(
                SheetRegion(
                    sheet_id=sheet.id,
                    region_type=seg.region_type,
                    polygon_points=seg.polygon_points,
                    bbox=seg.bbox,
                    bbox_normalized=seg.bbox_normalized,
                    confidence=seg.confidence,
                    detection_method=seg.detection_method,
                    source_version="v1.0",
                    attributes=seg.attributes
                )
            )

        persisted = self.repo.add_sheet_regions(db_regions)
        logger.info(f"Layout segmentado para hoja {sheet.id}: {len(persisted)} regiones creadas.")
        return persisted

    def match_and_extract_title_block(
        self,
        sheet_id: str,
        force_reprocess: bool = False,
        template_id: Optional[str] = None
    ) -> TitleBlockExtraction:
        """Compara la viñeta contra template_memory y extrae campos estructurados."""
        sheet = self.repo.get_sheet_by_id(sheet_id)
        if not sheet:
            raise ValueError(f"Lámina '{sheet_id}' no encontrada.")

        existing_extr = self.repo.get_title_block_extraction(sheet_id)
        if existing_extr and not force_reprocess:
            logger.info(f"Lámina {sheet_id} ya posee extracción de viñeta previa. Retornando existente.")
            return existing_extr

        # Asegurar regiones de layout
        regions = self.repo.list_regions_by_sheet(sheet_id)
        if not regions:
            regions = self.segment_sheet_layout(sheet_id=sheet_id, force_reprocess=force_reprocess)

        tb_region = next((r for r in regions if r.region_type == "title_block"), None)
        if not tb_region:
            # Fallback a región sintética en esquina inferior derecha
            tb_segment = LayoutSegment(
                region_type="title_block",
                bbox=[sheet.width_px * 0.70, sheet.height_px * 0.70, sheet.width_px * 0.98, sheet.height_px * 0.98],
                bbox_normalized=[0.70, 0.70, 0.98, 0.98],
                polygon_points=[[0.7, 0.7], [0.98, 0.7], [0.98, 0.98], [0.7, 0.98]],
                confidence=0.40,
                detection_method="fallback"
            )
        else:
            tb_segment = LayoutSegment(
                region_type=tb_region.region_type,
                bbox=tb_region.bbox,
                bbox_normalized=tb_region.bbox_normalized,
                polygon_points=tb_region.polygon_points,
                confidence=tb_region.confidence,
                detection_method=tb_region.detection_method,
                attributes=tb_region.attributes or {}
            )

        texts = self.repo.list_texts_by_sheet(sheet_id)
        analyzer = LayoutAnalyzer(width_px=sheet.width_px, height_px=sheet.height_px)

        # Buscar plantilla activa en template_memory
        template = None
        if template_id:
            template = self.db.query(TitleBlockTemplate).filter(TitleBlockTemplate.id == template_id).first()
        else:
            template = self.db.query(TitleBlockTemplate).filter(TitleBlockTemplate.is_active == True).first()

        res = analyzer.extract_title_block_fields(tb_segment, texts, template=template)
        fields = res["fields"]

        # Crear o actualizar registro TitleBlockExtraction
        extraction = TitleBlockExtraction(
            sheet_id=sheet.id,
            template_id=template.id if template else None,
            match_score=res["match_score"],
            extraction_status=res["extraction_status"],
            sheet_code=fields["sheet_code"],
            sheet_title=fields["sheet_title"],
            revision=fields["revision"],
            scale_text=fields["scale_text"],
            date_text=fields["date_text"],
            project_name=fields["project_name"],
            discipline=fields["discipline"],
            drawn_by=fields["drawn_by"],
            checked_by=fields["checked_by"],
            approved_by=fields["approved_by"],
            matched_anchors=res["matched_anchors"],
            unmatched_required_fields=res["unmatched_required_fields"],
            raw_fields=res["raw_fields"]
        )

        persisted = self.repo.upsert_title_block_extraction(extraction)

        # Actualizar metadatos directos en la lámina
        if fields["sheet_code"]:
            sheet.sheet_code = fields["sheet_code"]
        if fields["sheet_title"]:
            sheet.title = fields["sheet_title"]
        if fields["scale_text"]:
            sheet.scale = fields["scale_text"]
        if fields["revision"]:
            sheet.revision = fields["revision"]
        if fields["date_text"]:
            sheet.date_str = fields["date_text"]
        self.db.commit()

        logger.info(
            f"Viñeta extraída para hoja {sheet.sheet_number}: Código={sheet.sheet_code}, Escala={sheet.scale}, Rev={sheet.revision} (Score: {res['match_score']})"
        )
        return persisted

    def process_sheet(self, sheet_id: str, force_reprocess: bool = False) -> Dict[str, Any]:
        """Procesa layout y extracción de viñeta sobre una lámina."""
        start_t = time.time()
        regions = self.segment_sheet_layout(sheet_id=sheet_id, force_reprocess=force_reprocess)
        extraction = self.match_and_extract_title_block(sheet_id=sheet_id, force_reprocess=force_reprocess)
        elapsed = time.time() - start_t

        return {
            "sheet_id": sheet_id,
            "regions_count": len(regions),
            "title_block": {
                "sheet_code": extraction.sheet_code,
                "sheet_title": extraction.sheet_title,
                "scale": extraction.scale_text,
                "revision": extraction.revision,
                "date": extraction.date_text,
                "match_score": extraction.match_score,
                "status": extraction.extraction_status,
                "matched_anchors": extraction.matched_anchors,
                "unmatched_required_fields": extraction.unmatched_required_fields
            },
            "execution_time_sec": round(elapsed, 3)
        }

    def process_document(self, document_id: str, force_reprocess: bool = False) -> List[Dict[str, Any]]:
        """Procesa layout y viñeta para todas las hojas de un documento."""
        sheets = self.repo.list_sheets_by_document(document_id)
        if not sheets:
            raise ValueError(f"El documento '{document_id}' no tiene láminas registradas.")

        results: List[Dict[str, Any]] = []
        for sheet in sheets:
            results.append(self.process_sheet(sheet_id=sheet.id, force_reprocess=force_reprocess))
        return results
