import os
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.deps import get_current_tenant, require_role, TenantContext
from app.services.reporting.consolidated_service import ConsolidatedReportService
from app.schemas.consolidated_report import (
    ConsolidatedStageReportRead, EmitStageReportRequest, ProjectStageReportSnapshotSummary
)
from app.db.models.reporting import ProjectStageReportSnapshot
from app.db.models.core import Project

router = APIRouter()

def _snapshot_to_read_dto(snap: ProjectStageReportSnapshot, project: Optional[Project] = None) -> ConsolidatedStageReportRead:
    proj_name = project.name if project else "Proyecto"
    proj_code = project.code if project else "PRJ"

    return ConsolidatedStageReportRead(
        id=snap.id,
        project_id=snap.project_id,
        project_name=proj_name,
        project_code=proj_code,
        stage=snap.stage,
        revision_number=snap.revision_number,
        title=snap.title,
        global_stage_verdict=snap.global_stage_verdict,
        verdict_rationale=snap.verdict_rationale,
        issued_by=snap.issued_by,
        issued_at=snap.created_at,
        completeness=snap.completeness_summary,
        audit_verdicts=snap.audit_verdicts_summary,
        observations=snap.observations_summary,
        delta_evolution=snap.delta_evolution_summary,
        artifact_pdf_path=snap.artifact_pdf_path,
        artifact_json_path=snap.artifact_json_path,
        manifest_hash=snap.manifest_hash,
        is_live_preview=False
    )

@router.get("/preview", response_model=ConsolidatedStageReportRead)
def preview_consolidated_report(
    project_id: str = Query(...),
    stage: Optional[str] = Query(None),
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Genera la vista previa en vivo del reporte consolidado sin persistir snapshot."""
    svc = ConsolidatedReportService(db)
    try:
        data = svc.build_consolidated_data(project_id, stage)
        return ConsolidatedStageReportRead(**data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@router.post("/emit", response_model=ConsolidatedStageReportRead)
def emit_stage_snapshot(
    payload: EmitStageReportRequest,
    tenant: TenantContext = Depends(require_role(["admin", "audit_lead", "reviewer"])),
    db: Session = Depends(get_db)
):
    """Genera, exporta en JSON/PDF y persiste un Snapshot inmutable de cierre de etapa."""
    svc = ConsolidatedReportService(db)
    try:
        snapshot = svc.emit_stage_snapshot(
            project_id=payload.project_id,
            stage_override=payload.stage,
            title_override=payload.title,
            notes=payload.notes,
            author=tenant.user.display_name or tenant.user.email
        )
        project = db.query(Project).filter(Project.id == snapshot.project_id).first()
        return _snapshot_to_read_dto(snapshot, project)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@router.get("/snapshots", response_model=List[ProjectStageReportSnapshotSummary])
def list_stage_snapshots(
    project_id: str = Query(...),
    stage: Optional[str] = Query(None),
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Lista todos los snapshots y cortes históricos emitidos para un proyecto y etapa."""
    svc = ConsolidatedReportService(db)
    snapshots = svc.list_snapshots(project_id, stage)
    summaries = []
    for s in snapshots:
        comp = s.completeness_summary or {}
        obs = s.observations_summary or {}
        summaries.append(ProjectStageReportSnapshotSummary(
            id=s.id,
            project_id=s.project_id,
            stage=s.stage,
            revision_number=s.revision_number,
            title=s.title,
            global_stage_verdict=s.global_stage_verdict,
            completeness_percentage=comp.get("completeness_percentage", 0.0),
            open_obs_count=obs.get("open_obs", 0),
            open_rfi_count=obs.get("open_rfi", 0),
            active_blk_count=obs.get("active_blk", 0),
            issued_by=s.issued_by,
            created_at=s.created_at
        ))
    return summaries

@router.get("/snapshots/{snapshot_id}", response_model=ConsolidatedStageReportRead)
def get_stage_snapshot(
    snapshot_id: str,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Obtiene el detalle completo de un snapshot persistido."""
    svc = ConsolidatedReportService(db)
    snapshot = svc.get_snapshot_by_id(snapshot_id)
    if not snapshot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Snapshot '{snapshot_id}' no encontrado.")
    project = db.query(Project).filter(Project.id == snapshot.project_id).first()
    return _snapshot_to_read_dto(snapshot, project)

@router.get("/snapshots/{snapshot_id}/download/pdf")
def download_snapshot_pdf(
    snapshot_id: str,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Descarga el documento PDF vectorial generado para el snapshot."""
    svc = ConsolidatedReportService(db)
    snapshot = svc.get_snapshot_by_id(snapshot_id)
    if not snapshot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Snapshot '{snapshot_id}' no encontrado.")

    if not snapshot.artifact_pdf_path or not os.path.exists(snapshot.artifact_pdf_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El archivo PDF de este snapshot no se encuentra disponible.")

    filename = os.path.basename(snapshot.artifact_pdf_path)
    return FileResponse(
        path=snapshot.artifact_pdf_path,
        media_type="application/pdf",
        filename=filename
    )

@router.get("/snapshots/{snapshot_id}/download/json")
def download_snapshot_json(
    snapshot_id: str,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Descarga el archivo JSON estructurado con el manifiesto SHA-256 del snapshot."""
    svc = ConsolidatedReportService(db)
    snapshot = svc.get_snapshot_by_id(snapshot_id)
    if not snapshot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Snapshot '{snapshot_id}' no encontrado.")

    if not snapshot.artifact_json_path or not os.path.exists(snapshot.artifact_json_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El archivo JSON de este snapshot no se encuentra disponible.")

    filename = os.path.basename(snapshot.artifact_json_path)
    return FileResponse(
        path=snapshot.artifact_json_path,
        media_type="application/json",
        filename=filename
    )
