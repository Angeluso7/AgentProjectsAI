from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.db.models.document_memory import (
    Document, DocumentSheet, SheetRegion, DetectedSymbol
)
from app.db.models.template_memory import SymbolTemplate, SymbolLibrary
from app.db.repositories.document_repository import DocumentRepository
from app.db.repositories.operations_repository import OperationsRepository
from app.services.symbols.detector import SymbolDetector, DetectedSymbolDTO
from app.services.symbols.symbol_inventory_service import SymbolInventoryService
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
        discipline: Optional[str] = None,
        environment: Optional[str] = None
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
        drawing_bbox_norm = drawing_region.bbox_normalized if drawing_region else [0.0, 0.0, 1.0, 1.0]

        doc = getattr(sheet, "document", None) or self.db.query(Document).filter(Document.id == sheet.document_id).first()
        proj_id = doc.project_id if doc else None
        proj_doc_id = doc.id if (doc and doc.project_id) else None
        effective_env = (environment or "production").lower().strip()
        effective_discipline = discipline or (doc.metadata_info or {}).get("discipline") or (doc.project.discipline if getattr(doc, "project", None) else "piping")

        # ---------------------------------------------------------------------
        # 1. Estrategia Dual Real: Vectorial (PyMuPDF) con fallback Raster (OpenCV)
        # ---------------------------------------------------------------------
        import os
        import cv2
        import fitz
        from app.core.settings import settings
        from app.services.symbols.vector_extractor import VectorSymbolExtractor
        from app.services.symbols.raster_extractor import RasterSymbolExtractor
        from app.services.symbols.template_matcher import TemplateMatcher, AUTO_MATCH_THRESHOLD, HITL_SUGGESTION_THRESHOLD
        from app.services.symbols.symbol_inventory_service import SymbolInventoryService

        dx0, dy0, dx1, dy1 = drawing_bbox_norm

        pdf_path = None
        if doc and doc.file_path:
            if os.path.exists(doc.file_path):
                pdf_path = doc.file_path
            elif os.path.exists(os.path.join(settings.STORAGE_LOCAL_ROOT, doc.file_path)):
                pdf_path = os.path.join(settings.STORAGE_LOCAL_ROOT, doc.file_path)

        fitz_doc = None
        drawings = []
        page = None
        pw, ph = 0, 0
        if pdf_path:
            try:
                fitz_doc = fitz.open(pdf_path)
                page_num = max(1, sheet.sheet_number)
                page_idx = max(0, min(len(fitz_doc) - 1, page_num - 1))
                page = fitz_doc[page_idx]
                pw, ph = page.rect.width, page.rect.height
                drawings = page.get_drawings()
            except Exception as pdf_err:
                logger.warning(f"No se pudo inspeccionar PDF {pdf_path}: {pdf_err}")
                fitz_doc = None

        has_vector_drawings = len(drawings) >= 8
        raw_candidates = None
        render_mode = "vector"

        if fitz_doc and page and has_vector_drawings:
            logger.info(f"Lámina {sheet_id} (pág {sheet.sheet_number}): extrayendo con PIPELINE VECTORIAL ({len(drawings)} trazos).")
            region_rect = fitz.Rect(dx0 * pw, dy0 * ph, dx1 * pw, dy1 * ph)
            vec_extractor = VectorSymbolExtractor()
            raw_candidates = vec_extractor.extract_candidates_from_page(
                page=page,
                page_number=sheet.sheet_number,
                doc_uid=sheet.id[:8],
                region_rect=region_rect,
                min_size_mm=3.0,
                max_size_mm=35.0
            )
            render_mode = "vector"

        if not raw_candidates:
            # Fallback Raster: usar imagen rasterizada o renderizar desde PDF
            raster_path = sheet.raster_image_path
            if raster_path and not os.path.exists(raster_path) and os.path.exists(os.path.join(settings.STORAGE_LOCAL_ROOT, raster_path)):
                raster_path = os.path.join(settings.STORAGE_LOCAL_ROOT, raster_path)

            if (not raster_path or not os.path.exists(raster_path)) and fitz_doc and page:
                try:
                    pix = page.get_pixmap(dpi=150)
                    render_dir = os.path.join(settings.STORAGE_LOCAL_ROOT, "rendered")
                    os.makedirs(render_dir, exist_ok=True)
                    raster_path = os.path.join(render_dir, f"{sheet.id}_sheet_{sheet.sheet_number}.png")
                    pix.save(raster_path)
                    sheet.raster_image_path = raster_path
                    self.db.add(sheet)
                    self.db.commit()
                except Exception as rend_err:
                    logger.warning(f"No se pudo renderizar raster para lámina {sheet.id}: {rend_err}")

            if raster_path and os.path.exists(raster_path):
                logger.info(f"Lámina {sheet_id}: extrayendo con PIPELINE RASTER (OpenCV componentes conexos).")
                rast_extractor = RasterSymbolExtractor()
                all_rast_cands = rast_extractor.extract_candidates_from_image(
                    image_input=raster_path,
                    dpi=sheet.dpi or 150,
                    page_number=sheet.sheet_number,
                    doc_uid=sheet.id[:8],
                    min_size_mm=3.0,
                    max_size_mm=35.0
                )
                raw_candidates = [
                    c for c in all_rast_cands
                    if dx0 <= c.bbox_normalized[0] <= dx1 and dy0 <= c.bbox_normalized[1] <= dy1
                ]
                render_mode = "raster"

        created_symbols: List[DetectedSymbol] = []

        if raw_candidates is not None:
            # -----------------------------------------------------------------
            # 2. Matching determinista con TemplateMatcher contra SymbolTemplate
            # -----------------------------------------------------------------
            template_matcher = TemplateMatcher(self.db)

            for cand in raw_candidates:
                cand_img = None
                if cand.crop_image_path and os.path.exists(cand.crop_image_path):
                    cand_img = cv2.imread(cand.crop_image_path, cv2.IMREAD_UNCHANGED)

                matches = []
                if cand_img is not None:
                    matches = template_matcher.match_candidate_image(
                        candidate_img=cand_img,
                        discipline=effective_discipline
                    )

                best_match = matches[0] if matches else None
                best_score = best_match["score"] if best_match else 0.0

                bx0, by0, bx1, by1 = cand.bbox_normalized
                pixel_box = [
                    round(bx0 * sheet.width_px, 1),
                    round(by0 * sheet.height_px, 1),
                    round(bx1 * sheet.width_px, 1),
                    round(by1 * sheet.height_px, 1),
                ]

                if best_score >= AUTO_MATCH_THRESHOLD: # >= 0.82 Auto-Match
                    sym_type = best_match["symbol_class"]
                    matched_entry_id = best_match["template_id"]
                    confidence = round(best_score, 3)
                    det_status = "detected"
                    match_status = "matched"
                    rev_status = "accepted"
                    match_evidence = best_match.get("match_evidence", {})
                    match_rot = best_match.get("best_rotation_deg", 0)
                elif best_score >= HITL_SUGGESTION_THRESHOLD: # 0.68 - 0.82 Sugerencia HITL
                    sym_type = best_match["symbol_class"]
                    matched_entry_id = best_match["template_id"]
                    confidence = round(best_score, 3)
                    det_status = "low_confidence"
                    match_status = "ambiguous"
                    rev_status = "needs_review"
                    match_evidence = best_match.get("match_evidence", {})
                    match_rot = best_match.get("best_rotation_deg", 0)
                else: # < 0.68 Símbolo desconocido con geometría real
                    sym_type = "unknown_symbol_candidate"
                    matched_entry_id = None
                    confidence = round(getattr(cand, "confidence_score", 0.50), 3)
                    det_status = "low_confidence"
                    match_status = "unknown_symbol"
                    rev_status = "needs_review"
                    match_evidence = {
                        "top_score": round(best_score, 4),
                        "rejection_reason": f"Score por debajo del umbral HITL ({best_score:.3f} < {HITL_SUGGESTION_THRESHOLD})"
                    }
                    match_rot = best_match.get("best_rotation_deg", 0) if best_match else 0

                sym = DetectedSymbol(
                    document_id=sheet.document_id,
                    sheet_id=sheet.id,
                    region_id=drawing_region.id if drawing_region else None,
                    symbol_type=sym_type,
                    discipline=effective_discipline,
                    bbox=pixel_box,
                    bbox_normalized=[round(bx0, 4), round(by0, 4), round(bx1, 4), round(by1, 4)],
                    inner_drawing_bbox=[round(bx0, 4), round(by0, 4), round(bx1, 4), round(by1, 4)],
                    symbol_crop_bbox=[round(bx0, 4), round(by0, 4), round(bx1, 4), round(by1, 4)],
                    cell_bbox=[round(bx0, 4), round(by0, 4), round(bx1, 4), round(by1, 4)],
                    crop_image_path=cand.crop_image_path,
                    confidence=confidence,
                    detection_status=det_status,
                    source_engine=f"{render_mode}_symbol_extractor",
                    source_version="v1.0",
                    matched_library_entry_id=matched_entry_id,
                    matched_template_id=matched_entry_id,
                    match_score=round(best_score, 4),
                    match_score_visual=round(best_score, 4),
                    match_rotation_deg=match_rot,
                    match_method="ncc_hu_composite_v1",
                    match_evidence=match_evidence,
                    attributes=getattr(cand, "estimated_physical_size_mm", {}),
                    project_id=proj_id,
                    project_document_id=proj_doc_id,
                    record_kind="occurrence" if proj_id else "candidate",
                    environment=effective_env,
                    matching_status=match_status,
                    review_status=rev_status,
                    geometric_evidence=True,
                    geometric_confidence=0.85 if render_mode == "vector" else 0.75,
                    classification="symbol"
                )
                self.db.add(sym)
                self.db.commit()
                self.db.refresh(sym)

                SymbolInventoryService.ensure_crops_for_symbol(
                    sym,
                    raster_image_path=sheet.raster_image_path,
                    page_width_pt=sheet.width_mm * 72.0 / 25.4 if (sheet.width_mm and sheet.width_mm > 0) else 800.0,
                    page_height_pt=sheet.height_mm * 72.0 / 25.4 if (sheet.height_mm and sheet.height_mm > 0) else 600.0
                )

                self._evaluate_symbol_policy(sym, sheet)
                created_symbols.append(sym)

        else:
            # -----------------------------------------------------------------
            # 3. Fallback cuando no hay archivo físico (ej. tests unitarios)
            # -----------------------------------------------------------------
            if effective_env == "production":
                logger.warning(
                    f"Lámina {sheet_id}: modo producción sin archivo de lámina en disco. "
                    "No se generan símbolos sintéticos/placeholder. Retornando 0 detecciones."
                )
                return []

            # En sandbox/demo, permitir detector baseline con etiquetas sintéticas
            library_templates = self.db.query(SymbolTemplate).all()
            detector = SymbolDetector(width_px=sheet.width_px, height_px=sheet.height_px)
            dto_list = detector.detect_symbols(
                image_path=sheet.raster_image_path,
                drawing_area_bbox_norm=drawing_bbox_norm,
                library_templates=library_templates,
                engine=engine,
                confidence_threshold=confidence_threshold,
                discipline_filter=discipline,
                environment=effective_env
            )

            for dto in dto_list:
                sym = DetectedSymbol(
                    document_id=sheet.document_id,
                    sheet_id=sheet.id,
                    region_id=drawing_region.id if drawing_region else None,
                    symbol_type=dto.symbol_type,
                    discipline=dto.discipline,
                    bbox=dto.bbox,
                    bbox_normalized=dto.bbox_normalized,
                    inner_drawing_bbox=dto.bbox_normalized,
                    symbol_crop_bbox=dto.bbox_normalized,
                    cell_bbox=dto.bbox_normalized,
                    confidence=dto.confidence,
                    detection_status=dto.detection_status,
                    source_engine=dto.source_engine,
                    source_version=dto.source_version,
                    matched_library_entry_id=dto.matched_library_entry_id,
                    attributes=dto.attributes,
                    project_id=proj_id,
                    project_document_id=proj_doc_id,
                    record_kind="occurrence" if proj_id else "candidate",
                    environment=effective_env,
                    matching_status="unmatched",
                    geometric_evidence=False,
                    geometric_confidence=0.0,
                    classification="symbol"
                )
                self.db.add(sym)
                self.db.commit()
                self.db.refresh(sym)
                self._evaluate_symbol_policy(sym, sheet)
                created_symbols.append(sym)

        self.db.commit()
        for sym in created_symbols:
            self.db.refresh(sym)

        logger.info(f"Lámina {sheet_id}: {len(created_symbols)} símbolos reales procesados y persistidos.")
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
                evidence_refs={
                    "symbol_id": symbol.id,
                    "bbox": symbol.bbox_normalized,
                    "crop_image_path": symbol.crop_image_path
                },
                payload={
                    "symbol_id": symbol.id,
                    "symbol_type": symbol.symbol_type,
                    "discipline": symbol.discipline,
                    "confidence": symbol.confidence,
                    "crop_image_path": symbol.crop_image_path,
                    "crop_url": SymbolInventoryService.resolve_crop_url(symbol.crop_image_path),
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
        engine: str = "yolo_sahi_hybrid",
        discipline: Optional[str] = None,
        environment: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        doc = self.db.query(Document).filter(Document.id == document_id).first()
        effective_discipline = discipline
        if not effective_discipline and doc:
            meta = doc.metadata_info or {}
            effective_discipline = meta.get("discipline") or (doc.project.discipline if getattr(doc, "project", None) else None)

        sheets = self.doc_repo.list_sheets_by_document(document_id)
        if not sheets:
            raise ValueError(f"El documento '{document_id}' no posee láminas.")

        results = []
        for s in sheets:
            syms = self.detect_sheet_symbols(
                sheet_id=s.id,
                force_reprocess=force_reprocess,
                engine=engine,
                discipline=effective_discipline,
                environment=environment
            )
            matched_count = sum(1 for sym in syms if sym.matching_status == "matched")
            unknown_count = sum(1 for sym in syms if sym.matching_status == "unknown_symbol")
            unmatched_count = sum(1 for sym in syms if sym.matching_status == "unmatched")
            has_active_catalog = any(
                sym.match_evidence.get("catalog_status") != "no_active_catalog"
                for sym in syms if sym.match_evidence
            )
            results.append({
                "sheet_id": s.id,
                "sheet_number": s.sheet_number,
                "symbols_count": len(syms),
                "symbols": [sym.id for sym in syms],
                "active_catalog_found": has_active_catalog,
                "matched_count": matched_count,
                "unknown_count": unknown_count,
                "unmatched_count": unmatched_count
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
