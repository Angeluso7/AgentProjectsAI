from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.db.models.document_memory import (
    DocumentSheet, SheetRegion, ExtractedTable, ExtractedTableCell, ExtractedText
)
from app.db.models.intake_extractions import StructuredSymbol
from app.db.repositories.document_repository import DocumentRepository
from app.db.repositories.operations_repository import OperationsRepository
from app.services.tables.extractor import TableExtractor
from app.services.tables.classifier import TableClassifier
from app.services.ocr.service import OcrService
from app.services.layout.service import LayoutService
from app.core.logging import logger

class TableService:
    """Servicio orquestador para la extracción tabular profunda, clasificación y auditoría de celdas."""

    def __init__(self, db: Session):
        self.db = db
        self.doc_repo = DocumentRepository(db)
        self.ops_repo = OperationsRepository(db)
        self.classifier = TableClassifier()

    def extract_tables_from_sheet(
        self,
        sheet_id: str,
        force_reprocess: bool = False,
        region_id: Optional[str] = None,
        symbols: Optional[List[Any]] = None
    ) -> List[ExtractedTable]:
        sheet = self.doc_repo.get_sheet_by_id(sheet_id)
        if not sheet:
            raise ValueError(f"Lámina '{sheet_id}' no encontrada.")

        # Idempotencia: si ya existen tablas y no se fuerza reproceso
        existing_tables = self.db.query(ExtractedTable).filter(ExtractedTable.sheet_id == sheet_id).all()
        if existing_tables and not force_reprocess and not region_id:
            logger.info(f"Lámina {sheet_id} ya posee {len(existing_tables)} tablas extraídas. Retornando existentes.")
            return existing_tables

        if existing_tables and force_reprocess:
            for t in existing_tables:
                self.db.delete(t)
            self.db.commit()

        # Asegurar textos OCR
        texts = self.doc_repo.list_texts_by_sheet(sheet_id)
        if not texts:
            logger.info(f"Hoja {sheet_id} sin OCR. Ejecutando OCR previo...")
            ocr_svc = OcrService(self.db)
            texts = ocr_svc.process_sheet_ocr(sheet_id=sheet_id, force_reprocess=False)

        # Obtener regiones candidatas a tabla
        regions = self.doc_repo.list_regions_by_sheet(sheet_id)
        if not regions:
            layout_svc = LayoutService(self.db)
            regions = layout_svc.segment_sheet_layout(sheet_id=sheet_id, force_reprocess=False)

        # Obtener símbolos existentes en la lámina para vincular con celdas tabulares
        if symbols is None:
            symbols = []
            try:
                from app.db.models.document_memory import DetectedSymbol
                det_symbols = self.db.query(DetectedSymbol).filter(DetectedSymbol.sheet_id == sheet_id).all()
                symbols.extend(det_symbols)
            except Exception as ex:
                logger.warning(f"Aviso consultando DetectedSymbol para lámina {sheet_id}: {ex}")

            try:
                from app.db.models.intake_extractions import ExtractedItem
                struct_symbols = self.db.query(StructuredSymbol).join(
                    ExtractedItem, StructuredSymbol.extracted_item_id == ExtractedItem.id
                ).filter(
                    (ExtractedItem.source_asset_id == sheet_id) | (ExtractedItem.page_number == sheet.sheet_number)
                ).all()
                symbols.extend(struct_symbols)
            except Exception as ex:
                logger.warning(f"Aviso consultando StructuredSymbol para lámina {sheet_id}: {ex}")

        candidate_regions = [r for r in regions if r.region_type == "table_candidate"]
        if region_id:
            candidate_regions = [r for r in candidate_regions if r.id == region_id]

        # Si no hay regiones marcadas como table_candidate, evaluar si existen bloques de cuadro
        if not candidate_regions:
            logger.info(f"Hoja {sheet_id} sin regiones 'table_candidate' detectadas en layout.")
            return []

        extractor = TableExtractor(width_px=sheet.width_px, height_px=sheet.height_px)
        created_tables: List[ExtractedTable] = []

        for reg in candidate_regions:
            table_dto = extractor.extract_from_region(
                region_bbox_norm=reg.bbox_normalized,
                texts=texts,
                symbols=symbols
            )
            if not table_dto:
                continue

            # Clasificar tipo de tabla
            sample_cells = [c.text for c in table_dto.cells[:10]]
            table_type, class_conf, explanation = self.classifier.classify_table(
                title=table_dto.title,
                headers=table_dto.headers,
                sample_cells=sample_cells
            )

            # Promediar confianza global
            overall_conf = round((table_dto.confidence * 0.6) + (class_conf * 0.4), 3)

            db_table = ExtractedTable(
                document_id=sheet.document_id,
                sheet_id=sheet.id,
                region_id=reg.id,
                table_type=table_type,
                title=table_dto.title,
                bbox=table_dto.bbox,
                bbox_normalized=table_dto.bbox_normalized,
                row_count=table_dto.row_count,
                column_count=table_dto.column_count,
                confidence=overall_conf,
                extraction_status="extracted" if overall_conf >= 0.70 else "low_confidence",
                source_engine="spatial_grid_reconstruction",
                source_version="v1.0",
                raw_structure=table_dto.raw_structure
            )
            self.db.add(db_table)
            self.db.commit()
            self.db.refresh(db_table)

            # Persistir celdas individuales y actualizar linaje de símbolos
            for c in table_dto.cells:
                db_cell = ExtractedTableCell(
                    table_id=db_table.id,
                    row_index=c.row_index,
                    column_index=c.column_index,
                    text=c.text,
                    normalized_text=c.normalized_text,
                    confidence=c.confidence,
                    bbox=c.bbox,
                    bbox_normalized=c.bbox_normalized,
                    is_header=c.is_header,
                    source_text_refs=c.source_text_refs,
                    cell_type=c.cell_type,
                    symbol_id=c.symbol_id,
                    has_symbol=c.has_symbol
                )
                self.db.add(db_cell)

                if c.symbol_id:
                    db_sym = self.db.query(StructuredSymbol).filter(StructuredSymbol.id == c.symbol_id).first()
                    if db_sym:
                        db_sym.source_table_id = db_table.id
                        db_sym.row_index = c.row_index
                        db_sym.col_index = c.column_index
                        db_sym.cell_bbox = c.bbox_normalized
                        db_sym.layout_context = "inside_table"

            self.db.commit()

            # Evaluación de Políticas de Confianza y ReviewTask
            self._evaluate_table_policies(db_table, sheet, overall_conf, explanation)

            created_tables.append(db_table)

        logger.info(f"Lámina {sheet.id}: {len(created_tables)} tablas extraídas y persistidas.")
        return created_tables

    def _evaluate_table_policies(
        self,
        table: ExtractedTable,
        sheet: DocumentSheet,
        overall_conf: float,
        explanation: str
    ) -> None:
        """Evalúa políticas de confianza y registra tareas de revisión o trazas de auditoría."""
        policy = self.ops_repo.get_active_policy(applies_to="table_structure")
        auto_thresh = policy.auto_accept_threshold if policy else 0.82
        review_thresh = policy.review_threshold if policy else 0.60

        if overall_conf < auto_thresh or table.table_type == "unknown_table" or table.row_count < 2:
            reason = "TABLE_STRUCTURE_UNCERTAIN" if overall_conf >= review_thresh else "LOW_CONFIDENCE_TABLE"
            msg = f"Tabla '{table.title}' ({table.table_type}) con confianza {overall_conf:.2f} < {auto_thresh:.2f}. {explanation}"
            
            # Crear ReviewTask
            self.ops_repo.create_review_task(
                task_type="table_structure_review",
                reason_code=reason,
                reason_message=msg,
                confidence=overall_conf,
                priority="medium" if overall_conf >= review_thresh else "high",
                project_id=sheet.document.project_id if sheet.document else None,
                document_id=sheet.document_id,
                sheet_id=sheet.id,
                evidence_refs={"table_id": table.id, "bbox": table.bbox_normalized},
                payload={
                    "table_id": table.id,
                    "title": table.title,
                    "table_type": table.table_type,
                    "row_count": table.row_count,
                    "column_count": table.column_count,
                    "raw_structure": table.raw_structure
                }
            )

            # Registrar DecisionTrace
            self.ops_repo.record_trace(
                trace_type="table_extraction",
                entity_type="ExtractedTable",
                entity_id=table.id,
                engine_name="TableExtractor",
                engine_version="v1.0",
                confidence=overall_conf,
                policy_id=policy.id if policy else None,
                policy_version=policy.version if policy else "1.0",
                decision_status="review_required" if overall_conf >= review_thresh else "exception_required",
                explanation=msg,
                document_id=sheet.document_id,
                sheet_id=sheet.id
            )
        else:
            self.ops_repo.record_trace(
                trace_type="table_extraction",
                entity_type="ExtractedTable",
                entity_id=table.id,
                engine_name="TableExtractor",
                engine_version="v1.0",
                confidence=overall_conf,
                policy_id=policy.id if policy else None,
                policy_version=policy.version if policy else "1.0",
                decision_status="auto_accepted",
                explanation=f"Tabla '{table.title}' clasificada como '{table.table_type}' con confianza {overall_conf:.2f} >= auto_accept {auto_thresh:.2f}.",
                document_id=sheet.document_id,
                sheet_id=sheet.id
            )

    def extract_tables_from_document(
        self,
        document_id: str,
        force_reprocess: bool = False
    ) -> List[Dict[str, Any]]:
        sheets = self.doc_repo.list_sheets_by_document(document_id)
        if not sheets:
            raise ValueError(f"El documento '{document_id}' no posee láminas.")

        results = []
        for s in sheets:
            tables = self.extract_tables_from_sheet(sheet_id=s.id, force_reprocess=force_reprocess)
            results.append({
                "sheet_id": s.id,
                "sheet_number": s.sheet_number,
                "tables_count": len(tables),
                "tables": [t.id for t in tables]
            })
        return results

    def get_table(self, table_id: str) -> Optional[ExtractedTable]:
        return self.db.query(ExtractedTable).filter(ExtractedTable.id == table_id).first()

    def list_tables_by_sheet(self, sheet_id: str) -> List[ExtractedTable]:
        return self.db.query(ExtractedTable).filter(ExtractedTable.sheet_id == sheet_id).all()

    def list_cells_by_table(self, table_id: str) -> List[ExtractedTableCell]:
        return self.db.query(ExtractedTableCell).filter(
            ExtractedTableCell.table_id == table_id
        ).order_by(ExtractedTableCell.row_index.asc(), ExtractedTableCell.column_index.asc()).all()
