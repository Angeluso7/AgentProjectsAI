from typing import List
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models.core import Organization, User, OrganizationMembership
from app.schemas.organization import (
    OrganizationRead, OrganizationCreate, OrganizationMembershipRead,
    OrganizationMembershipCreate, OrganizationMembershipUpdate
)
from app.core.deps import get_current_tenant, require_role, TenantContext
from app.core.security import hash_password

router = APIRouter()

@router.get("/current", response_model=OrganizationRead)
def get_current_organization(tenant: TenantContext = Depends(get_current_tenant)):
    """Retorna la información de la organización activa en el contexto."""
    return tenant.organization

@router.get("/{organization_id}/members", response_model=List[OrganizationMembershipRead])
def list_organization_members(
    organization_id: str,
    tenant: TenantContext = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    """Lista todos los miembros y roles de la organización (Solo Admin)."""
    if tenant.organization.id != organization_id and not tenant.user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permiso para inspeccionar miembros de otra organización."
        )

    memberships = db.query(OrganizationMembership).filter(
        OrganizationMembership.organization_id == organization_id
    ).all()

    result = []
    for m in memberships:
        user = db.query(User).filter(User.id == m.user_id).first()
        result.append(
            OrganizationMembershipRead(
                id=m.id,
                organization_id=m.organization_id,
                user_id=m.user_id,
                user_email=user.email if user else None,
                user_display_name=user.display_name if user else None,
                role=m.role,
                status=m.status,
                created_at=m.created_at,
                updated_at=m.updated_at
            )
        )
    return result

@router.post("/{organization_id}/members", response_model=OrganizationMembershipRead, status_code=status.HTTP_201_CREATED)
def add_organization_member(
    organization_id: str,
    req: OrganizationMembershipCreate,
    tenant: TenantContext = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    """Agrega o invita a un nuevo usuario a la organización con un rol específico (Solo Admin)."""
    if tenant.organization.id != organization_id and not tenant.user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permiso para agregar miembros a otra organización."
        )

    # Buscar si el usuario ya existe por email
    user = db.query(User).filter(User.email == req.user_email).first()
    if not user:
        user = User(
            id=str(uuid.uuid4()),
            email=req.user_email,
            display_name=req.display_name or req.user_email.split('@')[0],
            password_hash=hash_password(req.initial_password or "Temporal123!"),
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    # Verificar si ya tiene membresía en esta organización
    existing_mem = db.query(OrganizationMembership).filter(
        OrganizationMembership.organization_id == organization_id,
        OrganizationMembership.user_id == user.id
    ).first()

    if existing_mem:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El usuario '{req.user_email}' ya es miembro de esta organización."
        )

    new_mem = OrganizationMembership(
        id=str(uuid.uuid4()),
        organization_id=organization_id,
        user_id=user.id,
        role=req.role,
        status="active"
    )
    db.add(new_mem)
    db.commit()
    db.refresh(new_mem)

    return OrganizationMembershipRead(
        id=new_mem.id,
        organization_id=new_mem.organization_id,
        user_id=new_mem.user_id,
        user_email=user.email,
        user_display_name=user.display_name,
        role=new_mem.role,
        status=new_mem.status,
        created_at=new_mem.created_at,
        updated_at=new_mem.updated_at
    )

@router.patch("/{organization_id}/members/{membership_id}", response_model=OrganizationMembershipRead)
def update_organization_member(
    organization_id: str,
    membership_id: str,
    req: OrganizationMembershipUpdate,
    tenant: TenantContext = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    """Modifica el rol o estado de una membresía existente (Solo Admin)."""
    if tenant.organization.id != organization_id and not tenant.user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado.")

    mem = db.query(OrganizationMembership).filter(
        OrganizationMembership.id == membership_id,
        OrganizationMembership.organization_id == organization_id
    ).first()

    if not mem:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membresía no encontrada.")

    if req.role:
        mem.role = req.role
    if req.status:
        mem.status = req.status
    db.commit()
    db.refresh(mem)

    user = db.query(User).filter(User.id == mem.user_id).first()
    return OrganizationMembershipRead(
        id=mem.id,
        organization_id=mem.organization_id,
        user_id=mem.user_id,
        user_email=user.email if user else None,
        user_display_name=user.display_name if user else None,
        role=mem.role,
        status=mem.status,
        created_at=mem.created_at,
        updated_at=mem.updated_at
    )
