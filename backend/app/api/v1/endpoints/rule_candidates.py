from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.deps import get_current_tenant, TenantContext
from app.schemas.rule_candidates import (
    PromoteRuleCandidateRequest, PromoteRuleCandidateResponse
)
from app.services.rules.promotion_service import RulePromotionService

router = APIRouter()


@router.post(
    "/{candidate_id}/promote",
    response_model=PromoteRuleCandidateResponse,
    status_code=status.HTTP_200_OK,
    summary="Promover regla candidata a Baseline QA/QC del Sistema"
)
def promote_rule_candidate(
    candidate_id: str,
    payload: PromoteRuleCandidateRequest,
    db: Session = Depends(get_db),
    tenant: Optional[TenantContext] = Depends(get_current_tenant),
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
    x_organization_id: Optional[str] = Header(None, alias="X-Organization-Id"),
    x_role: Optional[str] = Header(None, alias="X-Role"),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role")
):
    """
    Endpoint explícito para la promoción de reglas candidatas validadas hacia
    RuleDefinition + Baseline QA/QC + RuleApplicability aprobada.
    - Valida roles autorizados (admin, audit_lead, auditor).
    - Aplica aislamiento multi-tenant.
    - Deriva linaje inmutable desde base de datos.
    - Idempotente: no genera duplicados.
    - Excluye estrictamente símbolos y plantillas de simbología.
    """
    # Resolver usuario, rol y organización efectiva
    effective_user_id = x_user_id or (tenant.user.id if tenant and tenant.user else "auditor_lead")
    effective_role = x_user_role or x_role or (tenant.role if tenant else "admin")
    effective_org_id = x_organization_id or (tenant.organization.id if tenant and tenant.organization else None)

    return RulePromotionService.promote_candidate(
        db=db,
        candidate_id=candidate_id,
        payload=payload,
        user_id=effective_user_id,
        user_role=effective_role,
        organization_id=effective_org_id
    )
