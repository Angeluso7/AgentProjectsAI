from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import json

from app.db.session import get_db
from app.db.repositories.project_repository import ProjectRepository
from app.schemas.project import (
    ProjectCreate, ProjectRead, ProjectUpdate,
    ProjectVersionCreate, ProjectVersionRead,
    ProjectExportPayload
)
from app.core.deps import get_current_tenant, require_role, TenantContext

router = APIRouter()

@router.get("", response_model=List[ProjectRead], include_in_schema=False)
@router.get("/", response_model=List[ProjectRead])
def list_projects(
    include_archived: bool = Query(True, description="Incluir proyectos archivados"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filtrar por estado"),
    skip: int = 0,
    limit: int = 100,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Lista todos los proyectos registrados dentro de la organización activa con contadores de entidades."""
    repo = ProjectRepository(db)
    return repo.list_by_organization(
        organization_id=tenant.organization.id,
        include_archived=include_archived,
        status=status_filter,
        skip=skip,
        limit=limit
    )

@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED, include_in_schema=False)
@router.post("/", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(
    project_in: ProjectCreate,
    tenant: TenantContext = Depends(require_role(["admin", "audit_lead", "contributor"])),
    db: Session = Depends(get_db)
):
    """Crea un nuevo proyecto en la organización activa con su etapa y disciplina."""
    repo = ProjectRepository(db)
    existing = repo.get_by_code(project_in.code, organization_id=tenant.organization.id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya existe un proyecto con el código {project_in.code} en esta organización."
        )
    return repo.create_project(project_in, organization_id=tenant.organization.id)

@router.get("/{project_id}", response_model=ProjectRead)
def get_project(
    project_id: str,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Obtiene el detalle de un proyecto por ID con sus métricas y etapa."""
    repo = ProjectRepository(db)
    project = repo.get_by_id_and_organization(project_id, organization_id=tenant.organization.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proyecto no encontrado")
    return repo._to_read_schema(project)

@router.put("/{project_id}", response_model=ProjectRead)
def update_project(
    project_id: str,
    update_in: ProjectUpdate,
    tenant: TenantContext = Depends(require_role(["admin", "audit_lead", "contributor"])),
    db: Session = Depends(get_db)
):
    """Actualiza la información, etapa o estado de un proyecto dentro de la organización activa."""
    repo = ProjectRepository(db)
    project = repo.get_by_id_and_organization(project_id, organization_id=tenant.organization.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proyecto no encontrado")
    
    # Si se intenta cambiar el código, validar que no colisione
    if update_in.code and update_in.code != project.code:
        existing = repo.get_by_code(update_in.code, organization_id=tenant.organization.id)
        if existing and existing.id != project.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ya existe otro proyecto con el código {update_in.code}."
            )

    return repo.update_project(project, update_in.model_dump(exclude_unset=True))

@router.put("/{project_id}/archive", response_model=ProjectRead)
def archive_project(
    project_id: str,
    tenant: TenantContext = Depends(require_role(["admin", "audit_lead"])),
    db: Session = Depends(get_db)
):
    """Archiva un proyecto para retirarlo del flujo activo normal sin destruirlo."""
    repo = ProjectRepository(db)
    archived = repo.archive_project(project_id, organization_id=tenant.organization.id)
    if not archived:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proyecto no encontrado")
    return archived

@router.put("/{project_id}/unarchive", response_model=ProjectRead)
def unarchive_project(
    project_id: str,
    tenant: TenantContext = Depends(require_role(["admin", "audit_lead"])),
    db: Session = Depends(get_db)
):
    """Restaura un proyecto archivado a estado activo."""
    repo = ProjectRepository(db)
    unarchived = repo.unarchive_project(project_id, organization_id=tenant.organization.id)
    if not unarchived:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proyecto no encontrado")
    return unarchived

@router.delete("/{project_id}", status_code=status.HTTP_200_OK)
def delete_project(
    project_id: str,
    hard_delete: bool = Query(False, description="True para borrado físico en cascada, False para soft-delete"),
    tenant: TenantContext = Depends(require_role(["admin", "audit_lead"])),
    db: Session = Depends(get_db)
):
    """Elimina o marca como eliminado un proyecto dentro de la organización activa."""
    repo = ProjectRepository(db)
    success = repo.delete_project(project_id, organization_id=tenant.organization.id, hard_delete=hard_delete)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proyecto no encontrado")
    return {"message": "Proyecto eliminado exitosamente", "project_id": project_id, "hard_delete": hard_delete}

@router.get("/{project_id}/export", response_model=ProjectExportPayload)
def export_project(
    project_id: str,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Exporta toda la información, trazabilidad, documentos, selecciones y hallazgos del proyecto en formato estructurado JSON."""
    repo = ProjectRepository(db)
    export_payload = repo.export_project_data(project_id, organization_id=tenant.organization.id)
    if not export_payload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proyecto no encontrado")
    return export_payload

@router.post("/{project_id}/versions", response_model=ProjectVersionRead, status_code=status.HTTP_201_CREATED)
def add_project_version(
    project_id: str,
    version_in: ProjectVersionCreate,
    tenant: TenantContext = Depends(require_role(["admin", "audit_lead", "contributor"])),
    db: Session = Depends(get_db)
):
    """Crea una nueva versión de entrega para un proyecto dentro de la organización activa."""
    repo = ProjectRepository(db)
    project = repo.get_by_id_and_organization(project_id, organization_id=tenant.organization.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proyecto no encontrado")
    return repo.add_version(project_id, version_in)
