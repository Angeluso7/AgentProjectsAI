from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.db.models.document_memory import (
    DocumentSheet, SheetRegion, DetectedSymbol
)
from app.db.models.template_memory import SymbolTemplate, SymbolLibrary
from app.db.repositories.document_repository import DocumentRepository
from app.db.repositories.operations_repository import OperationsRepository
from app.services.symbols.detector import SymbolDetector, DetectedSymbolDTO
from app.services.layout.service import LayoutService
from app.schemas.symbol import SheetSymbolsSummaryResponse, SymbolSummaryItem
from app.core.logging import logger

class SymbolService:
    """Servicio orquestador para la detección visual de símbolos, integración con librerías y auditoría."""

    def __init__(self, db: Session):
        self.db = db
        self.doc_repo = DocumentRepository(db)
        self.ops_repo = OperationsRepository(db)

    def detect_sheet_symbols(
        self,
        sheet_id: str,
        force_reprocess: bool = False,
        engine: str = "yolo_sahi_hybrid",
        confidence_threshold: float = 0.50,
        discipline: Optional[str] = None
    ) -> List[DetectedSymbol]:
        sheet = self.doc_repo.get_sheet_by_id(sheet_id)
        if not sheet:
            raise ValueError(f"Lámina '{sheet_id}' no encontrada.")

        # Idempotencia
        existing_symbols = self.db.query(DetectedSymbol).filter(DetectedSymbol.sheet_id == sheet_id).all()
        if existing_symbols and not force_reprocess:
            logger.info(f"Lámina {sheet_id} ya posee {len(existing_symbols)} símbolos detectados. Retornando existentes.")
            return existing_symbols

        if existing_symbols and force_reprocess:
            for s in existing_symbols:
                self.db.delete(s)
            self.db.commit()

        # Obtener o calcular drawing_area
        regions = self.doc_repo.list_regions_by_sheet(sheet_id)
        if not regions:
            layout_svc = LayoutService(self.db)
            regions = layout_svc.segment_sheet_layout(sheet_id=sheet_id, force_reprocess=False)

        drawing_region = next((r for r in regions if r.region_type == "drawing_area"), None)
        drawing_bbox_norm = drawing_region.bbox_normalized if drawing_region else [0.05, 0.05, 0.70, 0.90]

        # Consultar librerías de símbolos canónicos en template_memory
        library_templates = self.db.query(SymbolTemplate).all()

        detector = SymbolDetector(width_px=sheet.width_px, height_px=sheet.height_px)
        dto_list = detector.detect_symbols(
            image_path=sheet.raster_image_path,
            drawing_area_bbox_norm=drawing_bbox_norm,
            library_templates=library_templates,
            engine=engine,
            confidence_threshold=confidence_threshold,
            discipline_filter=discipline
        )

        created_symbols: List[DetectedSymbol] = []
        for dto in dto_list:
            sym = DetectedSymbol(
                document_id=sheet.document_id,
                sheet_id=sheet.id,
                region_id=drawing_region.id if drawing_region else None,
                symbol_type=dto.symbol_type,
                discipline=dto.discipline,
                bbox=dto.bbox,
                bbox_normalized=dto.bbox_normalized,
                confidence=dto.confidence,
                detection_status=dto.detection_status,
                source_engine=dto.source_engine,
                source_version=dto.source_version,
                matched_library_entry_id=dto.matched_library_entry_id,
                attributes=dto.attributes
            )
            self.db.add(sym)
            self.db.commit()
            self.db.refresh(sym)

            # Evaluación de Políticas de Confianza
            self._evaluate_symbol_policy(sym, sheet)
            created_symbols.append(sym)

        logger.info(f"Lámina {sheet_id}: {len(created_symbols)} símbolos detectados y persistidos.")
        return created_symbols

    def _evaluate_symbol_policy(self, symbol: DetectedSymbol, sheet: DocumentSheet) -> None:
        """Evalúa políticas de confianza y registra tareas de revisión o trazas de auditoría."""
        policy = self.ops_repo.get_active_policy(applies_to="symbol_detection")
        auto_thresh = policy.auto_accept_threshold if policy else 0.85
        review_thresh = policy.review_threshold if policy else 0.65

        if symbol.confidence < auto_thresh or symbol.symbol_type == "unknown_symbol_candidate":
            reason = "UNKNOWN_SYMBOL_CANDIDATE" if symbol.symbol_type == "unknown_symbol_candidate" else "LOW_CONFIDENCE_SYMBOL"
            msg = f"Símbolo '{symbol.symbol_type}' detectado con confianza {symbol.confidence:.2f} < {auto_thresh:.2f} en disciplina '{symbol.discipline}'."

            self.ops_repo.create_review_task(
                task_type="symbol_detection_review",
                reason_code=reason,
                reason_message=msg,
                confidence=symbol.confidence,
                priority="medium" if symbol.confidence >= review_thresh else "high",
                project_id=sheet.document.project_id if sheet.document else None,
                document_id=sheet.document_id,
                sheet_id=sheet.id,
                evidence_refs={"symbol_id": symbol.id, "bbox": symbol.bbox_normalized},
                payload={
                    "symbol_id": symbol.id,
                    "symbol_type": symbol.symbol_type,
                    "discipline": symbol.discipline,
                    "confidence": symbol.confidence,
                    "engine": symbol.source_engine,
                    "attributes": symbol.attributes
                }
            )

            self.ops_repo.record_trace(
                trace_type="symbol_detection",
                entity_type="DetectedSymbol",
                entity_id=symbol.id,
                engine_name=symbol.source_engine,
                engine_version=symbol.source_version,
                confidence=symbol.confidence,
                policy_id=policy.id if policy else None,
                policy_version=policy.version if policy else "1.0",
                decision_status="review_required" if symbol.confidence >= review_thresh else "exception_required",
                explanation=msg,
                document_id=sheet.document_id,
                sheet_id=sheet.id
            )
        else:
            self.ops_repo.record_trace(
                trace_type="symbol_detection",
                entity_type="DetectedSymbol",
                entity_id=symbol.id,
                engine_name=symbol.source_engine,
                engine_version=symbol.source_version,
                confidence=symbol.confidence,
                policy_id=policy.id if policy else None,
                policy_version=policy.version if policy else "1.0",
                decision_status="auto_accepted",
                explanation=f"Símbolo '{symbol.symbol_type}' auto-aprobado con confianza {symbol.confidence:.2f} >= {auto_thresh:.2f}.",
                document_id=sheet.document_id,
                sheet_id=sheet.id
            )

    def detect_document_symbols(
        self,
        document_id: str,
        force_reprocess: bool = False,
        engine: str = "yolo_sahi_hybrid"
    ) -> List[Dict[str, Any]]:
        sheets = self.doc_repo.list_sheets_by_document(document_id)
        if not sheets:
            raise ValueError(f"El documento '{document_id}' no posee láminas.")

        results = []
        for s in sheets:
            syms = self.detect_sheet_symbols(sheet_id=s.id, force_reprocess=force_reprocess, engine=engine)
            results.append({
                "sheet_id": s.id,
                "sheet_number": s.sheet_number,
                "symbols_count": len(syms),
                "symbols": [sym.id for sym in syms]
            })
        return results

    def get_symbol(self, symbol_id: str) -> Optional[DetectedSymbol]:
        return self.db.query(DetectedSymbol).filter(DetectedSymbol.id == symbol_id).first()

    def list_symbols_by_sheet(
        self,
        sheet_id: str,
        symbol_type: Optional[str] = None,
        discipline: Optional[str] = None
    ) -> List[DetectedSymbol]:
        query = self.db.query(DetectedSymbol).filter(DetectedSymbol.sheet_id == sheet_id)
        if symbol_type:
            query = query.filter(DetectedSymbol.symbol_type == symbol_type)
        if discipline:
            query = query.filter(DetectedSymbol.discipline == discipline)
        return query.all()

    def list_symbols_by_document(self, document_id: str) -> List[DetectedSymbol]:
        return self.db.query(DetectedSymbol).filter(DetectedSymbol.document_id == document_id).all()

    def get_sheet_summary(self, sheet_id: str) -> SheetSymbolsSummaryResponse:
        symbols = self.list_symbols_by_sheet(sheet_id)
        by_cat: Dict[str, Dict[str, Any]] = {}

        for s in symbols:
            key = f"{s.discipline}:{s.symbol_type}"
            if key not in by_cat:
                by_cat[key] = {
                    "symbol_type": s.symbol_type,
                    "discipline": s.discipline,
                    "count": 0,
                    "total_conf": 0.0
                }
            by_cat[key]["count"] += 1
            by_cat[key]["total_conf"] += s.confidence

        items = [
            SymbolSummaryItem(
                symbol_type=data["symbol_type"],
                discipline=data["discipline"],
                count=data["count"],
                average_confidence=round(data["total_conf"] / data["count"], 3)
            )
            for data in by_cat.values()
        ]

        return SheetSymbolsSummaryResponse(
            sheet_id=sheet_id,
            total_symbols=len(symbols),
            by_category=items
        )
