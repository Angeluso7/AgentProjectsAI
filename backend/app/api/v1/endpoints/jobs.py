from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.operations import ProcessingJobRead, JobEventRead
from app.services.operations.service import OperationsService

router = APIRouter()

@router.get("", response_model=List[ProcessingJobRead])
def list_jobs(
    status_filter: Optional[str] = Query(None, alias="status", description="Filtrar por estado"),
    job_type: Optional[str] = Query(None, description="Filtrar por tipo de job"),
    target_type: Optional[str] = Query(None, description="Filtrar por tipo de target"),
    target_id: Optional[str] = Query(None, description="Filtrar por ID de target"),
    project_id: Optional[str] = Query(None, description="Filtrar por ID de proyecto"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """Lista los jobs de procesamiento con soporte para filtros de auditoría."""
    service = OperationsService(db)
    return service.list_jobs(
        status=status_filter,
        job_type=job_type,
        target_type=target_type,
        target_id=target_id,
        project_id=project_id,
        limit=limit,
        offset=offset
    )

@router.get("/{job_id}", response_model=ProcessingJobRead)
def get_job_detail(job_id: str, db: Session = Depends(get_db)):
    """Obtiene el detalle completo de un job, su estado, progreso, tiempos y errores."""
    service = OperationsService(db)
    job = service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job '{job_id}' no encontrado.")
    return job

@router.post("/{job_id}/retry", response_model=ProcessingJobRead)
def retry_job(job_id: str, db: Session = Depends(get_db)):
    """Reintenta manualmente la ejecución de un job fallido o cancelado."""
    service = OperationsService(db)
    try:
        return service.retry_job(job_id)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))

@router.post("/{job_id}/cancel", response_model=ProcessingJobRead)
def cancel_job(job_id: str, db: Session = Depends(get_db)):
    """Solicita la cancelación de un job en cola o en ejecución."""
    service = OperationsService(db)
    try:
        return service.cancel_job(job_id)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))

@router.get("/{job_id}/events", response_model=List[JobEventRead])
def list_job_events(job_id: str, db: Session = Depends(get_db)):
    """Consulta la bitácora inmutable de eventos y transiciones de estado de un job."""
    service = OperationsService(db)
    job = service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job '{job_id}' no encontrado.")
    return service.list_job_events(job_id)
