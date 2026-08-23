from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.repositories.review_repository import ReviewRepository
from app.schemas.review import ReviewRunCreate, ReviewRunRead, FindingRead
from app.services.decision_engine.service import DecisionEngineService

router = APIRouter()

@router.get("/", response_model=List[ReviewRunRead])
def list_review_runs(project_id: Optional[str] = None, db: Session = Depends(get_db)):
    """Lista las sesiones de auditoría ejecutadas."""
    repo = ReviewRepository(db)
    if project_id:
        return repo.list_by_project(project_id)
    return repo.list_all()

@router.post("/", response_model=ReviewRunRead, status_code=status.HTTP_201_CREATED)
def start_review_run(run_in: ReviewRunCreate, db: Session = Depends(get_db)):
    """Inicia una nueva sesión de auditoría/revisión sobre planos."""
    engine = DecisionEngineService(db)
    return engine.execute_review_run(
        project_id=run_in.project_id,
        run_name=run_in.run_name,
        document_ids=run_in.document_ids
    )

@router.get("/{run_id}", response_model=ReviewRunRead)
def get_review_run(run_id: str, db: Session = Depends(get_db)):
    """Obtiene el resultado detallado de una sesión de auditoría."""
    repo = ReviewRepository(db)
    run = repo.get_by_id(run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sesión de revisión no encontrada")
    return run

@router.get("/{run_id}/findings", response_model=List[FindingRead])
def list_run_findings(run_id: str, db: Session = Depends(get_db)):
    """Lista los hallazgos de una sesión de revisión específica."""
    repo = ReviewRepository(db)
    run = repo.get_by_id(run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sesión de revisión no encontrada")
    return repo.list_findings(run_id)
