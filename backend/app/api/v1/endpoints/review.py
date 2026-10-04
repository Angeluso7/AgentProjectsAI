from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.repositories.review_repository import ReviewRepository
from app.schemas.review import ReviewRunCreate, ReviewRunRead, FindingRead, HumanFeedbackCreate, HumanFeedbackRead
from app.services.decision_engine.service import DecisionEngineService
from app.services.human_review.service import HumanReviewService

router = APIRouter()

@router.get("/runs", response_model=List[ReviewRunRead])
def list_review_runs(project_id: Optional[str] = None, db: Session = Depends(get_db)):
    """Lista las sesiones de auditoría ejecutadas."""
    repo = ReviewRepository(db)
    if project_id:
        return repo.list_by_project(project_id)
    return repo.list_all()

@router.post("/runs", response_model=ReviewRunRead, status_code=status.HTTP_201_CREATED)
def start_review_run(run_in: ReviewRunCreate, db: Session = Depends(get_db)):
    """Inicia una nueva sesión de auditoría/revisión sobre planos."""
    engine = DecisionEngineService(db)
    return engine.execute_review_run(
        project_id=run_in.project_id,
        run_name=run_in.run_name,
        document_ids=run_in.document_ids
    )

@router.get("/runs/{run_id}", response_model=ReviewRunRead)
def get_review_run(run_id: str, db: Session = Depends(get_db)):
    """Obtiene el resultado detallado de una sesión de auditoría."""
    repo = ReviewRepository(db)
    run = repo.get_by_id(run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sesión de revisión no encontrada")
    return run

@router.get("/runs/{run_id}/findings", response_model=List[FindingRead])
def list_run_findings(run_id: str, db: Session = Depends(get_db)):
    """Lista los hallazgos de una sesión de revisión."""
    repo = ReviewRepository(db)
    return repo.list_findings(run_id)

@router.post("/findings/{finding_id}/feedback", response_model=HumanFeedbackRead)
def submit_human_feedback(finding_id: str, feedback_in: HumanFeedbackCreate, db: Session = Depends(get_db)):
    """Registra la validación o corrección humana (HITL) sobre un hallazgo."""
    svc = HumanReviewService(db)
    try:
        return svc.submit_feedback(finding_id=finding_id, feedback_in=feedback_in)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
