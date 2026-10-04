from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.repositories.document_repository import DocumentRepository
from app.schemas.document import ExtractedTextRead, OcrProcessRequest, OcrResultSummary
from app.schemas.operations import AsyncJobAcceptedResponse
from app.services.ocr.service import OcrService
from app.services.operations.service import OperationsService

router = APIRouter()

@router.get("/engines", response_model=Dict[str, bool])
def get_available_engines(db: Session = Depends(get_db)):
    """Consulta el estado de disponibilidad de cada motor OCR (PaddleOCR, Tesseract, VectorPDF)."""
    service = OcrService(db)
    return service.get_available_engines()

@router.post("/documents/{document_id}", response_model=List[OcrResultSummary])
def process_document_ocr(
    document_id: str,
    request: Optional[OcrProcessRequest] = None,
    db: Session = Depends(get_db)
):
    """Ejecuta OCR síncrono sobre todas las hojas rasterizadas de un documento."""
    service = OcrService(db)
    force = request.force_reprocess if request else False
    engine = request.engine if request else None

    try:
        results = service.process_document_ocr(
            document_id=document_id,
            force_reprocess=force,
            preferred_engine=engine
        )
        return results
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except FileNotFoundError as fe:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(fe))
    except RuntimeError as re:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(re))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error en OCR de documento: {str(e)}")

@router.post("/documents/{document_id}/async", response_model=AsyncJobAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
def process_document_ocr_async(
    document_id: str,
    request: Optional[OcrProcessRequest] = None,
    db: Session = Depends(get_db)
):
    """Encola OCR asíncrono para todas las hojas de un documento (HTTP 202 Accepted)."""
    ops_svc = OperationsService(db)
    repo = DocumentRepository(db)
    doc = repo.get_by_id(document_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Documento '{document_id}' no encontrado.")

    job = ops_svc.submit_job(
        job_type="document_ocr",
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
        message="OCR de documento encolado para procesamiento asíncrono.",
        target_type="document",
        target_id=document_id
    )

@router.post("/sheets/{sheet_id}", response_model=List[ExtractedTextRead])
def process_sheet_ocr(
    sheet_id: str,
    request: Optional[OcrProcessRequest] = None,
    db: Session = Depends(get_db)
):
    """Ejecuta OCR síncrono sobre una lámina/hoja específica rasterizada."""
    service = OcrService(db)
    force = request.force_reprocess if request else False
    engine = request.engine if request else None

    try:
        texts = service.process_sheet_ocr(
            sheet_id=sheet_id,
            force_reprocess=force,
            preferred_engine=engine
        )
        return texts
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except FileNotFoundError as fe:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(fe))
    except RuntimeError as re:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(re))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error en OCR de hoja: {str(e)}")

@router.post("/sheets/{sheet_id}/async", response_model=AsyncJobAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
def process_sheet_ocr_async(
    sheet_id: str,
    request: Optional[OcrProcessRequest] = None,
    db: Session = Depends(get_db)
):
    """Encola OCR asíncrono para una lámina/hoja (HTTP 202 Accepted)."""
    ops_svc = OperationsService(db)
    repo = DocumentRepository(db)
    sheet = repo.get_sheet_by_id(sheet_id)
    if not sheet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lámina '{sheet_id}' no encontrada.")

    job = ops_svc.submit_job(
        job_type="sheet_ocr",
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
        message="OCR de lámina encolado para procesamiento asíncrono.",
        target_type="sheet",
        target_id=sheet_id
    )

@router.get("/documents/{document_id}/texts", response_model=List[ExtractedTextRead])
def list_document_texts(document_id: str, db: Session = Depends(get_db)):
    """Obtiene todos los textos extraídos con OCR de un documento completo."""
    repo = DocumentRepository(db)
    doc = repo.get_by_id(document_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Documento '{document_id}' no encontrado.")
    return repo.list_texts_by_document(document_id)

@router.get("/sheets/{sheet_id}/texts", response_model=List[ExtractedTextRead])
def list_sheet_texts(sheet_id: str, db: Session = Depends(get_db)):
    """Obtiene todos los textos extraídos con OCR de una lámina/hoja específica."""
    repo = DocumentRepository(db)
    sheet = repo.get_sheet_by_id(sheet_id)
    if not sheet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lámina '{sheet_id}' no encontrada.")
    return repo.list_texts_by_sheet(sheet_id)
