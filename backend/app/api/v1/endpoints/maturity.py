from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.deps import get_current_tenant, TenantContext
from app.schemas.maturity import (
    ProjectMaturityProfileRead, ProjectMaturityEvaluationRequest,
    AcquisitionRouteItem
)
from app.services.maturity.service import ProjectMaturityService

router = APIRouter()

@router.get("/projects/{project_id}/maturity/latest", response_model=ProjectMaturityProfileRead)
def get_latest_project_maturity(
    project_id: str,
    stage: Optional[str] = None,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Obtiene el perfil de madurez / suficiencia informacional más reciente del proyecto.
    Si no existe uno previo, ejecuta la evaluación inicial automáticamente.
    """
    profile = ProjectMaturityService.get_latest_maturity(db, project_id, stage=stage)
    if not profile:
        profile = ProjectMaturityService.evaluate_project_maturity(
            db=db,
            project_id=project_id,
            stage=stage,
            evaluated_by=tenant.user.email if tenant.user else "system"
        )
    return profile

@router.post("/projects/{project_id}/maturity/evaluate", response_model=ProjectMaturityProfileRead)
def evaluate_project_maturity(
    project_id: str,
    request: ProjectMaturityEvaluationRequest,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Dispara la evaluación diagnóstica en tiempo real del perfil de madurez informacional,
    generando brechas críticas, rutas de adquisición y delta respecto al estado anterior.
    """
    try:
        profile = ProjectMaturityService.evaluate_project_maturity(
            db=db,
            project_id=project_id,
            stage=request.stage,
            target_level=request.target_level or "advanced",
            evaluated_by=tenant.user.email if tenant.user else "system"
        )
        return profile
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error evaluando madurez: {str(e)}")

@router.get("/projects/{project_id}/maturity/history", response_model=List[ProjectMaturityProfileRead])
def get_project_maturity_history(
    project_id: str,
    limit: int = 15,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Retorna el historial de evaluaciones de madurez del proyecto para visualizar su evolución temporal.
    """
    return ProjectMaturityService.get_maturity_history(db, project_id=project_id, limit=limit)

@router.get("/projects/{project_id}/maturity/acquisition-routes", response_model=List[Dict[str, Any]])
def get_project_acquisition_routes(
    project_id: str,
    stage: Optional[str] = None,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Retorna la lista priorizada de rutas sugeridas de adquisición de información para resolver brechas.
    """
    profile = ProjectMaturityService.get_latest_maturity(db, project_id, stage=stage)
    if not profile:
        profile = ProjectMaturityService.evaluate_project_maturity(
            db=db,
            project_id=project_id,
            stage=stage,
            evaluated_by=tenant.user.email if tenant.user else "system"
        )
    return profile.acquisition_routes or []

@router.get("/projects/{project_id}/maturity/{profile_id}/export")
def export_project_maturity_profile(
    project_id: str,
    profile_id: str,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Exporta el perfil de madurez en formato JSON estructurado con hash criptográfico SHA-256.
    """
    history = ProjectMaturityService.get_maturity_history(db, project_id=project_id, limit=100)
    profile = next((p for p in history if p.id == profile_id), None)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Perfil de madurez no encontrado.")
    return ProjectMaturityService.export_maturity_profile_json(profile)
