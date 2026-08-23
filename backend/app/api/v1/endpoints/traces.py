from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.operations import DecisionTraceRead
from app.services.operations.service import OperationsService
from app.core.deps import get_current_tenant, require_role, TenantContext

router = APIRouter()

@router.get("/{entity_type}/{entity_id}", response_model=List[DecisionTraceRead])
def get_entity_traces(
    entity_type: str,
    entity_id: str,
    tenant: TenantContext = Depends(require_role(["admin", "audit_lead", "reviewer"])),
    db: Session = Depends(get_db)
):
    """Consulta la trazabilidad de inferencias, políticas y revisiones de una entidad (Solo Admin, Audit Lead, Reviewer)."""
    service = OperationsService(db)
    traces = service.list_traces_by_entity(entity_type, entity_id)
    # Filtrar por organization_id del tenant
    filtered = [t for t in traces if getattr(t, "organization_id", None) in (tenant.organization.id, None)]
    return filtered
