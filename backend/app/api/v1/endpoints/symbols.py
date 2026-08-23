from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.repositories.document_repository import DocumentRepository
from app.schemas.symbol import (
    DetectedSymbolRead, SymbolDetectProcessRequest, SheetSymbolsSummaryResponse
)
from app.schemas.operations import AsyncJobAcceptedResponse
from app.services.symbols.service import SymbolService
from app.services.operations.service import OperationsService

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
