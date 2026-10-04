from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.deps import get_current_tenant, TenantContext
from app.schemas.assistant import (
    AssistantExecutionRequest,
    AssistantExecutionResponse,
    AssistantFeedbackRequest,
    AssistantInteractionRead,
    AssistantTaskCatalogItem
)
from app.services.assistant.service import AssistantService

router = APIRouter()

@router.get("/tasks", response_model=List[AssistantTaskCatalogItem])
def get_assistant_task_catalog(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_current_tenant)
):
    """Retorna el catálogo canónico de las 8 tareas asistidas y sus políticas de routing de motores."""
    service = AssistantService(db)
    return service.get_task_catalog()

@router.post("/execute", response_model=AssistantExecutionResponse)
def execute_assistant_task(
    payload: AssistantExecutionRequest,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_current_tenant)
):
    """
    Ejecuta una tarea asistida utilizando RAG gobernado y orquestación de motores IA por tiers.
    Garantiza que solo se consuma conocimiento aprobado y registra la interacción de forma trazable.
    """
    service = AssistantService(db)
    author = getattr(tenant.user, "email", "system") if hasattr(tenant, "user") else "system"
    return service.execute_task(
        organization_id=tenant.organization.id,
        payload=payload,
        user_id=author
    )

@router.post("/interactions/{interaction_id}/feedback", response_model=AssistantInteractionRead)
def submit_assistant_feedback(
    interaction_id: str,
    payload: AssistantFeedbackRequest,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_current_tenant)
):
    """Registra el feedback HITL del usuario (aceptada, editada o rechazada) para una interacción asistida."""
    service = AssistantService(db)
    author = getattr(tenant.user, "email", "system") if hasattr(tenant, "user") else "system"
    interaction = service.submit_feedback(
        interaction_id=interaction_id,
        organization_id=tenant.organization.id,
        payload=payload,
        user_id=author
    )
    if not interaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interacción con ID '{interaction_id}' no encontrada en la organización."
        )
    return interaction

@router.get("/interactions", response_model=List[AssistantInteractionRead])
def list_assistant_interactions(
    project_id: Optional[str] = Query(None, description="Filtrar por proyecto (opcional)"),
    task_type: Optional[str] = Query(None, description="Filtrar por tipo de tarea (opcional)"),
    feedback_status: Optional[str] = Query(None, description="Filtrar por estado de feedback (opcional)"),
    limit: int = Query(50, ge=1, le=200, description="Límite de registros"),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_current_tenant)
):
    """Lista el historial trazable de interacciones asistidas para auditoría y aprendizaje activo."""
    service = AssistantService(db)
    return service.list_interactions(
        organization_id=tenant.organization.id,
        project_id=project_id,
        task_type=task_type,
        feedback_status=feedback_status,
        limit=limit
    )
