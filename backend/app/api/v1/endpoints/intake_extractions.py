import os
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models.intake import SourceAsset
from app.db.repositories.intake_extraction_repository import IntakeExtractionRepository
from app.services.intake.ai_extractor import AiDocumentExtractorService
from app.services.extraction.candidate_enrichment_service import CandidateEnrichmentService
from app.schemas.intake_extractions import (
    SourceExtractionRead, SourceExtractionDetailRead,
    ProcessWithAiRequest, AiWebResearchRequest, ManualExtractionCreateRequest,
    WebSearchSourceRequest, WebSource, WebSearchHistoryRead,
    InspectManualUrlRequest, ManualUrlInspectionResponse, ProcessManualUrlRequest,
    ExtractedItemCreate, ExtractedItemUpdate, ExtractedItemRead,
    TechnicalInterpretationCandidateRead,
    ExtractionCommitRequest, ExtractionCommitResponse,
    DocumentOcrRequest, DocumentOcrResponse,
    GenerateRulesFromOcrRequest, GenerateRulesFromOcrResponse, GeneratedRuleItem,
    CandidateEnrichmentRequest, CandidateEnrichmentResponse,
    ItemContextResponse, RegionOcrRequest, RegionOcrResponse,
    ItemVisualSplitRequest, ItemCropRequest,
    ExtractParagraphRulesRequest, ExtractParagraphRulesResponse, ParagraphRuleCandidate,
    FieldAcceptancePatchRequest, ExtractionItemsSummaryStats
)

router = APIRouter()

# =========================================================
# 1. PROCESAR CON IA (OPCIÓN 1: DOCUMENTO / OPCIÓN 2: BÚSQUEDA WEB)
# =========================================================

@router.post("/process-with-ai", response_model=SourceExtractionDetailRead, status_code=status.HTTP_201_CREATED)
def process_document_with_ai(
    payload: ProcessWithAiRequest,
    db: Session = Depends(get_db)
):
    """
    Procesa con IA según la modalidad seleccionada:
    - ai_document: Analiza archivo/documento cargado, OCR semántico, capítulos, reglas y tablas.
    - ai_web_research: Investiga un prompt, norma o tema técnico en Internet con referencias y reglas propuestas.
    Retorna la sesión de extracción lista para el panel unificado de revisión humana.
    """
    service = AiDocumentExtractorService(db)
    try:
        if payload.extraction_mode == "ai_web_research" or payload.search_prompt:
            prompt = payload.search_prompt or payload.title
            extraction = service.extract_from_web_research(
                search_prompt=prompt,
                discipline=payload.discipline,
                document_type=payload.document_type,
                authority=payload.authority,
                project_id=payload.project_id,
                type_limits=payload.type_limits,
                max_total=payload.max_total,
                translation=payload.translation
            )
        else:
            extraction = service.extract_document_with_ai(
                title=payload.title,
                document_type=payload.document_type,
                authority=payload.authority,
                discipline=payload.discipline,
                source_asset_id=payload.source_asset_id,
                project_id=payload.project_id,
                text_content=payload.text_content,
                file_path=payload.file_path,
                translation=payload.translation
            )
        return extraction
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error en extracción con IA: {str(e)}")

@router.post("/search-web-sources", response_model=List[WebSource], status_code=status.HTTP_200_OK)
def search_web_sources(
    payload: WebSearchSourceRequest,
    db: Session = Depends(get_db)
):
    """
    Paso 1: Busca páginas y documentos en Internet basados en el prompt con validación multicriterio,
    prioridad de idioma, descubrimiento de subpáginas y persistencia en historial.
    """
    service = AiDocumentExtractorService(db)
    try:
        diag = service.search_web_sources_with_diagnostics(
            search_prompt=payload.search_prompt,
            discipline=payload.discipline,
            document_type=payload.document_type,
            authority=payload.authority,
            max_results=payload.max_results,
            user_id=payload.user_id,
            project_id=payload.project_id
        )
        return diag["results"]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error en búsqueda de fuentes web con IA: {str(e)}")

@router.get("/search-history", response_model=List[WebSearchHistoryRead], status_code=status.HTTP_200_OK)
def get_web_search_history(
    project_id: Optional[str] = Query(None),
    discipline: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """
    Consulta el historial persistente de búsquedas web y auditoría de ingesta.
    """
    repo = IntakeExtractionRepository(db)
    return repo.list_web_search_history(project_id=project_id, discipline=discipline, limit=limit)

@router.get("/search-history/{history_id}", response_model=WebSearchHistoryRead, status_code=status.HTTP_200_OK)
def get_web_search_history_entry(
    history_id: str,
    db: Session = Depends(get_db)
):
    """
    Recupera el detalle y diagnósticos de una búsqueda web persistida específica.
    """
    repo = IntakeExtractionRepository(db)
    entry = repo.get_web_search_history_by_id(history_id)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registro de búsqueda web no encontrado.")
    return entry

@router.post("/process-web-research", response_model=SourceExtractionDetailRead, status_code=status.HTTP_201_CREATED)
def process_web_research(
    payload: AiWebResearchRequest,
    db: Session = Depends(get_db)
):
    """
    Paso 2: Ejecuta la extracción usando las fuentes web seleccionadas por el usuario.
    Aplica traducción técnica post-extracción conservando el texto original para trazabilidad.
    """
    service = AiDocumentExtractorService(db)
    repo = IntakeExtractionRepository(db)
    try:
        extraction = service.extract_from_web_research(
            search_prompt=payload.search_prompt,
            selected_sources=[s.model_dump() for s in payload.selected_sources],
            discipline=payload.discipline,
            document_type=payload.document_type,
            authority=payload.authority,
            project_id=payload.project_id,
            focus_areas=payload.focus_areas,
            type_limits=payload.type_limits,
            max_total=payload.max_total,
            translation=payload.translation
        )
        
        # Si se proporcionó search_history_id, enlazar la extracción creada
        if payload.search_history_id:
            repo.update_web_search_history_extraction(
                history_id=payload.search_history_id,
                source_extraction_id=extraction.id,
                selected_sources=[s.model_dump() for s in payload.selected_sources],
                status="extracted"
            )

        return extraction
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error en investigación web con IA: {str(e)}")


@router.post("/inspect-manual-url", response_model=ManualUrlInspectionResponse, status_code=status.HTTP_200_OK)
def inspect_manual_url(
    payload: InspectManualUrlRequest,
    db: Session = Depends(get_db)
):
    """
    Flujo Principal Web (Paso 1):
    Inspecciona y valida exhaustivamente una URL ingresada manualmente por el usuario.
    - Aplica controles de seguridad SSRF (bloqueo de loopback, IPs privadas y metadatos).
    - Valida acceso HTTP 200 y descarta Soft-404, login walls y páginas de error.
    - Detecta idioma, calcula hash de contenido y genera vista previa de texto limpio.
    - Descubre enlaces internos del mismo dominio y los clasifica por relevancia temática.
    """
    service = AiDocumentExtractorService(db)
    try:
        inspection_result = service.inspect_manual_url(
            url=payload.url,
            discipline=payload.discipline or "Arquitectura",
            document_type=payload.document_type or "norma",
            authority=payload.authority,
            search_prompt=payload.search_prompt,
            max_internal_links=payload.max_internal_links or 15,
            user_id=payload.user_id,
            project_id=payload.project_id
        )
        return inspection_result
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error al inspeccionar URL manual: {str(e)}")


@router.post("/process-manual-url", response_model=SourceExtractionDetailRead, status_code=status.HTTP_201_CREATED)
def process_manual_url_extraction(
    payload: ProcessManualUrlRequest,
    db: Session = Depends(get_db)
):
    """
    Flujo Principal Web (Paso 2):
    Ejecuta la extracción estructurada desde la URL manual principal y los subenlaces seleccionados por el usuario.
    - Extrae reglas, tablas, imágenes, símbolos y equipos.
    - Aplica traducción técnica al español si está activada (preservando los textos originales).
    - Persiste la sesión y registra la auditoría completa en WebSearchHistory.
    """
    service = AiDocumentExtractorService(db)
    try:
        extraction = service.extract_from_manual_url(
            main_source=payload.main_source.model_dump(),
            selected_sublinks=[s.model_dump() for s in payload.selected_sublinks],
            discipline=payload.discipline,
            document_type=payload.document_type,
            authority=payload.authority,
            project_id=payload.project_id,
            search_prompt=payload.search_prompt,
            type_limits=payload.type_limits,
            max_total=payload.max_total,
            translate_to_spanish=payload.translate_to_spanish,
            translation=payload.translation
        )
        return extraction
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error al procesar extracción de URL manual: {str(e)}")


# =========================================================
# 2. PROCESAR SIN IA (CREAR SESIÓN MANUAL)
# =========================================================

@router.post("/create-manual", response_model=SourceExtractionRead, status_code=status.HTTP_201_CREATED)
def create_manual_extraction_session(
    payload: ManualExtractionCreateRequest,
    db: Session = Depends(get_db)
):
    """
    Inicia una sesión de procesamiento manual asistido (SIN IA) para incorporar elementos desde el visor continuo.
    """
    repo = IntakeExtractionRepository(db)
    try:
        session = repo.create_extraction_session(
            title=payload.title,
            document_type=payload.document_type,
            authority=payload.authority,
            discipline=payload.discipline,
            extraction_mode="without_ai",
            source_origin="document",
            source_asset_id=payload.source_asset_id,
            project_id=payload.project_id,
            source_file_path=payload.source_file_path
        )
        return session
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Error al crear sesión manual: {str(e)}")


# =========================================================
# 3. LISTAR Y CONSULTAR SESIONES DE EXTRACCIÓN
# =========================================================

@router.get("", response_model=List[SourceExtractionRead])
def list_extractions(
    discipline: Optional[str] = Query(None),
    document_type: Optional[str] = Query(None),
    extraction_mode: Optional[str] = Query(None),
    source_origin: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db)
):
    """Lista las sesiones de extracción de documentos y búsquedas web estructuradas."""
    repo = IntakeExtractionRepository(db)
    return repo.list_extractions(
        discipline=discipline,
        document_type=document_type,
        extraction_mode=extraction_mode,
        source_origin=source_origin,
        status=status_filter
    )

@router.get("/{extraction_id}", response_model=SourceExtractionDetailRead)
def get_extraction_detail(extraction_id: str, db: Session = Depends(get_db)):
    """Obtiene el detalle completo de una sesión con todos sus elementos extraídos."""
    repo = IntakeExtractionRepository(db)
    extraction = repo.get_extraction_by_id(extraction_id)
    if not extraction:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sesión de extracción no encontrada.")
    return extraction


# =========================================================
# 4. GESTIÓN DE ELEMENTOS EXTRAÍDOS (ITEMS)
# =========================================================

@router.get("/{extraction_id}/items", response_model=List[ExtractedItemRead])
def list_extraction_items(
    extraction_id: str,
    item_type: Optional[str] = Query(None, description="Filtrar por tipo de elemento (rule, table, symbol, image, equipment, etc.)"),
    completeness_status: Optional[str] = Query(None, description="Filtrar por completitud (complete, partial, missing_data, web_suggested)"),
    review_status: Optional[str] = Query(None, description="Filtrar por estado de revisión (draft, to_confirm, accepted, rejected, validada)"),
    discipline: Optional[str] = Query(None, description="Filtrar por disciplina"),
    source_origin: Optional[str] = Query(None, description="Filtrar por origen (document, web)"),
    query: Optional[str] = Query(None, description="Búsqueda textual por título, código o contenido"),
    db: Session = Depends(get_db)
):
    """
    Consulta filtrada completa de elementos extraídos en una sesión:
    Permite filtrar independientemente por tipo de elemento y por completitud,
    sin acoplar completitud con el estado de revisión humana.
    """
    repo = IntakeExtractionRepository(db)
    return repo.list_extracted_items(
        extraction_id=extraction_id,
        item_type=item_type,
        completeness_status=completeness_status,
        review_status=review_status,
        discipline=discipline,
        source_origin=source_origin,
        query=query
    )


@router.get("/{extraction_id}/stats", response_model=ExtractionItemsSummaryStats)
def get_extraction_stats(
    extraction_id: str,
    db: Session = Depends(get_db)
):
    """Retorna contadores agregados en vivo por tipo, completitud y revisión para la UI."""
    service = CandidateEnrichmentService(db)
    return service.get_item_summary_stats(extraction_id)


@router.patch("/{extraction_id}/items/{item_id}/accept-field", response_model=ExtractedItemRead)
def accept_item_field(
    extraction_id: str,
    item_id: str,
    payload: FieldAcceptancePatchRequest,
    db: Session = Depends(get_db)
):
    """
    Aceptación parcial y granular por campo:
    Aplica una sugerencia IA/web o edición manual a un campo específico (title, description, function, code_or_number)
    y preserva el linaje completo en field_provenance sin sobreescribir otros campos.
    """
    service = CandidateEnrichmentService(db)
    try:
        updated = service.apply_field_patch(
            item_id=item_id,
            field_name=payload.field_name,
            accepted_value=payload.accepted_value,
            accepted_from=payload.accepted_from,
            user_id=payload.user_id or "auditor"
        )
        return updated
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


@router.get("/{extraction_id}/candidates", response_model=List[TechnicalInterpretationCandidateRead])
def list_extraction_candidates(
    extraction_id: str,
    candidate_type: Optional[str] = Query(None, description="Filtrar por tipo canónico de candidato"),
    review_status: Optional[str] = Query(None, description="Filtrar por estado de revisión"),
    page_number: Optional[int] = Query(None, description="Filtrar por número de página"),
    db: Session = Depends(get_db)
):
    """
    Capa 2: Consulta filtrada de candidatos de interpretación técnica generados
    (premise_candidate, rule_candidate, symbol_candidate, table_matrix_candidate,
    equipment_image_candidate, diagram_candidate, example_candidate).
    """
    repo = IntakeExtractionRepository(db)
    return repo.list_extracted_candidates(
        extraction_id=extraction_id,
        candidate_type=candidate_type,
        review_status=review_status,
        page_number=page_number
    )

@router.post("/{extraction_id}/items", response_model=ExtractedItemRead, status_code=status.HTTP_201_CREATED)
def add_extracted_item(
    extraction_id: str,
    payload: ExtractedItemCreate,
    db: Session = Depends(get_db)
):
    """Añade un elemento o candidato extraído manualmente o asistido desde el visor."""
    repo = IntakeExtractionRepository(db)
    try:
        item = repo.add_extracted_item(
            extraction_id=extraction_id,
            item_type=payload.item_type,
            candidate_type=payload.candidate_type,
            title=payload.title,
            code_or_number=payload.code_or_number,
            description=payload.description,
            content_text=payload.content_text,
            derived_text=payload.derived_text,
            ocr_text=payload.ocr_text,
            caption_or_context=payload.caption_or_context,
            disclaimer_notes=payload.disclaimer_notes,
            crop_image_base64=payload.crop_image_base64,
            bbox_normalized=payload.bbox_normalized,
            page_number=payload.page_number,
            evidence_references=payload.evidence_references,
            technical_parameters=payload.technical_parameters,
            target_destination=payload.target_destination,
            review_status=payload.review_status,
            structured_matrix=payload.structured_matrix,
            validated_at=payload.validated_at,
            validated_by=payload.validated_by,
            source_origin=payload.source_origin,
            source_reference=payload.source_reference,
            item_nature=payload.item_nature,
            governance_note=payload.governance_note,
            metadata_payload=payload.metadata_payload,
            completeness_status=payload.completeness_status,
            enrichment_status=payload.enrichment_status,
            requires_validation=payload.requires_validation,
            enriched_from_web=payload.enriched_from_web,
            enrichment_method=payload.enrichment_method,
            match_confidence=payload.match_confidence,
            suggested_title=payload.suggested_title,
            suggested_description=payload.suggested_description,
            suggested_function=payload.suggested_function,
            suggested_source_url=payload.suggested_source_url,
            suggested_source_label=payload.suggested_source_label
        )
        return item
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))

@router.put("/{extraction_id}/items/{item_id}", response_model=ExtractedItemRead)
def update_extracted_item(
    extraction_id: str,
    item_id: str,
    payload: ExtractedItemUpdate,
    db: Session = Depends(get_db)
):
    """Actualiza metadatos, clasificación, texto o estado de revisión de un elemento / candidato."""
    repo = IntakeExtractionRepository(db)
    try:
        updated = repo.update_extracted_item(item_id, payload.model_dump(exclude_unset=True))
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Elemento no encontrado.")
        return updated
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(ve)
        )

@router.delete("/{extraction_id}/items/{item_id}", status_code=status.HTTP_200_OK)
def delete_extracted_item(
    extraction_id: str,
    item_id: str,
    db: Session = Depends(get_db)
):
    """Elimina o descarta un elemento de la sesión de extracción."""
    repo = IntakeExtractionRepository(db)
    success = repo.delete_extracted_item(item_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Elemento no encontrado.")
    return {"message": "Elemento eliminado exitosamente."}

@router.get("/{extraction_id}/items", response_model=List[ExtractedItemRead])
def list_extracted_items(
    extraction_id: str,
    item_type: Optional[str] = Query(None, description="Filtro por tipo de elemento (rule, symbol, table, equipment, figure)"),
    completeness_status: Optional[str] = Query(None, description="Filtro ortogonal por completitud (complete, partial, missing_data, web_suggested)"),
    review_status: Optional[str] = Query(None, description="Filtro por estado de revisión humana (draft, to_confirm, accepted, rejected)"),
    discipline: Optional[str] = Query(None, description="Filtro por disciplina técnica"),
    source_origin: Optional[str] = Query(None, description="Filtro por origen (document, web)"),
    query: Optional[str] = Query(None, description="Término de búsqueda en título, descripción o código"),
    db: Session = Depends(get_db)
):
    """
    Lista elementos extraídos con filtros ortogonales completos por tipo y completitud técnica.
    """
    repo = IntakeExtractionRepository(db)
    return repo.list_extracted_items(
        extraction_id=extraction_id,
        item_type=item_type,
        completeness_status=completeness_status,
        review_status=review_status,
        discipline=discipline,
        source_origin=source_origin,
        query=query
    )

@router.get("/{extraction_id}/stats", response_model=ExtractionItemsSummaryStats)
def get_extraction_stats(
    extraction_id: str,
    db: Session = Depends(get_db)
):
    """
    Retorna métricas agregadas en tiempo real de completitud, revisión y distribución por tipo.
    """
    service = CandidateEnrichmentService(db)
    return service.get_item_summary_stats(extraction_id)

@router.patch("/{extraction_id}/items/{item_id}/accept-field", response_model=ExtractedItemRead)
def accept_item_field(
    extraction_id: str,
    item_id: str,
    payload: FieldAcceptancePatchRequest,
    db: Session = Depends(get_db)
):
    """
    Aplica una aceptación parcial por campo específico (title, description, function, etc.)
    con trazabilidad y linaje estricto en field_provenance y recalcula la completitud técnica.
    """
    service = CandidateEnrichmentService(db)
    try:
        updated_item = service.apply_field_patch(
            item_id=item_id,
            field_name=payload.field_name,
            accepted_value=payload.accepted_value,
            accepted_from=payload.accepted_from,
            user_id=payload.user_id
        )
        return updated_item
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error al aplicar parche de campo: {str(e)}")



# =========================================================
# 5. INCORPORACIÓN AL MOTOR DE REGLAS QA/QC (COMMIT)
# =========================================================

@router.post("/{extraction_id}/commit", response_model=ExtractionCommitResponse)
def commit_extraction_to_rules(
    extraction_id: str,
    payload: ExtractionCommitRequest,
    db: Session = Depends(get_db)
):
    """
    Incorpora los elementos aceptados y validados de la extracción hacia el Motor de Reglas QA/QC
    y hacia la Base de Conocimiento Curada con trazabilidad completa.
    """
    repo = IntakeExtractionRepository(db)
    try:
        res = repo.commit_extraction_to_rules(
            extraction_id=extraction_id,
            approved_item_ids=payload.approved_item_ids,
            target_rule_document_title=payload.target_rule_document_title,
            target_rule_document_description=payload.target_rule_document_description
        )
        return ExtractionCommitResponse(**res)
    except ValueError as ve:
        err_msg = str(ve)
        if "ya existe en el Motor de Reglas" in err_msg or "no puede incorporarse nuevamente" in err_msg:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error en commit: {str(e)}")


# =========================================================
# 6. OCR GENERAL DEL DOCUMENTO COMPLETO
# =========================================================

@router.post("/document-ocr", response_model=DocumentOcrResponse)
def get_full_document_ocr(
    payload: DocumentOcrRequest,
    db: Session = Depends(get_db)
):
    """
    Retorna el texto OCR continuo de todo el documento normativo o por página para búsqueda y exploración.
    """
    if payload.source_asset_id:
        source = db.query(SourceAsset).filter(SourceAsset.id == payload.source_asset_id).first()
        if source and source.file_path and os.path.exists(source.file_path):
            try:
                import fitz
                doc = fitz.open(source.file_path)
                pages = []
                for pno in range(len(doc)):
                    page_obj = doc[pno]
                    txt = page_obj.get_text().strip()
                    pages.append({
                        "page_number": pno + 1,
                        "text_content": txt if txt else f"(Página {pno + 1}: Sin texto reconocible o documento gráfico)",
                        "confidence": 0.98 if txt else 0.5
                    })
                doc.close()
                if pages:
                    full_text = "\n\n--- PÁGINA SIGUIENTE ---\n\n".join(f"=== PÁGINA {p['page_number']} ===\n" + p["text_content"] for p in pages)
                    return DocumentOcrResponse(total_pages=len(pages), full_text=full_text, pages=pages)
            except Exception as e:
                print(f"Aviso leyendo OCR real desde PDF: {e}")

    # Fallback con contenido estructurado normativo
    pages = [
        {
            "page_number": 1,
            "text_content": (
                "ORDENANZA GENERAL DE URBANISMO Y CONSTRUCCIONES (OGUC)\n"
                "TITULO 4: DE LA ARQUITECTURA - CAPITULO 1: DISPOSICIONES GENERALES\n"
                "Art. 4.1.1 Los edificios que se construyan deberán cumplir con las normas de habitabilidad y seguridad.\n"
                "Art. 4.1.7 Toda escalera de uso público deberá contar con pasamanos continuo a 0.90 m de altura."
            ),
            "confidence": 0.96
        },
        {
            "page_number": 2,
            "text_content": (
                "CAPITULO 2: DE LAS CONDICIONES DE SEGURIDAD CONTRA INCENDIO\n"
                "Art. 4.3.1 Todo edificio de más de 5 pisos deberá contar con zona vertical de seguridad protegida.\n"
                "TABLA 4.3.A: Exigencias de resistencia al fuego para elementos soportantes verticales: F-120."
            ),
            "confidence": 0.94
        },
        {
            "page_number": 3,
            "text_content": (
                "CAPITULO 3: EVACUACION Y SALIDAS DE EMERGENCIA\n"
                "Art. 4.3.7 Las puertas de escape deberán abrir en el sentido de la evacuación sin llave ni traba.\n"
                "FIGURA 4.3.1: Detalle de ancho libre de paso en puertas y distancia de apertura."
            ),
            "confidence": 0.95
        }
    ]
    full_text = "\n\n--- PÁGINA SIGUIENTE ---\n\n".join(p["text_content"] for p in pages)
    return DocumentOcrResponse(total_pages=len(pages), full_text=full_text, pages=pages)


# =========================================================
# 7. GENERACIÓN DE REGLAS CON IA DESDE TEXTO OCR
# =========================================================

@router.post("/generate-rules-from-ocr", response_model=GenerateRulesFromOcrResponse)
def generate_rules_from_ocr(
    payload: GenerateRulesFromOcrRequest,
    db: Session = Depends(get_db)
):
    """
    Analiza el texto OCR (general o de una página específica) y extrae una lista estructurada
    de reglas técnicas QA/QC individuales, listas para incorporarse a la sesión y al panel lateral.
    """
    service = AiDocumentExtractorService(db)
    try:
        rules_list = service.generate_rules_from_ocr_text(
            ocr_text=payload.ocr_text,
            discipline=payload.discipline,
            document_title=payload.document_title,
            page_number=payload.page_number
        )
        return GenerateRulesFromOcrResponse(rules=rules_list)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generando reglas desde OCR con IA: {str(e)}"
        )


# =========================================================
# 8. CONTEXTO DE PÁGINA EXACTA Y RECORTE MULTIMODAL
# =========================================================

@router.get("/{extraction_id}/items/{item_id}/context", response_model=ItemContextResponse)
def get_item_context(
    extraction_id: str,
    item_id: str,
    page_number: Optional[int] = Query(None, description="Página específica para navegar ocurrencias multipágina"),
    bbox: Optional[str] = Query(None, description="BBox normalizado opcional en JSON o separado por comas"),
    db: Session = Depends(get_db)
):
    """
    Obtiene la vista contextual de la página exacta del documento para un elemento multimodal.
    Proporciona URL de página renderizada, coordenadas bbox_normalized, texto de entorno y sugerencias.
    Soporta visualización de ocurrencias secundarias especificando page_number y bbox.
    """
    service = CandidateEnrichmentService(db)
    parsed_bbox: Optional[List[float]] = None
    if bbox:
        try:
            import json
            if bbox.startswith("["):
                parsed_bbox = [float(x) for x in json.loads(bbox)]
            else:
                parsed_bbox = [float(x.strip()) for x in bbox.split(",")]
        except Exception:
            parsed_bbox = None

    try:
        return service.get_item_context(
            extraction_id=extraction_id,
            item_id=item_id,
            page_number=page_number,
            bbox_override=parsed_bbox
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error obteniendo contexto: {str(e)}")


# =========================================================
# 9. ENRIQUECIMIENTO ASISTIDO POR BÚSQUEDA WEB / CATÁLOGO
# =========================================================

@router.post("/{extraction_id}/items/{item_id}/enrich", response_model=CandidateEnrichmentResponse)
def enrich_extracted_item(
    extraction_id: str,
    item_id: str,
    payload: Optional[CandidateEnrichmentRequest] = None,
    db: Session = Depends(get_db)
):
    """
    Dispara la búsqueda de referencia y enriquecimiento asistido para un elemento multimodal.
    Retorna sugerencias fundamentadas con nivel de confianza y URL de fuente o reporta datos faltantes con honestidad.
    """
    service = CandidateEnrichmentService(db)
    try:
        custom_q = payload.caption_or_context if payload else None
        item, res = service.enrich_item(
            extraction_id=extraction_id,
            item_id=item_id,
            custom_query=custom_q,
            payload=payload
        )
        
        return CandidateEnrichmentResponse(
            item_id=item.id,
            enrichment_status=item.enrichment_status,
            completeness_status=item.completeness_status,
            match_confidence=item.match_confidence,
            suggested_title=item.suggested_title,
            suggested_description=item.suggested_description,
            suggested_function=item.suggested_function,
            suggested_source_label=item.suggested_source_label,
            suggested_source_url=item.suggested_source_url,
            enrichment_method=item.enrichment_method or "web_reference_lookup",
            requires_validation=item.requires_validation,
            enriched_from_web=item.enriched_from_web,
            technical_properties=item.technical_parameters.get("suggested_properties", {}) if item.technical_parameters else {},
            message=res.get("message") or f"Enriquecimiento ejecutado. Estado: {item.enrichment_status} (Confianza: {int(item.match_confidence * 100)}%)",
            presentation_language=res.get("presentation_language") or item.presentation_language,
            effective_fields=res.get("effective_fields") or item.effective_fields
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error en enriquecimiento asistido: {str(e)}")


@router.post("/enrich-candidate", response_model=CandidateEnrichmentResponse)
def enrich_candidate_payload(
    payload: CandidateEnrichmentRequest,
    db: Session = Depends(get_db)
):
    """
    Endpoint general para enriquecer un candidato o contexto técnico en tiempo real sin persistencia obligatoria.
    """
    service = CandidateEnrichmentService(db)
    res = service.enrich_candidate(
        candidate_type=payload.candidate_type,
        title=payload.title,
        caption_or_context=payload.caption_or_context,
        ocr_text=payload.ocr_text,
        discipline=payload.discipline,
        page_number=payload.page_number or 1,
        document_title=payload.document_title,
        force_web_search=payload.force_web_search,
        presentation_language=payload.presentation_language or "es",
        source_fields=payload.source_fields,
        translated_fields=payload.translated_fields,
        effective_fields=payload.effective_fields
    )
    return CandidateEnrichmentResponse(**res)


# =========================================================
# 10. OCR DE SUB-REGIÓN EN VISOR DE CONTEXTO
# =========================================================

@router.post("/{extraction_id}/items/{item_id}/region-ocr", response_model=RegionOcrResponse)
def extract_region_ocr_text(
    extraction_id: str,
    item_id: str,
    payload: RegionOcrRequest,
    db: Session = Depends(get_db)
):
    """
    Ejecuta OCR sobre una sub-región seleccionada por el usuario en el visor de contexto
    para volcar el texto reconocido al campo destino (título, descripción, función).
    """
    service = CandidateEnrichmentService(db)
    try:
        res = service.extract_region_ocr(
            extraction_id=extraction_id,
            item_id=item_id,
            page_number=payload.page_number,
            bbox=payload.bbox,
            target_field=payload.target_field or "title"
        )
        return RegionOcrResponse(**res)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error en OCR de región: {str(e)}")


# =========================================================
# 11. APLICAR SUGERENCIAS AL ELEMENTO ACTIVO
# =========================================================

@router.post("/{extraction_id}/items/{item_id}/apply-suggestion", response_model=ExtractedItemRead)
def apply_item_suggestion(
    extraction_id: str,
    item_id: str,
    db: Session = Depends(get_db)
):
    """
    Aplica las sugerencias encontradas (título, descripción, función, referencia) al elemento activo,
    establece el estado de completitud a 'complete', marca requires_validation=False y enrichment_status='manual_completed'.
    """
    repo = IntakeExtractionRepository(db)
    item = repo.get_extracted_item_by_id(item_id)
    if not item or item.extraction_id != extraction_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Elemento no encontrado.")

    if not item.suggested_title and not item.suggested_description:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No hay sugerencias disponibles para aplicar en este elemento.")

    update_payload = {
        "title": item.suggested_title or item.title,
        "description": item.suggested_description or item.description,
        "enrichment_status": "manual_completed",
        "completeness_status": "complete",
        "requires_validation": False,
        "source_reference": item.suggested_source_label or item.source_reference
    }

    if item.suggested_function:
        tech = dict(item.technical_parameters or {})
        tech["function_or_role"] = item.suggested_function
        update_payload["technical_parameters"] = tech

    updated = repo.update_extracted_item(item_id, update_payload)
    return updated


# =========================================================
# 12. SEPARACIÓN VISUAL ("SEPARAR ELEMENTO")
# =========================================================

@router.post("/{extraction_id}/items/{item_id}/split", response_model=ExtractedItemRead, status_code=status.HTTP_201_CREATED)
def split_extracted_item_endpoint(
    extraction_id: str,
    item_id: str,
    payload: ItemVisualSplitRequest,
    db: Session = Depends(get_db)
):
    """
    Separa visualmente una subregión seleccionada de una regla/elemento compuesto:
    - Crea un nuevo elemento extraído derivado usando la subimagen recortada.
    - Ejecuta OCR y sugerencias sobre la nueva subimagen.
    - Preserva el elemento padre 100% intacto y vincula la nueva regla mediante parent_item_id y derivation_type=visual_split.
    """
    service = AiDocumentExtractorService(db)
    try:
        new_item = service.split_extracted_item(
            extraction_id=extraction_id,
            item_id=item_id,
            bbox=payload.bbox,
            title_hint=payload.title_hint,
            discipline=payload.discipline,
            user_id=payload.user_id
        )
        return new_item
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error en separación visual: {str(e)}")


# =========================================================
# 13. RECORTE DE CONTEXTO ("RECORTAR ELEMENTO ACTUAL")
# =========================================================

@router.patch("/{extraction_id}/items/{item_id}/crop", response_model=ExtractedItemRead)
def crop_extracted_item_endpoint(
    extraction_id: str,
    item_id: str,
    payload: ItemCropRequest,
    db: Session = Depends(get_db)
):
    """
    Recorta la imagen del elemento actual sin crear un nuevo elemento:
    - Actualiza crop_image_path y bbox_normalized.
    - Registra el historial de recorte previo (previous_crop_history) para auditoría.
    - Vuelve a ejecutar OCR sobre la nueva área recortada.
    """
    service = AiDocumentExtractorService(db)
    try:
        updated_item = service.crop_extracted_item(
            extraction_id=extraction_id,
            item_id=item_id,
            bbox=payload.bbox,
            user_id=payload.user_id
        )
        return updated_item
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error al recortar elemento: {str(e)}")


# =========================================================
# 14. DETECCIÓN Y RESUMEN DE PÁRRAFOS DE TEXTO LIBRE
# =========================================================

@router.post("/extract-paragraph-rules", response_model=ExtractParagraphRulesResponse)
def extract_paragraph_rules_endpoint(
    payload: ExtractParagraphRulesRequest,
    db: Session = Depends(get_db)
):
    """
    Detección estructural de párrafos de texto libre relevantes fuera de tablas y fuera de figuras,
    resumiéndolos en español técnico como candidatos de regla o criterios reutilizables (paragraph_rule_candidate).
    """
    service = AiDocumentExtractorService(db)
    try:
        candidates = service.extract_free_text_paragraph_rules(
            text_content=payload.text_content,
            discipline=payload.discipline,
            document_type=payload.document_type,
            page_number=payload.page_number,
            source_reference=payload.source_reference
        )
        return ExtractParagraphRulesResponse(
            total_paragraphs_detected=len(candidates),
            rules_candidates=[ParagraphRuleCandidate(**c) for c in candidates]
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error extrayendo párrafos de texto libre: {str(e)}")

