import os
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.repositories.document_repository import DocumentRepository
from app.schemas.symbol import (
    DetectedSymbolRead, SymbolDetectProcessRequest, SheetSymbolsSummaryResponse,
    PromoteSymbolToTemplateRequest, PromoteSymbolToTemplateResponse, LegendExtractionRequest,
    StructuredSymbolUpdate, BatchCurateSymbolsRequest, BatchCurateSymbolsResponse,
    DeduplicateSymbolsRequest, DeduplicateSymbolsResponse,
    MergeVariantRequest, SplitVariantRequest,
    BatchPromoteToTemplateRequest, BatchPromoteToTemplateResponse,
    CanonicalCatalogResponse, CanonicalTemplateItem, CandidateCurationDetail,
    SymbolOccurrenceItem, MatchCandidateRequest, MatchCandidateResponse, MatchedTemplateItem
)
from app.schemas.intake_extractions import StructuredSymbolRead
from app.schemas.operations import AsyncJobAcceptedResponse
from app.services.symbols.service import SymbolService
from app.services.operations.service import OperationsService
from app.services.symbols.legend_table_extractor import LegendTableExtractor
from app.services.symbols.deduplication_service import SymbolDeduplicationService
from app.services.symbols.template_normalizer import TemplateNormalizer
from app.services.symbols.template_matcher import TemplateMatcher
from app.db.models.intake_extractions import StructuredSymbol, ExtractedItem, SourceExtraction
from app.db.models.template_memory import SymbolLibrary, SymbolTemplate

router = APIRouter()


@router.get("/sheets/{sheet_id}", response_model=List[DetectedSymbolRead])
def list_sheet_symbols(
    sheet_id: str,
    symbol_type: Optional[str] = Query(None, description="Filtra por tipo de símbolo"),
    discipline: Optional[str] = Query(None, description="Filtra por disciplina"),
    db: Session = Depends(get_db)
):
    """Lista los símbolos detectados en una lámina técnica."""
    service = SymbolService(db)
    return service.list_symbols_by_sheet(sheet_id=sheet_id, symbol_type=symbol_type, discipline=discipline)

@router.get("/sheets/{sheet_id}/summary", response_model=SheetSymbolsSummaryResponse)
def get_sheet_symbols_summary(sheet_id: str, db: Session = Depends(get_db)):
    """Obtiene el conteo y resumen agrupado de símbolos por categoría y disciplina en una lámina."""
    service = SymbolService(db)
    return service.get_sheet_summary(sheet_id)

@router.get("/documents/{document_id}", response_model=List[DetectedSymbolRead])
def list_document_symbols(document_id: str, db: Session = Depends(get_db)):
    """Lista todos los símbolos detectados en las diferentes láminas de un documento."""
    service = SymbolService(db)
    return service.list_symbols_by_document(document_id)

@router.get("/structured", response_model=List[StructuredSymbolRead])
def list_structured_symbols(
    family: Optional[str] = Query(None, description="Filtra por canonical_symbol_family"),
    render_mode: Optional[str] = Query(None, description="vector, raster, mixed"),
    layout_context: Optional[str] = Query(None, description="inside_table, semi_structured_legend, free_layout"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """Lista símbolos estructurados persistidos con metadatos de Fase 1."""
    query = db.query(StructuredSymbol)
    if family:
        query = query.filter(StructuredSymbol.canonical_symbol_family == family)
    if render_mode:
        query = query.filter(StructuredSymbol.source_render_mode == render_mode)
    if layout_context:
        query = query.filter(StructuredSymbol.layout_context == layout_context)

    return query.order_by(StructuredSymbol.created_at.desc()).offset(offset).limit(limit).all()


@router.get("/curation-candidates", response_model=List[CandidateCurationDetail])
def list_curation_candidates(
    extraction_id: Optional[str] = Query(None, description="Filtra por ID de extracción"),
    rule_document_id: Optional[str] = Query(None, description="Filtra por ID de documento normativo"),
    family: Optional[str] = Query(None, description="Filtra por canonical_symbol_family"),
    render_mode: Optional[str] = Query(None, description="vector, raster, mixed"),
    review_status: Optional[str] = Query(None, description="accepted, rejected, pending, flagged_false_positive"),
    search: Optional[str] = Query(None, description="Búsqueda por nombre o texto"),
    limit: int = Query(100, ge=1, le=300),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """
    Retorna la lista de candidatos estructurados para curación HITL (Fase 2).
    Incluye las 9 evidencias obligatorias para decisión:
    crop, documento origen, página, contexto estructural, OCR asociado,
    modo render, score, grupo visual actual y posible plantilla similar existente.
    """
    dedup_svc = SymbolDeduplicationService(db)
    query = db.query(StructuredSymbol, ExtractedItem, SourceExtraction)\
              .join(ExtractedItem, StructuredSymbol.extracted_item_id == ExtractedItem.id)\
              .outerjoin(SourceExtraction, ExtractedItem.extraction_id == SourceExtraction.id)

    if extraction_id:
        query = query.filter(ExtractedItem.extraction_id == extraction_id)
    if rule_document_id:
        from app.db.models.intake_extractions import RuleDocument, RuleDocumentItem
        rule_doc = db.query(RuleDocument).filter(RuleDocument.id == rule_document_id).first()
        if rule_doc and rule_doc.source_extraction_id:
            query = query.filter(ExtractedItem.extraction_id == rule_doc.source_extraction_id)
        else:
            item_ids = [r[0] for r in db.query(RuleDocumentItem.extracted_item_id).filter(RuleDocumentItem.rule_document_id == rule_document_id).all() if r[0]]
            if item_ids:
                query = query.filter(ExtractedItem.id.in_(item_ids))
    if family and family != "all":
        query = query.filter(StructuredSymbol.canonical_symbol_family == family)
    if render_mode and render_mode != "all":
        query = query.filter(StructuredSymbol.source_render_mode == render_mode)
    if review_status and review_status != "all":
        query = query.filter(ExtractedItem.review_status == review_status)
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (StructuredSymbol.symbol_name.ilike(search_pattern)) |
            (ExtractedItem.description.ilike(search_pattern)) |
            (ExtractedItem.ocr_text.ilike(search_pattern))
        )

    rows = query.order_by(StructuredSymbol.created_at.desc()).offset(offset).limit(limit).all()

    # Pre-cargar ocurrencias multipágina para candidatos agrupados
    group_ids = {sym.visual_variant_group_id for sym, _, _ in rows if sym.visual_variant_group_id}
    group_occurrences_map: Dict[str, List[SymbolOccurrenceItem]] = {}
    if group_ids:
        group_rows = db.query(StructuredSymbol, ExtractedItem, SourceExtraction)\
                       .join(ExtractedItem, StructuredSymbol.extracted_item_id == ExtractedItem.id)\
                       .outerjoin(SourceExtraction, ExtractedItem.extraction_id == SourceExtraction.id)\
                       .filter(StructuredSymbol.visual_variant_group_id.in_(group_ids))\
                       .all()
        for g_sym, g_item, g_ext in group_rows:
            occ = SymbolOccurrenceItem(
                page_number=g_item.page_number or 1,
                sheet_id=getattr(g_item, "source_asset_id", None) or getattr(g_sym, "sheet_id", None),
                bbox_normalized=g_item.bbox_normalized or getattr(g_sym, "bbox_normalized", []) or [],
                source_document_id=g_ext.id if g_ext else getattr(g_sym, "source_document_id", None),
                crop_image_path=g_sym.crop_image_path or g_item.crop_image_path,
                document_title=g_ext.title if g_ext else None
            )
            group_occurrences_map.setdefault(g_sym.visual_variant_group_id, []).append(occ)

    results: List[CandidateCurationDetail] = []
    for sym, item, ext in rows:
        best_match = dedup_svc.find_best_existing_template(sym)

        # Ocurrencias multipágina del símbolo o grupo de variantes
        occurrences = group_occurrences_map.get(sym.visual_variant_group_id, []) if sym.visual_variant_group_id else []
        if not occurrences:
            occurrences = [
                SymbolOccurrenceItem(
                    page_number=item.page_number or 1,
                    sheet_id=item.source_asset_id,
                    bbox_normalized=item.bbox_normalized or [],
                    source_document_id=ext.id if ext else None,
                    crop_image_path=sym.crop_image_path or item.crop_image_path,
                    document_title=ext.title if ext else None
                )
            ]

        results.append(CandidateCurationDetail(
            id=sym.id,
            extracted_item_id=item.id,
            symbol_name=sym.symbol_name,
            standard_family=sym.standard_family,
            discipline=sym.discipline,
            category=sym.category,
            crop_image_path=sym.crop_image_path,
            confidence_score=sym.confidence_score or 0.0,
            source_render_mode=sym.source_render_mode or "vector",
            layout_context=sym.layout_context or "inside_table",
            context_association_mode=sym.context_association_mode or "row_band",
            standard_reference=sym.standard_reference,
            canonical_symbol_family=sym.canonical_symbol_family,
            visual_variant_group_id=sym.visual_variant_group_id,
            estimated_physical_size_mm=sym.estimated_physical_size_mm,
            reused_for_matching_count=sym.reused_for_matching_count or 0,
            false_positive_count=sym.false_positive_count or 0,
            human_validation_notes=sym.human_validation_notes,
            created_at=sym.created_at or datetime.now(timezone.utc),
            document_title=ext.title if ext else None,
            document_id=ext.id if ext else None,
            extraction_id=item.extraction_id,
            page_number=item.page_number or 1,
            ocr_associated_text=item.ocr_text,
            review_status=item.review_status or "pending",
            possible_matching_template=best_match,
            source_table_id=sym.source_table_id,
            row_index=sym.row_index,
            col_index=sym.col_index,
            cell_bbox=sym.cell_bbox,
            row_bbox=sym.row_bbox,
            occurrences=occurrences
        ))

    return results


@router.get("/canonical-catalog", response_model=CanonicalCatalogResponse)
def get_canonical_catalog(
    library_name: str = Query("ISA-5.1 Piping Library", description="Nombre de la biblioteca"),
    discipline: str = Query("piping", description="Disciplina"),
    db: Session = Depends(get_db)
):
    """
    Retorna el catálogo consolidado de plantillas canónicas de piping e instrumentación
    persistidas en template_memory para búsqueda y matching.
    """
    lib = db.query(SymbolLibrary).filter(SymbolLibrary.name == library_name).first()
    if not lib:
        # Retorna catálogo vacío inicializado
        return CanonicalCatalogResponse(
            library_id="NEW",
            library_name=library_name,
            discipline=discipline,
            standard_name="ISA-5.1 / ASME B16.34",
            total_templates=0,
            family_counts={},
            templates=[]
        )

    templates = db.query(SymbolTemplate).filter(SymbolTemplate.library_id == lib.id)\
                  .order_by(SymbolTemplate.created_at.desc()).all()

    family_counts: Dict[str, int] = {}
    template_items: List[CanonicalTemplateItem] = []

    for t in templates:
        family_counts[t.symbol_class] = family_counts.get(t.symbol_class, 0) + 1
        desc = t.feature_descriptors or {}

        template_items.append(CanonicalTemplateItem(
            id=t.id,
            library_id=t.library_id,
            symbol_class=t.symbol_class,
            display_name=t.display_name,
            aliases=t.aliases or [],
            image_template_path=t.image_template_path,
            vector_svg_path=t.vector_svg_path,
            approved_by=desc.get("approved_by"),
            approved_at=desc.get("approved_at"),
            source_structured_symbol_id=desc.get("source_structured_symbol_id"),
            visual_variant_group_id=desc.get("visual_variant_group_id"),
            feature_descriptors=desc,
            created_at=t.created_at or datetime.now(timezone.utc)
        ))

    return CanonicalCatalogResponse(
        library_id=lib.id,
        library_name=lib.name,
        discipline=lib.discipline,
        standard_name=lib.standard_name,
        total_templates=len(templates),
        family_counts=family_counts,
        templates=template_items
    )


@router.get("/{symbol_id}", response_model=DetectedSymbolRead)
def get_symbol_detail(symbol_id: str, db: Session = Depends(get_db)):
    """Obtiene el detalle y atributos de un símbolo detectado."""
    service = SymbolService(db)
    sym = service.get_symbol(symbol_id)
    if not sym:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Símbolo '{symbol_id}' no encontrado.")
    return sym


@router.post("/sheets/{sheet_id}", response_model=List[DetectedSymbolRead])
def detect_sheet_symbols_sync(
    sheet_id: str,
    request: Optional[SymbolDetectProcessRequest] = None,
    db: Session = Depends(get_db)
):
    """Ejecuta detección visual síncrona de símbolos sobre la región drawing_area de una lámina."""
    service = SymbolService(db)
    force = request.force_reprocess if request else False
    engine = request.engine if request and request.engine else "yolo_sahi_hybrid"
    thresh = request.confidence_threshold if request and request.confidence_threshold else 0.50
    disc = request.discipline if request else None

    try:
        return service.detect_sheet_symbols(
            sheet_id=sheet_id,
            force_reprocess=force,
            engine=engine,
            confidence_threshold=thresh,
            discipline=disc
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error en detección de símbolos: {str(e)}")

@router.post("/sheets/{sheet_id}/async", response_model=AsyncJobAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
def detect_sheet_symbols_async(
    sheet_id: str,
    request: Optional[SymbolDetectProcessRequest] = None,
    db: Session = Depends(get_db)
):
    """Encola detección visual asíncrona de símbolos para una lámina (HTTP 202 Accepted)."""
    ops_svc = OperationsService(db)
    repo = DocumentRepository(db)
    sheet = repo.get_sheet_by_id(sheet_id)
    if not sheet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lámina '{sheet_id}' no encontrada.")

    job = ops_svc.submit_job(
        job_type="sheet_symbol_detect",
        target_type="sheet",
        target_id=sheet_id,
        project_id=sheet.document.project_id if sheet.document else None,
        input_payload=request.model_dump() if request else {},
        async_mode=True
    )
    return AsyncJobAcceptedResponse(
        job_id=job.id,
        status="queued",
        poll_url=f"/api/v1/jobs/{job.id}",
        message="Detección visual de símbolos encolada para procesamiento asíncrono.",
        target_type="sheet",
        target_id=sheet_id
    )

@router.post("/documents/{document_id}/async", response_model=AsyncJobAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
def detect_document_symbols_async(
    document_id: str,
    request: Optional[SymbolDetectProcessRequest] = None,
    db: Session = Depends(get_db)
):
    """Encola detección visual asíncrona de símbolos para todas las láminas de un documento (HTTP 202 Accepted)."""
    ops_svc = OperationsService(db)
    repo = DocumentRepository(db)
    doc = repo.get_by_id(document_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Documento '{document_id}' no encontrado.")

    job = ops_svc.submit_job(
        job_type="document_symbol_detect",
        target_type="document",
        target_id=document_id,
        project_id=doc.project_id,
        input_payload=request.model_dump() if request else {},
        async_mode=True
    )
    return AsyncJobAcceptedResponse(
        job_id=job.id,
        status="queued",
        poll_url=f"/api/v1/jobs/{job.id}",
        message="Detección visual de símbolos para documento encolada para procesamiento asíncrono.",
        target_type="document",
        target_id=document_id
    )


@router.post("/extract-legend")
async def extract_legend_symbols(
    request: Optional[LegendExtractionRequest] = None,
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """
    Fábrica de candidatos de simbología (Fase 1).
    Extrae candidatos de tablas/leyendas de piping usando PyMuPDF get_drawings() (vector)
    o OpenCV morfológico (raster como fallback).
    Persiste en BD con metadatos contextuales cuando se suministra extraction_id.
    """
    pdf_bytes = None
    page_num = 1
    disc = "piping"
    pref_mode = "auto"
    ext_id = None

    if file:
        pdf_bytes = await file.read()
    elif request and request.file_path and os.path.exists(request.file_path):
        with open(request.file_path, "rb") as f:
            pdf_bytes = f.read()

    if request:
        page_num = request.page_number
        disc = request.discipline
        pref_mode = request.preferred_mode
        ext_id = request.extraction_id

    if not pdf_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe proporcionar un archivo PDF mediante upload o una ruta existente en file_path."
        )

    extractor = LegendTableExtractor(db)
    results = extractor.extract_from_pdf_page(
        pdf_bytes=pdf_bytes,
        page_number=page_num,
        extraction_id=ext_id,
        discipline=disc,
        preferred_mode=pref_mode
    )

    return {
        "success": True,
        "page_number": page_num,
        "symbols_count": len(results),
        "extraction_mode": results[0].source_render_mode if results else pref_mode,
        "symbols": [r.__dict__ for r in results]
    }



# ============================================================================
# FASE 2: CURACIÓN HITL, EDICIÓN, DEDUPLICACIÓN Y PROMOCIÓN CONTROLADA
# ============================================================================

@router.patch("/structured/{symbol_id}", response_model=StructuredSymbolRead)
def update_structured_symbol(
    symbol_id: str,
    payload: StructuredSymbolUpdate,
    db: Session = Depends(get_db)
):
    """
    Edición asistida (HITL) de un candidato de símbolo:
    permite corregir nombre técnico, familia canónica, estándar, notas o estado de revisión.
    """
    sym = db.query(StructuredSymbol).filter(StructuredSymbol.id == symbol_id).first()
    if not sym:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="StructuredSymbol no encontrado.")

    if payload.symbol_name is not None:
        sym.symbol_name = payload.symbol_name
    if payload.canonical_symbol_family is not None:
        sym.canonical_symbol_family = payload.canonical_symbol_family
    if payload.category is not None:
        sym.category = payload.category
    if payload.standard_reference is not None:
        sym.standard_reference = payload.standard_reference
    if payload.human_validation_notes is not None:
        sym.human_validation_notes = payload.human_validation_notes
    if payload.visual_variant_group_id is not None:
        sym.visual_variant_group_id = payload.visual_variant_group_id

    # Sincronizar con ExtractedItem correspondiente
    item = db.query(ExtractedItem).filter(ExtractedItem.id == sym.extracted_item_id).first()
    if item:
        if payload.symbol_name is not None:
            item.tag_or_code = payload.symbol_name
        if payload.review_status is not None:
            item.review_status = payload.review_status
            if payload.review_status == "flagged_false_positive":
                sym.false_positive_count = (sym.false_positive_count or 0) + 1

    db.commit()
    db.refresh(sym)
    return sym


@router.post("/curate", response_model=BatchCurateSymbolsResponse)
def batch_curate_symbols(
    payload: BatchCurateSymbolsRequest,
    db: Session = Depends(get_db)
):
    """
    Acciones de validación humana masiva o individual sobre candidatos de símbolos:
    aprobar ('accept'), rechazar ('reject'), marcar falso positivo ('flag_false_positive')
    o actualizar familia canónica.
    """
    symbols = db.query(StructuredSymbol).filter(StructuredSymbol.id.in_(payload.symbol_ids)).all()
    if not symbols:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ningún símbolo encontrado para curar.")

    accepted, rejected, flagged, updated = 0, 0, 0, 0
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    reviewer = payload.reviewer or "auditor"

    for sym in symbols:
        item = db.query(ExtractedItem).filter(ExtractedItem.id == sym.extracted_item_id).first()

        if payload.action == "accept":
            if item:
                item.review_status = "accepted"
            note = f"Aprobado por {reviewer} en {now_str}"
            if payload.notes:
                note += f": {payload.notes}"
            sym.human_validation_notes = f"{sym.human_validation_notes or ''} | {note}".strip(" |")
            accepted += 1
            updated += 1

        elif payload.action == "reject":
            if item:
                item.review_status = "rejected"
            note = f"Rechazado por {reviewer} en {now_str}"
            if payload.notes:
                note += f": {payload.notes}"
            sym.human_validation_notes = f"{sym.human_validation_notes or ''} | {note}".strip(" |")
            rejected += 1
            updated += 1

        elif payload.action == "flag_false_positive":
            if item:
                item.review_status = "flagged_false_positive"
            sym.false_positive_count = (sym.false_positive_count or 0) + 1
            note = f"Marcado como Falso Positivo por {reviewer} en {now_str}"
            if payload.notes:
                note += f": {payload.notes}"
            sym.human_validation_notes = f"{sym.human_validation_notes or ''} | {note}".strip(" |")
            flagged += 1
            updated += 1

        elif payload.action == "update_family":
            if payload.canonical_symbol_family:
                sym.canonical_symbol_family = payload.canonical_symbol_family
            if payload.standard_reference:
                sym.standard_reference = payload.standard_reference
            updated += 1

    db.commit()

    return BatchCurateSymbolsResponse(
        updated_count=updated,
        accepted_count=accepted,
        rejected_count=rejected,
        flagged_count=flagged,
        message=f"Curación procesada con éxito: {updated} símbolos actualizados ({accepted} aprobados, {rejected} rechazados, {flagged} falsos positivos)."
    )


@router.post("/deduplicate", response_model=DeduplicateSymbolsResponse)
def deduplicate_symbols(
    payload: DeduplicateSymbolsRequest,
    db: Session = Depends(get_db)
):
    """
    Ejecuta el motor de deduplicación multi-factor (dHash 64-bit + semántica + geométrica)
    sobre los candidatos, identificando duplicados y asignando 'visual_variant_group_id'.
    """
    dedup_svc = SymbolDeduplicationService(db)
    return dedup_svc.run_deduplication(payload)


@router.post("/variants/merge")
def merge_symbol_variant(
    payload: MergeVariantRequest,
    db: Session = Depends(get_db)
):
    """Fusiona manualmente un símbolo con un grupo de variantes existente."""
    dedup_svc = SymbolDeduplicationService(db)
    ok = dedup_svc.merge_symbol_into_group(payload.symbol_id, payload.target_group_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Símbolo no encontrado.")
    return {"success": True, "message": f"Símbolo fusionado al grupo de variantes {payload.target_group_id}."}


@router.post("/variants/split")
def split_symbol_variant(
    payload: SplitVariantRequest,
    db: Session = Depends(get_db)
):
    """Separa manualmente un símbolo de su grupo de variantes, asignándole un nuevo ID independiente."""
    dedup_svc = SymbolDeduplicationService(db)
    try:
        new_group_id = dedup_svc.split_symbol_from_group(payload.symbol_id)
        return {"success": True, "new_group_id": new_group_id, "message": f"Símbolo separado con éxito en nuevo grupo {new_group_id}."}
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


@router.post("/promote-to-template", response_model=PromoteSymbolToTemplateResponse)
def promote_symbol_to_template(
    payload: PromoteSymbolToTemplateRequest,
    db: Session = Depends(get_db)
):
    """
    Promueve un símbolo estructurado curado a la biblioteca canónica SymbolTemplate
    para ser utilizado en matching y búsqueda futura.
    Cumple condición de auditoría de Fase 2: registra quién aprobó, cuándo,
    candidato de origen, nombre final, familia final y grupo de variantes.
    """
    sym = db.query(StructuredSymbol).filter(StructuredSymbol.id == payload.structured_symbol_id).first()
    if not sym:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="StructuredSymbol no encontrado.")

    # Buscar o crear SymbolLibrary
    lib = db.query(SymbolLibrary).filter(SymbolLibrary.name == payload.library_name).first()
    if not lib:
        lib = SymbolLibrary(
            id=str(uuid.uuid4()),
            name=payload.library_name,
            discipline=payload.discipline or sym.discipline,
            standard_name=sym.standard_reference or "ISA-5.1 / ASME B16.34",
            description="Biblioteca generada a partir de símbolos curados y aprobados de leyendas de piping."
        )
        db.add(lib)
        db.flush()

    now_utc = datetime.now(timezone.utc).isoformat()
    reviewer = payload.reviewer or "auditor"
    template_id = str(uuid.uuid4())

    # Generación y normalización de la máscara geométrica 128x128
    normalizer = TemplateNormalizer()
    norm_mask_path = None
    mask_hash = None
    hu_moments = []
    contour_sig = []
    ar = 1.0
    primitives = {}

    if sym.crop_image_path and os.path.exists(sym.crop_image_path):
        try:
            storage_dir = "/app/storage/symbol_templates"
            os.makedirs(storage_dir, exist_ok=True)
            target_mask_path = os.path.join(storage_dir, f"{template_id}_mask.png")
            norm_res = normalizer.normalize_from_path(sym.crop_image_path, output_mask_path=target_mask_path)
            norm_mask_path = target_mask_path
            mask_hash = norm_res.get("mask_hash")
            hu_moments = norm_res.get("hu_moments") or []
            contour_sig = norm_res.get("contour_signature") or []
            ar = float(norm_res.get("aspect_ratio") or 1.0)
            primitives = norm_res.get("primitive_signature") or {}
        except Exception as e:
            pass

    template = SymbolTemplate(
        id=template_id,
        library_id=lib.id,
        symbol_class=sym.canonical_symbol_family,
        display_name=sym.symbol_name,
        aliases=[sym.symbol_name, sym.category] if sym.category else [sym.symbol_name],
        image_template_path=sym.crop_image_path,
        normalized_mask_path=norm_mask_path,
        mask_hash=mask_hash,
        hu_moments=hu_moments,
        contour_signature=contour_sig,
        aspect_ratio=ar,
        primitive_signature=primitives,
        rotation_invariance_mode="orthogonal_4_rotations",
        is_active_for_detection=True,
        vector_svg_path=sym.svg_path,
        feature_descriptors={
            "canonical_family": sym.canonical_symbol_family,
            "source_render_mode": sym.source_render_mode,
            "estimated_physical_size_mm": sym.estimated_physical_size_mm,
            "user_notes": payload.user_notes,
            "approved_by": reviewer,
            "approved_at": now_utc,
            "source_structured_symbol_id": sym.id,
            "source_extracted_item_id": sym.extracted_item_id,
            "final_name": sym.symbol_name,
            "final_family": sym.canonical_symbol_family,
            "visual_variant_group_id": sym.visual_variant_group_id,
            "standard_reference": sym.standard_reference or "ISA-5.1"
        }
    )
    db.add(template)

    # Actualizar StructuredSymbol y ExtractedItem
    sym.reused_for_matching_count = (sym.reused_for_matching_count or 0) + 1
    approval_note = f"Promovido a plantilla por {reviewer} en {now_utc}"
    if payload.user_notes:
        approval_note += f": {payload.user_notes}"
    sym.human_validation_notes = f"{sym.human_validation_notes or ''} | {approval_note}".strip(" |")

    item = db.query(ExtractedItem).filter(ExtractedItem.id == sym.extracted_item_id).first()
    if item:
        item.review_status = "accepted"

    db.commit()

    return PromoteSymbolToTemplateResponse(
        template_id=template.id,
        library_id=lib.id,
        symbol_class=template.symbol_class,
        display_name=template.display_name,
        reused_for_matching_count=sym.reused_for_matching_count,
        message="Símbolo promovido exitosamente a plantilla reutilizable.",
        approved_by=reviewer,
        approved_at=now_utc,
        source_structured_symbol_id=sym.id,
        visual_variant_group_id=sym.visual_variant_group_id
    )


@router.post("/promote-batch", response_model=BatchPromoteToTemplateResponse)
def batch_promote_to_template(
    payload: BatchPromoteToTemplateRequest,
    db: Session = Depends(get_db)
):
    """
    Promoción controlada en lote de múltiples candidatos aprobados a SymbolTemplate.
    """
    symbols = db.query(StructuredSymbol).filter(StructuredSymbol.id.in_(payload.structured_symbol_ids)).all()
    if not symbols:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No se encontraron símbolos para promover.")

    lib = db.query(SymbolLibrary).filter(SymbolLibrary.name == payload.library_name).first()
    if not lib:
        lib = SymbolLibrary(
            id=str(uuid.uuid4()),
            name=payload.library_name,
            discipline=payload.discipline,
            standard_name="ISA-5.1 / ASME B16.34",
            description="Biblioteca generada a partir de símbolos curados y aprobados."
        )
        db.add(lib)
        db.flush()

    now_utc = datetime.now(timezone.utc).isoformat()
    reviewer = payload.reviewer or "auditor"
    promoted_list: List[Dict[str, Any]] = []
    normalizer = TemplateNormalizer()

    for sym in symbols:
        template_id = str(uuid.uuid4())
        norm_mask_path = None
        mask_hash = None
        hu_moments = []
        contour_sig = []
        ar = 1.0
        primitives = {}

        if sym.crop_image_path and os.path.exists(sym.crop_image_path):
            try:
                storage_dir = "/app/storage/symbol_templates"
                os.makedirs(storage_dir, exist_ok=True)
                target_mask_path = os.path.join(storage_dir, f"{template_id}_mask.png")
                norm_res = normalizer.normalize_from_path(sym.crop_image_path, output_mask_path=target_mask_path)
                norm_mask_path = target_mask_path
                mask_hash = norm_res.get("mask_hash")
                hu_moments = norm_res.get("hu_moments") or []
                contour_sig = norm_res.get("contour_signature") or []
                ar = float(norm_res.get("aspect_ratio") or 1.0)
                primitives = norm_res.get("primitive_signature") or {}
            except Exception:
                pass

        template = SymbolTemplate(
            id=template_id,
            library_id=lib.id,
            symbol_class=sym.canonical_symbol_family,
            display_name=sym.symbol_name,
            aliases=[sym.symbol_name, sym.category] if sym.category else [sym.symbol_name],
            image_template_path=sym.crop_image_path,
            normalized_mask_path=norm_mask_path,
            mask_hash=mask_hash,
            hu_moments=hu_moments,
            contour_signature=contour_sig,
            aspect_ratio=ar,
            primitive_signature=primitives,
            rotation_invariance_mode="orthogonal_4_rotations",
            is_active_for_detection=True,
            vector_svg_path=sym.svg_path,
            feature_descriptors={
                "canonical_family": sym.canonical_symbol_family,
                "source_render_mode": sym.source_render_mode,
                "estimated_physical_size_mm": sym.estimated_physical_size_mm,
                "user_notes": payload.user_notes,
                "approved_by": reviewer,
                "approved_at": now_utc,
                "source_structured_symbol_id": sym.id,
                "source_extracted_item_id": sym.extracted_item_id,
                "final_name": sym.symbol_name,
                "final_family": sym.canonical_symbol_family,
                "visual_variant_group_id": sym.visual_variant_group_id,
                "standard_reference": sym.standard_reference or "ISA-5.1"
            }
        )
        db.add(template)

        sym.reused_for_matching_count = (sym.reused_for_matching_count or 0) + 1
        note = f"Promovido a plantilla en lote por {reviewer} ({now_utc})"
        sym.human_validation_notes = f"{sym.human_validation_notes or ''} | {note}".strip(" |")

        item = db.query(ExtractedItem).filter(ExtractedItem.id == sym.extracted_item_id).first()
        if item:
            item.review_status = "accepted"

        promoted_list.append({
            "template_id": template.id,
            "display_name": template.display_name,
            "symbol_class": template.symbol_class,
            "visual_variant_group_id": sym.visual_variant_group_id
        })

    db.commit()

    return BatchPromoteToTemplateResponse(
        promoted_count=len(promoted_list),
        library_id=lib.id,
        library_name=lib.name,
        promoted_templates=promoted_list,
        message=f"{len(promoted_list)} símbolos promovidos exitosamente a {lib.name}."
    )


@router.post("/{symbol_id}/promote-to-template", response_model=PromoteSymbolToTemplateResponse)
def promote_symbol_by_id(
    symbol_id: str,
    library_name: Optional[str] = Query("ISA-5.1 Piping Library"),
    discipline: Optional[str] = Query("piping"),
    reviewer: Optional[str] = Query("auditor"),
    db: Session = Depends(get_db)
):
    """Promueve un símbolo individual a SymbolTemplate activo utilizando su identificador en URL."""
    req = PromoteSymbolToTemplateRequest(
        structured_symbol_id=symbol_id,
        library_name=library_name,
        discipline=discipline,
        reviewer=reviewer
    )
    return promote_symbol_to_template(req, db)


@router.post("/match-candidate", response_model=MatchCandidateResponse)
def match_candidate(
    payload: MatchCandidateRequest,
    db: Session = Depends(get_db)
):
    """
    Motor seguro de matching determinista (OpenCV NCC + Hu Moments).
    El backend resuelve internamente la ruta del recorte del candidato validando que
    tenga evidencia geométrica física real.
    No acepta rutas arbitrarias del cliente.
    """
    # 1. Resolver entidad candidata en el servidor
    sym = db.query(StructuredSymbol).filter(StructuredSymbol.id == payload.candidate_id).first()
    crop_path = None
    if sym:
        crop_path = sym.crop_image_path
    else:
        item = db.query(ExtractedItem).filter(ExtractedItem.id == payload.candidate_id).first()
        if item:
            meta = item.metadata_payload or {}
            crop_path = meta.get("crop_image_path") or meta.get("visual_crop_path")

    if not crop_path or not os.path.exists(crop_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró recorte de imagen válido o el candidato no tiene evidencia geométrica física."
        )

    # 2. Cargar imagen y ejecutar TemplateMatcher
    import cv2
    img = cv2.imread(crop_path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No se pudo decodificar la imagen del candidato en el servidor."
        )

    matcher = TemplateMatcher(db)
    matches_raw = matcher.match_candidate_image(
        candidate_img=img,
        discipline=payload.discipline,
        organization_id=payload.organization_id,
        allowed_rotations=payload.allowed_rotations,
        top_k=payload.top_k
    )

    matches = [MatchedTemplateItem(**m) for m in matches_raw]
    best = matches[0] if matches else None
    total_templates = db.query(SymbolTemplate).filter(SymbolTemplate.is_active_for_detection == True).count()

    return MatchCandidateResponse(
        candidate_id=payload.candidate_id,
        total_templates_evaluated=total_templates,
        best_match=best,
        matches=matches
    )




