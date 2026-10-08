import os
import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.repositories.intake_repository import IntakeRepository
from app.schemas.intake import (
    SourceAssetCreate, SourceAssetRead, SourceAssetApprovalRequest,
    SourceAssetIngestResponse, SourceDependenciesResponse, SourceDeleteResponse,
    ResearchQueryRead, ResearchQueryDetailRead,
    SourceDocumentPagesResponse, PageCropRequest, PageCropResponse,
    RuleSummarizeRequest, RuleSummarizeResponse,
    BatchSourceUploadResponse, BatchSourceFileResultItem
)
from app.services.intake.service import IntakeService

logger = logging.getLogger("plan_review")

router = APIRouter()


@router.post("/sources", response_model=SourceAssetRead, status_code=status.HTTP_201_CREATED)
def register_source_json(
    payload: SourceAssetCreate,
    db: Session = Depends(get_db)
):
    """Registra una nueva fuente en el sistema mediante payload estructurado JSON."""
    service = IntakeService(db)
    try:
        source = service.register_source(
            source_type=payload.source_type,
            title=payload.title,
            organization_id=payload.organization_id,
            project_id=payload.project_id,
            source_origin=payload.source_origin,
            document_type=payload.document_type,
            discipline=payload.discipline,
            description=payload.description,
            source_url=payload.source_url,
            filename=payload.original_filename,
            version=payload.version,
            owner=payload.owner,
            metadata_payload=payload.metadata_payload
        )
        return source
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))

@router.post("/sources/upload", response_model=SourceAssetRead, status_code=status.HTTP_201_CREATED)
async def register_source_file(
    source_type: str = Form(...),
    title: str = Form(...),
    discipline: str = Form("general"),
    document_type: Optional[str] = Form("blueprint_pdf"),
    description: Optional[str] = Form(None),
    authority: Optional[str] = Form(None),
    project_id: Optional[str] = Form(None),
    version: str = Form("1.0"),
    owner: str = Form("system"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Registra una fuente mediante carga física de archivo local (PDF, DOCX, etc.) en volumen persistente."""
    service = IntakeService(db)
    content = await file.read()
    meta = {}
    if authority:
        meta["authority"] = authority

    try:
        source = service.register_source(
            source_type=source_type,
            title=title,
            project_id=project_id,
            source_origin="local_upload",
            document_type=document_type,
            discipline=discipline,
            description=description,
            file_bytes=content,
            filename=file.filename,
            mime_type=file.content_type,
            version=version,
            owner=owner,
            metadata_payload=meta
        )
        return source
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))


@router.post("/sources/batch-upload", response_model=BatchSourceUploadResponse, status_code=status.HTTP_201_CREATED)
async def register_sources_batch(
    source_type: str = Form(...),
    title_prefix: Optional[str] = Form(None),
    discipline: str = Form("general"),
    document_type: Optional[str] = Form("standard_doc"),
    description: Optional[str] = Form(None),
    authority: Optional[str] = Form(None),
    project_id: Optional[str] = Form(None),
    version: str = Form("1.0"),
    owner: str = Form("system"),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    """
    Carga por lotes de fuentes documentales / entrenamiento para la Base de Conocimiento.
    Permite subir múltiples archivos o una carpeta completa de fuentes normativas / catálogos.
    Un fallo en un archivo individual no aborta el lote.
    """
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se enviaron archivos para la carga de fuentes por lotes."
        )

    service = IntakeService(db)
    sources: List[SourceAssetRead] = []
    results: List[BatchSourceFileResultItem] = []
    successful_count = 0
    duplicated_count = 0
    failed_count = 0

    base_meta = {}
    if authority:
        base_meta["authority"] = authority

    for upload_file in files:
        raw_name = upload_file.filename or "unnamed_source"
        clean_basename = raw_name.replace("\\", "/").split("/")[-1]
        try:
            content = await upload_file.read()
            if not content:
                failed_count += 1
                results.append(BatchSourceFileResultItem(
                    filename=clean_basename,
                    status="failed",
                    error_message="El archivo está vacío."
                ))
                continue

            file_hash = service.calculate_hash(content)
            existing = service.repo.get_by_sha256(file_hash)
            if existing:
                duplicated_count += 1
                sources.append(existing)
                results.append(BatchSourceFileResultItem(
                    filename=clean_basename,
                    status="already_exists",
                    source_id=existing.id,
                    source_title=existing.title,
                    file_size_bytes=len(content),
                    mime_type=existing.mime_type,
                    error_message=None
                ))
                continue

            # Generar título por archivo a partir de title_prefix o del nombre del archivo
            stem = os.path.splitext(clean_basename)[0]
            clean_stem = stem.replace("_", " ").replace("-", " ").strip()
            if title_prefix and title_prefix.strip():
                item_title = f"{title_prefix.strip()} - {clean_stem}"
            else:
                item_title = clean_stem.title() if clean_stem else clean_basename

            file_meta = dict(base_meta)
            if "/" in raw_name or "\\" in raw_name:
                file_meta["relative_path"] = raw_name

            source = service.register_source(
                source_type=source_type,
                title=item_title,
                project_id=project_id,
                source_origin="local_upload",
                document_type=document_type,
                discipline=discipline,
                description=description,
                file_bytes=content,
                filename=clean_basename,
                mime_type=upload_file.content_type or "application/octet-stream",
                version=version,
                owner=owner,
                metadata_payload=file_meta
            )
            successful_count += 1
            sources.append(source)
            results.append(BatchSourceFileResultItem(
                filename=clean_basename,
                status="uploaded",
                source_id=source.id,
                source_title=source.title,
                file_size_bytes=len(content),
                mime_type=source.mime_type,
                error_message=None
            ))
        except Exception as err:
            logger.error(f"Error procesando fuente '{clean_basename}' en batch upload: {err}", exc_info=True)
            failed_count += 1
            results.append(BatchSourceFileResultItem(
                filename=clean_basename,
                status="failed",
                error_message=str(err)
            ))
        finally:
            try:
                await upload_file.close()
            except Exception:
                pass

    return BatchSourceUploadResponse(
        total_files=len(files),
        successful_count=successful_count,
        duplicated_count=duplicated_count,
        failed_count=failed_count,
        sources=sources,
        results=results
    )


@router.get("/disciplines", response_model=List[str])
def list_disciplines(db: Session = Depends(get_db)):
    """Retorna el listado unificado de disciplinas base y personalizadas registradas."""
    repo = IntakeRepository(db)
    return repo.list_distinct_disciplines()

@router.get("/sources", response_model=List[SourceAssetRead])
def list_sources(
    source_type: Optional[str] = Query(None, description="Filtrar por tipo de fuente"),
    discipline: Optional[str] = Query(None, description="Filtrar por disciplina"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filtrar por estado"),
    approval_status: Optional[str] = Query(None, description="Filtrar por estado de aprobación"),
    linked_memory_target: Optional[str] = Query(None, description="Filtrar por memoria destino"),
    db: Session = Depends(get_db)
):
    """Lista las fuentes registradas aplicando filtros de gobierno y memoria destino."""
    repo = IntakeRepository(db)
    return repo.list_sources(
        source_type=source_type,
        discipline=discipline,
        status=status_filter,
        approval_status=approval_status,
        linked_memory_target=linked_memory_target
    )

@router.get("/sources/{source_id}", response_model=SourceAssetRead)
def get_source(source_id: str, db: Session = Depends(get_db)):
    """Consulta los detalles de una fuente registrada."""
    repo = IntakeRepository(db)
    source = repo.get_by_id(source_id)
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fuente no encontrada.")
    return source

@router.get("/sources/{source_id}/dependencies", response_model=SourceDependenciesResponse)
def get_source_dependencies(source_id: str, db: Session = Depends(get_db)):
    """Obtiene las dependencias activas (extracciones, reglas) de una fuente antes de eliminar."""
    service = IntakeService(db)
    return service.get_source_dependencies(source_id)

@router.delete("/sources/{source_id}", response_model=SourceDeleteResponse)
def delete_source(
    source_id: str,
    hard_delete: bool = Query(False, description="Forzar eliminación física de BD y archivo en disco"),
    db: Session = Depends(get_db)
):
    """Elimina o archiva una fuente garantizando consistencia entre UI, BD y archivo físico."""
    service = IntakeService(db)
    try:
        return service.delete_source(source_id=source_id, hard_delete=hard_delete)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error al eliminar fuente: {str(e)}")

@router.post("/sources/{source_id}/approval", response_model=SourceAssetRead)
def approve_source(
    source_id: str,
    payload: SourceAssetApprovalRequest,
    db: Session = Depends(get_db)
):
    """Aprueba o rechaza una fuente para su posterior alimentación a memorias del sistema."""
    service = IntakeService(db)
    try:
        return service.approve_or_reject_source(
            source_id=source_id,
            approved=payload.approved,
            notes=payload.notes,
            reviewer=payload.reviewer
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))

@router.post("/sources/{source_id}/ingest", response_model=SourceAssetIngestResponse)
def ingest_source_to_target(
    source_id: str,
    project_id: Optional[str] = Query(None, description="ID del proyecto si el destino es document_memory"),
    db: Session = Depends(get_db)
):
    """Dispara el direccionamiento e ingesta formal hacia la memoria destino correspondiente."""
    service = IntakeService(db)
    try:
        return service.ingest_source(source_id=source_id, project_id=project_id)
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error en ingestión: {str(e)}")

# =========================================================
# ENDPOINTS DE INVESTIGACIÓN WEB PERSISTENTE (ETAPA 3)
# =========================================================

@router.get("/research/queries", response_model=List[ResearchQueryRead])
def list_research_queries(
    discipline: Optional[str] = Query(None, description="Filtrar por disciplina"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filtrar por estado"),
    db: Session = Depends(get_db)
):
    """Lista el histórico estructurado de investigaciones web guardadas para su reutilización."""
    repo = IntakeRepository(db)
    return repo.list_research_queries(discipline=discipline, status=status_filter)

@router.get("/research/queries/{query_id}", response_model=ResearchQueryDetailRead)
def get_research_query_detail(query_id: str, db: Session = Depends(get_db)):
    """Obtiene el detalle completo de una investigación web, incluyendo citas y reglas derivadas."""
    repo = IntakeRepository(db)
    query = repo.get_research_query_detail(query_id)
    if not query:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investigación web no encontrada.")
    return query


# =========================================================
# ENDPOINTS DE VISOR DOCUMENTAL REAL, RECORTES Y RESUMEN
# =========================================================

@router.get("/sources/{source_id}/pages", response_model=SourceDocumentPagesResponse)
def get_source_document_pages(
    source_id: str,
    db: Session = Depends(get_db)
):
    """
    Retorna las páginas reales renderizadas en alta resolución del documento físico incorporado,
    permitiendo al visor documental comportarse como un lector PDF continuo y real.
    """
    service = IntakeService(db)
    try:
        return service.get_source_pages(source_id)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error obteniendo páginas: {str(e)}")

@router.post("/sources/{source_id}/crop", response_model=PageCropResponse)
def crop_source_document_page(
    source_id: str,
    payload: PageCropRequest,
    db: Session = Depends(get_db)
):
    """
    Recorta con precisión una región seleccionada sobre la página real del documento
    y extrae texto/OCR específico para el botón 'Imagen' o 'Texto'.
    """
    service = IntakeService(db)
    try:
        return service.crop_source_page(
            source_id=source_id,
            page_number=payload.page_number,
            bbox=payload.bbox,
            title=payload.title
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error al recortar región: {str(e)}")

@router.post("/sources/summarize-rule", response_model=RuleSummarizeResponse)
def summarize_technical_rule(
    payload: RuleSummarizeRequest,
    db: Session = Depends(get_db)
):
    """
    Sintetiza y estructura un texto normativo o extracto documental en un enunciado
    claro y conciso de regla técnica QA/QC con parámetros cuantificables.
    """
    service = IntakeService(db)
    try:
        return service.summarize_rule(
            text_content=payload.text_content,
            discipline=payload.discipline or "general",
            title=payload.title,
            item_type=payload.item_type or "rule"
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error al resumir regla: {str(e)}")

@router.get("/sources/{source_id}/file")
def get_source_raw_file(
    source_id: str,
    db: Session = Depends(get_db)
):
    """
    Retorna el archivo binario original (PDF, imagen) directamente desde su ruta persistida en disco
    con Content-Disposition: inline para visualización embebida sin forzar descargas ni cuadros de guardar.
    """
    repo = IntakeRepository(db)
    source = repo.get_by_id(source_id)
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fuente no encontrada.")
    if not source.file_path or not os.path.exists(source.file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archivo físico no disponible en almacenamiento persistente.")
    
    media_type = source.mime_type or "application/pdf"
    filename = source.original_filename or f"{source.title}.pdf"
    
    return FileResponse(
        path=source.file_path,
        media_type=media_type,
        content_disposition_type="inline",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Accept-Ranges": "bytes",
            "Cache-Control": "public, max-age=3600",
        }
    )
