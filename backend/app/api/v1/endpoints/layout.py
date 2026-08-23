from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.repositories.document_repository import DocumentRepository
from app.schemas.document import (
    SheetRegionRead, TitleBlockExtractionRead,
    LayoutProcessRequest, TitleBlockMatchRequest
)
from app.schemas.operations import AsyncJobAcceptedResponse
from app.services.layout.service import LayoutService
from app.services.operations.service import OperationsService

router = APIRouter()

@router.post("/sheets/{sheet_id}", response_model=Dict[str, Any])
def process_sheet_layout(
    sheet_id: str,
    request: Optional[LayoutProcessRequest] = None,
    db: Session = Depends(get_db)
):
    """Ejecuta segmentación de layout macro-regional y extracción de viñeta síncrona sobre una lámina."""
    service = LayoutService(db)
    force = request.force_reprocess if request else False

    try:
        return service.process_sheet(sheet_id=sheet_id, force_reprocess=force)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error en layout de lámina: {str(e)}")

@router.post("/sheets/{sheet_id}/async", response_model=AsyncJobAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
def process_sheet_layout_async(
    sheet_id: str,
    request: Optional[LayoutProcessRequest] = None,
    db: Session = Depends(get_db)
):
    """Encola layout y extracción de viñeta asíncrono para una lámina (HTTP 202 Accepted)."""
    ops_svc = OperationsService(db)
    repo = DocumentRepository(db)
    sheet = repo.get_sheet_by_id(sheet_id)
    if not sheet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lámina '{sheet_id}' no encontrada.")

    job = ops_svc.submit_job(
        job_type="sheet_layout",
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
        message="Layout de lámina encolado para procesamiento asíncrono.",
        target_type="sheet",
        target_id=sheet_id
    )

@router.post("/documents/{document_id}", response_model=List[Dict[str, Any]])
def process_document_layout(
    document_id: str,
    request: Optional[LayoutProcessRequest] = None,
    db: Session = Depends(get_db)
):
    """Ejecuta segmentación de layout y extracción de viñetas síncrono sobre todas las hojas de un documento."""
    service = LayoutService(db)
    force = request.force_reprocess if request else False

    try:
        return service.process_document(document_id=document_id, force_reprocess=force)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error en layout de documento: {str(e)}")

@router.post("/documents/{document_id}/async", response_model=AsyncJobAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
def process_document_layout_async(
    document_id: str,
    request: Optional[LayoutProcessRequest] = None,
    db: Session = Depends(get_db)
):
    """Encola layout asíncrono para todas las hojas de un documento (HTTP 202 Accepted)."""
    ops_svc = OperationsService(db)
    repo = DocumentRepository(db)
    doc = repo.get_by_id(document_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Documento '{document_id}' no encontrado.")

    job = ops_svc.submit_job(
        job_type="document_layout",
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
        message="Layout de documento encolado para procesamiento asíncrono.",
        target_type="document",
        target_id=document_id
    )

@router.get("/sheets/{sheet_id}/regions", response_model=List[SheetRegionRead])
def list_sheet_regions(sheet_id: str, db: Session = Depends(get_db)):
    """Consulta las macro-regiones segmentadas para una lámina."""
    repo = DocumentRepository(db)
    sheet = repo.get_sheet_by_id(sheet_id)
    if not sheet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lámina '{sheet_id}' no encontrada.")
    return repo.list_regions_by_sheet(sheet_id)

@router.post("/sheets/{sheet_id}/title-block", response_model=TitleBlockExtractionRead)
def match_title_block(
    sheet_id: str,
    request: Optional[TitleBlockMatchRequest] = None,
    db: Session = Depends(get_db)
):
    """Ejecuta el matching de viñeta contra template_memory y extrae sus metadatos estructurados."""
    service = LayoutService(db)
    force = request.force_reprocess if request else False
    template_id = request.template_id if request else None

    try:
        return service.match_and_extract_title_block(
            sheet_id=sheet_id,
            force_reprocess=force,
            template_id=template_id
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error en title block matching: {str(e)}")

@router.get("/sheets/{sheet_id}/title-block", response_model=Optional[TitleBlockExtractionRead])
def get_title_block_extraction(sheet_id: str, db: Session = Depends(get_db)):
    """Obtiene los metadatos estructurados extraídos de la viñeta de una lámina."""
    repo = DocumentRepository(db)
    sheet = repo.get_sheet_by_id(sheet_id)
    if not sheet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lámina '{sheet_id}' no encontrada.")
    extraction = repo.get_title_block_extraction(sheet_id)
    if not extraction:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Viñeta no procesada para la lámina '{sheet_id}'.")
    return extraction
