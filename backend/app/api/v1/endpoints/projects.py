import os
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Response, UploadFile, File, Form
from fastapi.responses import JSONResponse, FileResponse
from sqlalchemy.orm import Session
import json

from app.db.session import get_db
from app.db.repositories.project_repository import ProjectRepository
from app.db.repositories.document_repository import DocumentRepository
from app.services.ingest.service import IngestService
from app.schemas.project import (
    ProjectCreate, ProjectRead, ProjectUpdate,
    ProjectVersionCreate, ProjectVersionRead,
    ProjectExportPayload, ProjectDeletionImpact,
    ProjectClearContentRequest, ProjectDeleteConfirmedRequest,
    ProjectLifecycleResult
)
from app.schemas.document import (
    ProjectDocumentView, to_project_document_view, DocumentProcessRequest
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
    from sqlalchemy.exc import IntegrityError

    repo = ProjectRepository(db)
    clean_code = project_in.code.strip()
    existing = repo.get_by_code(clean_code, organization_id=tenant.organization.id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": f"El código {clean_code} ya existe en esta organización.",
                "conflict_type": "duplicate_code",
                "existing_project": {
                    "id": existing.id,
                    "code": existing.code,
                    "name": existing.name,
                    "status": existing.status,
                    "is_archived": existing.status == "archived"
                }
            }
        )
    try:
        return repo.create_project(project_in, organization_id=tenant.organization.id)
    except IntegrityError:
        db.rollback()
        conflict = repo.get_by_code(clean_code, organization_id=tenant.organization.id)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": f"El código {clean_code} ya existe en esta organización.",
                "conflict_type": "duplicate_code",
                "existing_project": {
                    "id": conflict.id if conflict else "",
                    "code": conflict.code if conflict else clean_code,
                    "name": conflict.name if conflict else "",
                    "status": conflict.status if conflict else "active",
                    "is_archived": conflict.status == "archived" if conflict else False
                }
            }
        )

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
    if update_in.code and update_in.code.strip() != project.code:
        clean_code = update_in.code.strip()
        existing = repo.get_by_code(clean_code, organization_id=tenant.organization.id)
        if existing and existing.id != project.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": f"Ya existe otro proyecto con el código «{clean_code}».",
                    "conflict_type": "duplicate_code",
                    "existing_project": {
                        "id": existing.id,
                        "code": existing.code,
                        "name": existing.name,
                        "status": existing.status,
                        "is_archived": existing.status == "archived"
                    }
                }
            )

    return repo.update_project(project, update_in.model_dump(exclude_unset=True))

@router.get("/{project_id}/deletion-impact", response_model=ProjectDeletionImpact)
def get_project_deletion_impact(
    project_id: str,
    tenant: TenantContext = Depends(require_role(["admin", "audit_lead", "reviewer", "contributor"])),
    db: Session = Depends(get_db)
):
    """Calcula y devuelve el resumen del impacto de vaciar o eliminar un proyecto."""
    repo = ProjectRepository(db)
    impact = repo.get_deletion_impact(project_id, organization_id=tenant.organization.id)
    if not impact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proyecto no encontrado")
    return impact

@router.patch("/{project_id}/archive", response_model=ProjectRead)
@router.put("/{project_id}/archive", response_model=ProjectRead, include_in_schema=False)
def archive_project(
    project_id: str,
    tenant: TenantContext = Depends(require_role(["admin", "audit_lead"])),
    db: Session = Depends(get_db)
):
    """Archiva un proyecto para retirarlo del flujo activo normal sin destruirlo."""
    repo = ProjectRepository(db)
    archived = repo.archive_project(
        project_id,
        organization_id=tenant.organization.id,
        user_id=tenant.user.id if hasattr(tenant, "user") and tenant.user else None
    )
    if not archived:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proyecto no encontrado")
    return archived

@router.patch("/{project_id}/restore", response_model=ProjectRead)
@router.put("/{project_id}/restore", response_model=ProjectRead, include_in_schema=False)
@router.put("/{project_id}/unarchive", response_model=ProjectRead, include_in_schema=False)
def restore_project(
    project_id: str,
    tenant: TenantContext = Depends(require_role(["admin", "audit_lead"])),
    db: Session = Depends(get_db)
):
    """Restaura un proyecto archivado a estado activo."""
    repo = ProjectRepository(db)
    restored = repo.restore_project(
        project_id,
        organization_id=tenant.organization.id,
        user_id=tenant.user.id if hasattr(tenant, "user") and tenant.user else None
    )
    if not restored:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proyecto no encontrado")
    return restored

@router.post("/{project_id}/clear-content", response_model=ProjectLifecycleResult)
def clear_project_content(
    project_id: str,
    payload: ProjectClearContentRequest,
    tenant: TenantContext = Depends(require_role(["admin", "audit_lead"])),
    db: Session = Depends(get_db)
):
    """Vacía de forma transaccional todo el contenido del proyecto (documentos, láminas, archivos, hallazgos) conservando su ficha."""
    repo = ProjectRepository(db)
    result = repo.clear_project_content(
        project_id=project_id,
        organization_id=tenant.organization.id,
        confirmation_code=payload.confirmation_code,
        reason=payload.reason,
        acknowledge_data_loss=payload.acknowledge_data_loss,
        user_id=tenant.user.id if hasattr(tenant, "user") and tenant.user else None
    )
    if not result.success and result.error == "confirmation_code_mismatch":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.message)
    if not result.success and result.status == "not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result.message)
    if not result.success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=result.message)
    return result

@router.post("/{project_id}/delete-confirmed", response_model=ProjectLifecycleResult)
def delete_project_confirmed(
    project_id: str,
    payload: ProjectDeleteConfirmedRequest,
    tenant: TenantContext = Depends(require_role(["admin", "audit_lead"])),
    db: Session = Depends(get_db)
):
    """Elimina definitivamente o anonimiza un proyecto con purga exhaustiva de almacenamiento físico y dependencias en BD."""
    repo = ProjectRepository(db)
    result = repo.delete_confirmed(
        project_id=project_id,
        organization_id=tenant.organization.id,
        confirmation_code=payload.confirmation_code,
        mode=payload.mode,
        reason=payload.reason,
        acknowledge_data_loss=payload.acknowledge_data_loss,
        user_id=tenant.user.id if hasattr(tenant, "user") and tenant.user else None
    )
    if not result.success and result.error == "confirmation_code_mismatch":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.message)
    if not result.success and result.status == "not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result.message)
    if not result.success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=result.message)
    return result

@router.delete("/{project_id}", status_code=status.HTTP_200_OK)
def delete_project(
    project_id: str,
    confirmation_code: Optional[str] = Query(None, description="Código de confirmación para borrado definitivo"),
    mode: str = Query("hard_delete", description="hard_delete | anonymize"),
    acknowledge_data_loss: bool = Query(True),
    hard_delete: bool = Query(False, description="True para borrado físico en cascada, False para soft-delete"),
    tenant: TenantContext = Depends(require_role(["admin", "audit_lead"])),
    db: Session = Depends(get_db)
):
    """Elimina o marca como eliminado un proyecto dentro de la organización activa."""
    repo = ProjectRepository(db)
    if confirmation_code:
        result = repo.delete_confirmed(
            project_id=project_id,
            organization_id=tenant.organization.id,
            confirmation_code=confirmation_code,
            mode=mode,
            acknowledge_data_loss=acknowledge_data_loss,
            user_id=tenant.user.id if hasattr(tenant, "user") and tenant.user else None
        )
        if not result.success and result.error == "confirmation_code_mismatch":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.message)
        if not result.success and result.status == "not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result.message)
        if not result.success:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=result.message)
        return {"message": result.message, "project_id": project_id, "hard_delete": True, "result": result.model_dump()}

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


# ====================================================================
# Ciclo Operativo de Documentos por Proyecto
# ====================================================================

@router.post("/{project_id}/documents", response_model=ProjectDocumentView, status_code=status.HTTP_201_CREATED)
async def upload_project_document(
    project_id: str,
    file: UploadFile = File(...),
    discipline: Optional[str] = Form(None),
    document_type: Optional[str] = Form(None),
    auto_process: bool = Form(True),
    dpi: Optional[int] = Form(None),
    metadata_json: Optional[str] = Form(None),
    tenant: TenantContext = Depends(require_role(["admin", "audit_lead", "contributor"])),
    db: Session = Depends(get_db)
):
    """Carga y asocia un documento técnico al proyecto indicado dentro de la organización activa."""
    proj_repo = ProjectRepository(db)
    project = proj_repo.get_by_id_and_organization(project_id, organization_id=tenant.organization.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proyecto no encontrado en esta organización")

    if not file or not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Archivo no enviado o nombre de archivo vacío."
        )

    content = await file.read()
    ingest_svc = IngestService(db)

    meta_extra: dict = {
        "original_filename": file.filename,
        "uploaded_by": tenant.user.email if hasattr(tenant, "user") and tenant.user else None
    }
    if metadata_json:
        try:
            parsed = json.loads(metadata_json)
            if isinstance(parsed, dict):
                meta_extra.update(parsed)
        except Exception:
            meta_extra["raw_metadata"] = metadata_json

    if discipline:
        meta_extra["discipline"] = discipline
    elif project.discipline:
        meta_extra["discipline"] = project.discipline

    if document_type:
        meta_extra["document_type"] = document_type

    try:
        doc = ingest_svc.ingest_file(
            project_id=project_id,
            filename=file.filename or "document.pdf",
            file_bytes=content,
            auto_process=auto_process,
            dpi=dpi,
            metadata_extra=meta_extra
        )
        return to_project_document_view(doc, project)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error al cargar documento: {str(e)}")


@router.get("/{project_id}/documents", response_model=List[ProjectDocumentView])
def list_project_documents(
    project_id: str,
    status_filter: Optional[str] = Query(None, alias="status", description="Filtrar por processing_status opcional"),
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Lista todos los documentos del proyecto con todos sus estados operativos (uploaded, queued, processing, processed, failed)."""
    proj_repo = ProjectRepository(db)
    project = proj_repo.get_by_id_and_organization(project_id, organization_id=tenant.organization.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proyecto no encontrado en esta organización")

    doc_repo = DocumentRepository(db)
    docs = doc_repo.list_by_project_all_statuses(project_id=project_id, organization_id=tenant.organization.id)
    
    views = [to_project_document_view(d, project) for d in docs]
    if status_filter:
        views = [
            v for v in views
            if v.processing_status == status_filter or (status_filter == "processed" and v.processing_status in ("processed", "ready"))
        ]
    return views


@router.get("/{project_id}/documents/{document_id}", response_model=ProjectDocumentView)
def get_project_document(
    project_id: str,
    document_id: str,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Consulta la ficha unificada de un documento de proyecto."""
    proj_repo = ProjectRepository(db)
    project = proj_repo.get_by_id_and_organization(project_id, organization_id=tenant.organization.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proyecto no encontrado")

    doc_repo = DocumentRepository(db)
    doc = doc_repo.get_by_id(document_id)
    if not doc or doc.project_id != project_id or doc.organization_id != tenant.organization.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento no encontrado en este proyecto")

    return to_project_document_view(doc, project)


@router.post("/{project_id}/documents/{document_id}/process", response_model=ProjectDocumentView)
def process_project_document(
    project_id: str,
    document_id: str,
    request: Optional[DocumentProcessRequest] = None,
    tenant: TenantContext = Depends(require_role(["admin", "audit_lead", "contributor"])),
    db: Session = Depends(get_db)
):
    """Procesa o reprocesa un documento de proyecto."""
    proj_repo = ProjectRepository(db)
    project = proj_repo.get_by_id_and_organization(project_id, organization_id=tenant.organization.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proyecto no encontrado")

    doc_repo = DocumentRepository(db)
    doc = doc_repo.get_by_id(document_id)
    if not doc or doc.project_id != project_id or doc.organization_id != tenant.organization.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento no encontrado en este proyecto")

    ingest_svc = IngestService(db)
    target_dpi = request.dpi if request else None
    try:
        updated_doc = ingest_svc.process_document(document_id=document_id, dpi=target_dpi)
        return to_project_document_view(updated_doc, project)
    except Exception as e:
        doc.status = "failed"
        doc.error_message = str(e)
        db.commit()
        db.refresh(doc)
        return to_project_document_view(doc, project)


@router.post("/{project_id}/documents/{document_id}/retry", response_model=ProjectDocumentView)
def retry_project_document(
    project_id: str,
    document_id: str,
    request: Optional[DocumentProcessRequest] = None,
    tenant: TenantContext = Depends(require_role(["admin", "audit_lead", "contributor"])),
    db: Session = Depends(get_db)
):
    """Reintenta el procesamiento de un documento en estado failed conservando su identidad."""
    proj_repo = ProjectRepository(db)
    project = proj_repo.get_by_id_and_organization(project_id, organization_id=tenant.organization.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proyecto no encontrado")

    doc_repo = DocumentRepository(db)
    doc = doc_repo.get_by_id(document_id)
    if not doc or doc.project_id != project_id or doc.organization_id != tenant.organization.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento no encontrado en este proyecto")

    # Limpiar láminas previas si hubiesen quedado incompletas
    doc_repo.delete_sheets_by_document(document_id)

    ingest_svc = IngestService(db)
    target_dpi = request.dpi if request else None
    try:
        updated_doc = ingest_svc.process_document(document_id=document_id, dpi=target_dpi)
        return to_project_document_view(updated_doc, project)
    except Exception as e:
        doc.status = "failed"
        doc.error_message = str(e)
        db.commit()
        db.refresh(doc)
        return to_project_document_view(doc, project)


@router.delete("/{project_id}/documents/{document_id}")
def delete_project_document(
    project_id: str,
    document_id: str,
    hard_delete: bool = Query(True, description="Eliminar físicamente registro y archivos"),
    tenant: TenantContext = Depends(require_role(["admin", "audit_lead", "contributor"])),
    db: Session = Depends(get_db)
):
    """Elimina un documento del proyecto y limpia sus hojas y archivos físicos asociados de forma segura."""
    proj_repo = ProjectRepository(db)
    project = proj_repo.get_by_id_and_organization(project_id, organization_id=tenant.organization.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proyecto no encontrado")

    doc_repo = DocumentRepository(db)
    doc = doc_repo.get_by_id(document_id)
    if not doc or doc.project_id != project_id or doc.organization_id != tenant.organization.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento no encontrado en este proyecto")

    user_id = tenant.user.id if hasattr(tenant, "user") and tenant.user else None
    if hard_delete:
        result = doc_repo.hard_delete_document(document_id=document_id, user_id=user_id)
        return {"success": True, "document_id": document_id, "message": "Documento y archivos eliminados exitosamente", "result": result}
    else:
        archived = doc_repo.soft_delete_document(document_id=document_id, user_id=user_id)
        return {"success": True, "document_id": document_id, "message": f"Documento '{archived.filename}' archivado exitosamente."}


@router.get("/{project_id}/documents/{document_id}/download")
def download_project_document(
    project_id: str,
    document_id: str,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Descarga de forma segura el archivo técnico original del documento."""
    proj_repo = ProjectRepository(db)
    project = proj_repo.get_by_id_and_organization(project_id, organization_id=tenant.organization.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proyecto no encontrado")

    doc_repo = DocumentRepository(db)
    doc = doc_repo.get_by_id(document_id)
    if not doc or doc.project_id != project_id or doc.organization_id != tenant.organization.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento no encontrado en este proyecto")

    if not doc.file_path or not os.path.exists(doc.file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archivo físico no encontrado en almacenamiento.")

    return FileResponse(
        doc.file_path,
        filename=doc.filename,
        media_type=doc.mime_type or "application/octet-stream"
    )

