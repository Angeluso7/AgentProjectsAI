from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models.decision_memory import RuleFinding
from app.schemas.qa_rule import RuleFindingRead, FindingResolutionRequest, FindingResolutionRead
from app.schemas.review import HumanFeedbackCreate, HumanFeedbackRead
from app.services.rules.engine import RuleEngine
from app.services.human_review.service import HumanReviewService

router = APIRouter()

@router.get("", response_model=List[RuleFindingRead])
def list_findings(
    document_id: Optional[str] = Query(None, description="Filtrar por ID de documento"),
    sheet_id: Optional[str] = Query(None, description="Filtrar por ID de lámina"),
    severity: Optional[str] = Query(None, description="critical, high, medium, low, info"),
    status_filter: Optional[str] = Query(None, alias="status", description="open, confirmed, dismissed, corrected, accepted_risk"),
    db: Session = Depends(get_db)
):
    """Lista hallazgos de auditoría QA/QC con filtros por severidad, estado y lámina."""
    engine = RuleEngine(db)
    return engine.list_findings(
        document_id=document_id,
        sheet_id=sheet_id,
        severity=severity,
        status=status_filter
    )

@router.get("/{finding_id}", response_model=RuleFindingRead)
def get_finding(finding_id: str, db: Session = Depends(get_db)):
    """Obtiene el detalle completo de un hallazgo con evidencias y resoluciones."""
    engine = RuleEngine(db)
    finding = engine.get_finding(finding_id)
    if not finding:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Hallazgo '{finding_id}' no encontrado.")
    return finding

@router.post("/{finding_id}/resolve", response_model=RuleFindingRead)
def resolve_finding(
    finding_id: str,
    resolution: FindingResolutionRequest,
    db: Session = Depends(get_db)
):
    """Registra la resolución o dictamen de auditoría sobre un hallazgo (confirmed, dismissed, corrected, accepted_risk)."""
    engine = RuleEngine(db)
    try:
        return engine.resolve_finding(finding_id=finding_id, resolution_data=resolution.model_dump())
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error al resolver hallazgo: {str(e)}")

@router.post("/{finding_id}/feedback", response_model=HumanFeedbackRead)
def submit_human_feedback(finding_id: str, feedback_in: HumanFeedbackCreate, db: Session = Depends(get_db)):
    """Registra supervisión humana de reentrenamiento sobre un hallazgo."""
    svc = HumanReviewService(db)
    try:
        return svc.submit_feedback(finding_id=finding_id, feedback_in=feedback_in)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
