from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.operations import ConfidencePolicyRead, ConfidencePolicyCreate
from app.services.operations.service import OperationsService

router = APIRouter()

@router.get("", response_model=List[ConfidencePolicyRead])
def list_policies(
    applies_to: Optional[str] = Query(None, description="Filtrar por ámbito: ocr_text, title_block_field, title_block_match, normative_source"),
    db: Session = Depends(get_db)
):
    """Consulta las políticas de confianza activas y sus umbrales de revisión."""
    service = OperationsService(db)
    return service.list_policies(applies_to=applies_to)

@router.post("", response_model=ConfidencePolicyRead, status_code=status.HTTP_201_CREATED)
def create_policy(payload: ConfidencePolicyCreate, db: Session = Depends(get_db)):
    """Crea una nueva política de confianza versionada."""
    service = OperationsService(db)
    try:
        return service.create_policy(payload.model_dump())
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/seed-defaults", response_model=List[ConfidencePolicyRead])
def seed_default_policies(db: Session = Depends(get_db)):
    """Inicializa las políticas de confianza baseline (conservadoras y provisionales)."""
    service = OperationsService(db)
    service.seed_default_policies()
    return service.list_policies()
