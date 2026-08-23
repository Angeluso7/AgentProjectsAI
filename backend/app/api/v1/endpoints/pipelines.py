from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models.operations import ReviewPipelineRun, PipelineStageRun
from app.schemas.pipeline import (
    ReviewPipelineRunRead, PipelineStageRunRead, ReviewPipelineRunCreateRequest, PipelineActionResponse
)
from app.services.operations.pipeline_service import ReviewPipelineService
from app.services.operations.service import OperationsService
from app.db.repositories.document_repository import DocumentRepository
from app.core.deps import get_current_tenant, require_role, TenantContext

router = APIRouter()

@router.get("", response_model=List[ReviewPipelineRunRead])
def list_pipeline_runs(
    scope_type: Optional[str] = Query(None, description="document, sheet, project"),
    scope_id: Optional[str] = Query(None, description="ID del scope"),
    status_filter: Optional[str] = Query(None, alias="status", description="queued, running, completed, failed, awaiting_review"),
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Lista las ejecuciones históricas del pipeline One-Click dentro de la organización activa."""
    query = db.query(ReviewPipelineRun).filter(ReviewPipelineRun.organization_id == tenant.organization.id)
    if scope_type:
        query = query.filter(ReviewPipelineRun.scope_type == scope_type)
    if scope_id:
        query = query.filter(ReviewPipelineRun.scope_id == scope_id)
    if status_filter:
        query = query.filter(ReviewPipelineRun.status == status_filter)
    return query.order_by(ReviewPipelineRun.created_at.desc()).all()

@router.get("/{pipeline_run_id}", response_model=ReviewPipelineRunRead)
def get_pipeline_run(
    pipeline_run_id: str,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Obtiene el estado general, progreso y etapas de una corrida dentro de la organización activa."""
    p_run = db.query(ReviewPipelineRun).filter(
        ReviewPipelineRun.id == pipeline_run_id,
        ReviewPipelineRun.organization_id == tenant.organization.id
    ).first()
    if not p_run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Pipeline '{pipeline_run_id}' no encontrado.")
    return p_run

@router.get("/{pipeline_run_id}/stages", response_model=List[PipelineStageRunRead])
def get_pipeline_stages(
    pipeline_run_id: str,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Obtiene el detalle de las 8 etapas ejecutadas dentro del pipeline."""
    p_run = db.query(ReviewPipelineRun).filter(
        ReviewPipelineRun.id == pipeline_run_id,
        ReviewPipelineRun.organization_id == tenant.organization.id
    ).first()
    if not p_run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Pipeline '{pipeline_run_id}' no encontrado.")

    stages = db.query(PipelineStageRun).filter(
        PipelineStageRun.pipeline_run_id == pipeline_run_id
    ).order_by(PipelineStageRun.stage_order.asc()).all()
    return stages

@router.post("/documents/{document_id}/run", response_model=PipelineActionResponse, status_code=status.HTTP_202_ACCEPTED)
def run_document_pipeline_async(
    document_id: str,
    req: ReviewPipelineRunCreateRequest = ReviewPipelineRunCreateRequest(),
    tenant: TenantContext = Depends(require_role(["admin", "audit_lead", "contributor"])),
    db: Session = Depends(get_db)
):
    """Dispara la ejecución One-Click integral para un documento completo (HTTP 202 Accepted)."""
    doc_repo = DocumentRepository(db)
    doc = doc_repo.get_by_id(document_id)
    if not doc or doc.organization_id != tenant.organization.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Documento '{document_id}' no encontrado.")

    pipe_svc = ReviewPipelineService(db)
    try:
        pipeline_run = pipe_svc.create_pipeline_run(
            scope_type="document",
            scope_id=document_id,
            requested_by=tenant.user.email,
            force_reprocess=req.force_reprocess or False,
            organization_id=tenant.organization.id
        )
    except ValueError as ve:
        if "Existe un pipeline activo" in str(ve):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(ve))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))

    ops_svc = OperationsService(db)
    job = ops_svc.submit_job(
        job_type="document_pipeline_run",
        target_type="document",
        target_id=document_id,
        project_id=doc.project_id,
        input_payload={
            "pipeline_run_id": pipeline_run.id,
            "force_reprocess": req.force_reprocess,
            "organization_id": tenant.organization.id
        },
        requested_by=tenant.user.email,
        async_mode=True
    )

    return PipelineActionResponse(
        pipeline_run_id=pipeline_run.id,
        status="queued",
        current_stage="ingest",
        progress_percent=0,
        poll_url=f"/api/v1/pipelines/{pipeline_run.id}",
        message="Pipeline One-Click Review para documento iniciado exitosamente."
    )

@router.post("/sheets/{sheet_id}/run", response_model=PipelineActionResponse, status_code=status.HTTP_202_ACCEPTED)
def run_sheet_pipeline_async(
    sheet_id: str,
    req: ReviewPipelineRunCreateRequest = ReviewPipelineRunCreateRequest(),
    tenant: TenantContext = Depends(require_role(["admin", "audit_lead", "contributor"])),
    db: Session = Depends(get_db)
):
    """Dispara la ejecución One-Click integral para una lámina individual (HTTP 202 Accepted)."""
    doc_repo = DocumentRepository(db)
    sheet = doc_repo.get_sheet_by_id(sheet_id)
    if not sheet or (sheet.document and sheet.document.organization_id != tenant.organization.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lámina '{sheet_id}' no encontrada.")

    pipe_svc = ReviewPipelineService(db)
    try:
        pipeline_run = pipe_svc.create_pipeline_run(
            scope_type="sheet",
            scope_id=sheet_id,
            requested_by=tenant.user.email,
            force_reprocess=req.force_reprocess or False,
            organization_id=tenant.organization.id
        )
    except ValueError as ve:
        if "Existe un pipeline activo" in str(ve):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(ve))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))

    ops_svc = OperationsService(db)
    job = ops_svc.submit_job(
        job_type="sheet_pipeline_run",
        target_type="sheet",
        target_id=sheet_id,
        project_id=sheet.document.project_id if sheet.document else None,
        input_payload={
            "pipeline_run_id": pipeline_run.id,
            "force_reprocess": req.force_reprocess,
            "organization_id": tenant.organization.id
        },
        requested_by=tenant.user.email,
        async_mode=True
    )

    return PipelineActionResponse(
        pipeline_run_id=pipeline_run.id,
        status="queued",
        current_stage="ingest",
        progress_percent=0,
        poll_url=f"/api/v1/pipelines/{pipeline_run.id}",
        message="Pipeline One-Click Review para lámina iniciado exitosamente."
    )

@router.post("/{pipeline_run_id}/retry", response_model=PipelineActionResponse)
def retry_pipeline_run(
    pipeline_run_id: str,
    tenant: TenantContext = Depends(require_role(["admin", "audit_lead"])),
    db: Session = Depends(get_db)
):
    """Reintenta la ejecución de un pipeline fallido o pausado (Admin o Audit Lead)."""
    pipe_svc = ReviewPipelineService(db)
    p_run = pipe_svc.get_pipeline_run(pipeline_run_id)
    if not p_run or p_run.organization_id != tenant.organization.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline no encontrado.")

    try:
        p_res = pipe_svc.retry_pipeline(pipeline_run_id)
        return PipelineActionResponse(
            pipeline_run_id=p_res.id,
            status=p_res.status,
            current_stage=p_res.current_stage,
            progress_percent=p_res.progress_percent,
            poll_url=f"/api/v1/pipelines/{p_res.id}",
            message="Reintento de pipeline ejecutado."
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))

@router.post("/{pipeline_run_id}/cancel", response_model=PipelineActionResponse)
def cancel_pipeline_run(
    pipeline_run_id: str,
    tenant: TenantContext = Depends(require_role(["admin", "audit_lead"])),
    db: Session = Depends(get_db)
):
    """Cancela una ejecución activa del pipeline (Admin o Audit Lead)."""
    pipe_svc = ReviewPipelineService(db)
    p_run = pipe_svc.get_pipeline_run(pipeline_run_id)
    if not p_run or p_run.organization_id != tenant.organization.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline no encontrado.")

    p_res = pipe_svc.cancel_pipeline(pipeline_run_id)
    return PipelineActionResponse(
        pipeline_run_id=p_res.id,
        status="cancelled",
        current_stage=p_res.current_stage,
        progress_percent=p_res.progress_percent,
        poll_url=f"/api/v1/pipelines/{p_res.id}",
        message="Pipeline cancelado exitosamente."
    )
