from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.operations import ReviewTaskRead, ReviewDecisionRequest, ReviewDecisionRead
from app.services.operations.service import OperationsService

router = APIRouter()

@router.get("", response_model=List[ReviewTaskRead])
def list_review_tasks(
    status_filter: Optional[str] = Query(None, alias="status", description="open, in_review, approved, corrected, rejected"),
    task_type: Optional[str] = Query(None, description="low_confidence_ocr, title_block_field_review, failed_processing_job, etc."),
    priority: Optional[str] = Query(None, description="low, medium, high, critical"),
    project_id: Optional[str] = Query(None, description="Filtrar por proyecto"),
    db: Session = Depends(get_db)
):
    """Lista las tareas pendientes en la cola de revisión humana (HITL)."""
    service = OperationsService(db)
    return service.list_review_tasks(
        status=status_filter,
        task_type=task_type,
        priority=priority,
        project_id=project_id
    )

@router.get("/{task_id}", response_model=ReviewTaskRead)
def get_review_task_detail(task_id: str, db: Session = Depends(get_db)):
    """Obtiene el detalle completo de una tarea de revisión y sus evidencias."""
    service = OperationsService(db)
    task = service.get_review_task(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Tarea '{task_id}' no encontrada.")
    return task

@router.post("/{task_id}/decision", response_model=ReviewDecisionRead)
def record_human_decision(
    task_id: str,
    payload: ReviewDecisionRequest,
    db: Session = Depends(get_db)
):
    """Registra la decisión humana (aprobación, corrección o rechazo) preservando el valor original."""
    service = OperationsService(db)
    try:
        return service.resolve_review_task(
            task_id=task_id,
            decision=payload.decision,
            corrected_value=payload.corrected_value,
            reviewer=payload.reviewer,
            reason_code=payload.reason_code,
            notes=payload.notes
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
