import os
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import FileResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models.core import Project
from app.db.models.decision_memory import ReviewRun, ReviewReport, ReviewRunDocument, ReviewDiscipline, ReviewTopic
from app.services.review.taxonomy_service import TaxonomyService
from app.services.review.orchestrator import ReviewOrchestrator
from app.services.review.export_service import ReviewExportService
from app.db.models.document_memory import DetectedSymbol
from app.services.symbols.symbol_inventory_service import SymbolInventoryService
from app.schemas.review_orchestration import (
    ReviewDisciplineResponse,
    ReviewTopicResponse,
    ReviewPlanRequest,
    ReviewPlanResponse,
    ReviewRunCreateRequest,
    ReviewRunExecuteResponse,
    ReviewRunDetailsResponse,
    ReviewExportCreateRequest,
    ReviewReportResponse,
    SymbolOccurrenceSummary,
    SymbolInventoryGroupResponse,
    SymbolInventoryMetricsResponse,
    SymbolInventoryResponse,
    DeleteReviewRunResponse,
    ClearReviewRunsResponse
)
from app.core.deps import get_current_tenant, require_role, TenantContext
from app.core.logging import logger

router = APIRouter()


@router.get("/disciplines", response_model=List[ReviewDisciplineResponse])
def get_review_disciplines(
    active_only: bool = Query(True, description="Filtrar solo disciplinas activas"),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_current_tenant)
):
    """Retorna el catálogo canónico de especialidades/disciplinas de ingeniería."""
    return TaxonomyService.get_disciplines(db=db, active_only=active_only)


@router.get("/topics", response_model=List[ReviewTopicResponse])
def get_review_topics(
    discipline_code: Optional[str] = Query(None, description="Filtrar por código de disciplina (incluye transversales)"),
    active_only: bool = Query(True, description="Filtrar solo temas activos"),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_current_tenant)
):
    """Retorna los puntos o temas de revisión técnica disponibles."""
    return TaxonomyService.get_topics(db=db, discipline_code=discipline_code, active_only=active_only)


@router.post("/plan", response_model=ReviewPlanResponse)
def get_review_plan(
    payload: ReviewPlanRequest,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_current_tenant)
):
    """
    Genera el pre-flight plan explicativo: reglas aplicables, reglas no aprobadas,
    fases de ejecución, dependencias y documentos requeridos faltantes.
    """
    try:
        plan = ReviewOrchestrator.generate_review_plan(
            db=db,
            project_id=payload.project_id,
            discipline_code=payload.discipline_code,
            topic_code=payload.topic_code,
            document_ids=payload.document_ids,
            mode=payload.mode
        )
        return plan
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.error(f"Error generando plan de revisión: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno generando plan.")


@router.post("/runs", response_model=ReviewRunExecuteResponse, status_code=status.HTTP_201_CREATED)
def execute_review_run(
    payload: ReviewRunCreateRequest,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_current_tenant)
):
    """
    Ejecuta una corrida de auditoría por especialidad y punto de revisión:
    - Fases 1 a 4: preparación técnica de datos (no generan hallazgos QA/QC).
    - Fases 5 a 8: evaluación de reglas determinísticas QA/QC.
    - Fase 9: consolidación y reporte persistido.
    """
    try:
        user_id = getattr(tenant.user, "email", "auditor_qa") if tenant.user else "auditor_qa"
        result = ReviewOrchestrator.execute_review_run(
            db=db,
            project_id=payload.project_id,
            discipline_code=payload.discipline_code,
            topic_code=payload.topic_code,
            document_ids=payload.document_ids,
            mode=payload.mode,
            requested_by=user_id,
            run_name=payload.run_name
        )
        return result
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.error(f"Error ejecutando corrida de revisión: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error en ejecución: {str(e)}")


@router.get("/runs/{run_id}", response_model=ReviewRunDetailsResponse)
def get_review_run_details(
    run_id: str,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_current_tenant)
):
    """Retorna el detalle completo de una corrida: pasos, ejecuciones, estado estructurado y hallazgos."""
    details = ReviewOrchestrator.get_review_run_details(db=db, review_run_id=run_id)
    if not details:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Corrida '{run_id}' no encontrada.")
    
    # Aislamiento multi-tenant estricto
    if tenant and tenant.organization:
        proj_id = details.get("project_id") if isinstance(details, dict) else getattr(details, "project_id", None)
        project = db.query(Project).filter(Project.id == proj_id).first()
        if project and project.organization_id != tenant.organization.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No autorizado para acceder a corridas de otra organización."
            )
    return details


@router.get("/runs/{run_id}/symbol-inventory", response_model=SymbolInventoryResponse)
def get_run_symbol_inventory(
    run_id: str,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_current_tenant)
):
    """Retorna el inventario consolidado de simbología (Tabla 1) y sus métricas."""
    run = db.query(ReviewRun).filter(ReviewRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Corrida '{run_id}' no encontrada.")

    if tenant and tenant.organization and run.organization_id != tenant.organization.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No autorizado para acceder a corridas de otra organización."
        )

    return SymbolInventoryService.format_run_inventory(db, run)


@router.post("/runs/{run_id}/symbol-inventory/regenerate", response_model=SymbolInventoryResponse)
def regenerate_run_symbol_inventory(
    run_id: str,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_current_tenant)
):
    """
    Regenera de forma controlada e idempotente el inventario de simbología para una corrida de revisión.
    No permite ejecución en corridas pending/running.
    Si los datos fuente y versión del algoritmo no cambiaron y el inventario ya existe, es idempotente.
    Registra audit trail, versión y timestamp de recálculo.
    """
    run = db.query(ReviewRun).filter(ReviewRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Corrida '{run_id}' no encontrada.")

    if tenant and tenant.organization and run.organization_id != tenant.organization.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No autorizado para regenerar inventario de otra organización."
        )

    if run.status in ["pending", "running"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede regenerar el inventario mientras la corrida de revisión esté en ejecución."
        )

    has_docs = db.query(ReviewRunDocument).filter(
        ReviewRunDocument.review_run_id == run.id,
        ReviewRunDocument.status == "included"
    ).count() > 0

    if not has_docs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La corrida no contiene documentos válidos para regenerar el inventario."
        )

    current_source_hash = SymbolInventoryService.compute_source_snapshot_hash(db, run)
    run_summary = dict(run.summary or {})
    inv_meta = run_summary.get("symbol_inventory_meta", {})
    existing_hash = inv_meta.get("inventory_source_snapshot_hash")

    # Idempotencia: si el snapshot no cambió y ya se completó el inventario
    if existing_hash == current_source_hash and inv_meta.get("inventory_build_completed") is True:
        logger.info(f"Inventario para run {run.id} ya está actualizado con snapshot {current_source_hash}.")
        return SymbolInventoryService.format_run_inventory(db, run)

    user_name = getattr(tenant.user, "email", None) or getattr(tenant.user, "username", None) or "user"
    SymbolInventoryService.build_run_inventory(
        db=db,
        review_run=run,
        force_rebuild=True,
        requested_by=user_name
    )

    return SymbolInventoryService.format_run_inventory(db, run)


@router.get("/runs/{run_id}/symbol-inventory/groups/{group_id}/occurrences", response_model=List[SymbolOccurrenceSummary])
def get_run_symbol_group_occurrences(
    run_id: str,
    group_id: str,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_current_tenant)
):
    """Retorna la lista de ocurrencias detalladas con doble crop para un grupo de inventario (Tabla 2)."""
    run = db.query(ReviewRun).filter(ReviewRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Corrida '{run_id}' no encontrada.")

    if tenant and tenant.organization and run.organization_id != tenant.organization.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No autorizado para acceder a corridas de otra organización."
        )

    return SymbolInventoryService.get_group_occurrences_summary(db, group_id)


@router.get("/runs", response_model=List[ReviewRunDetailsResponse])
def list_review_runs(
    project_id: str = Query(..., description="ID del proyecto"),
    discipline_code: Optional[str] = Query(None, description="Filtrar por especialidad"),
    topic_code: Optional[str] = Query(None, description="Filtrar por punto de revisión"),
    limit: int = Query(20, description="Límite de corridas a listar"),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_current_tenant)
):
    """Lista las últimas corridas de auditoría ejecutadas para un proyecto, ordenadas descendentemente por fecha/hora solicitada exacta."""
    # Validar acceso al proyecto
    if tenant and tenant.organization:
        proj = db.query(Project).filter(Project.id == project_id).first()
        if proj and proj.organization_id != tenant.organization.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No autorizado para acceder a proyectos de otra organización."
            )

    q = db.query(ReviewRun).filter(ReviewRun.project_id == project_id)
    if discipline_code:
        disc = db.query(ReviewDiscipline).filter(ReviewDiscipline.code == discipline_code).first()
        if disc:
            q = q.filter(ReviewRun.discipline_id == disc.id)
    if topic_code:
        top = db.query(ReviewTopic).filter(ReviewTopic.code == topic_code).first()
        if top:
            q = q.filter(ReviewRun.topic_id == top.id)

    runs = q.order_by(
        func.coalesce(ReviewRun.requested_at, ReviewRun.created_at).desc(),
        ReviewRun.created_at.desc()
    ).limit(limit).all()

    results = []
    for r in runs:
        det = ReviewOrchestrator.get_review_run_details(db=db, review_run_id=r.id)
        if det:
            results.append(det)
    return results


@router.delete("/runs/{run_id}", response_model=DeleteReviewRunResponse)
def delete_review_run(
    run_id: str,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_role(["admin", "audit_lead", "reviewer"]))
):
    """Elimina una corrida de auditoría individual y todas sus entidades hijas asociadas."""
    run = db.query(ReviewRun).filter(ReviewRun.id == run_id).first()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Corrida de auditoría '{run_id}' no encontrada."
        )

    if tenant and tenant.organization:
        proj = db.query(Project).filter(Project.id == run.project_id).first()
        if proj and proj.organization_id != tenant.organization.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No autorizado para eliminar corridas de otra organización."
            )

    ReviewOrchestrator.delete_review_run(db, run_id)
    return DeleteReviewRunResponse(
        message="Corrida de revisión eliminada exitosamente.",
        deleted_run_id=run_id
    )


@router.delete("/runs", response_model=ClearReviewRunsResponse)
def clear_review_runs(
    project_id: str = Query(..., description="ID del proyecto"),
    discipline_code: Optional[str] = Query(None, description="Filtrar por especialidad"),
    topic_code: Optional[str] = Query(None, description="Filtrar por punto de revisión"),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_role(["admin", "audit_lead", "reviewer"]))
):
    """Limpia en bloque el historial de auditorías para un proyecto o alcance específico."""
    if tenant and tenant.organization:
        proj = db.query(Project).filter(Project.id == project_id).first()
        if proj and proj.organization_id != tenant.organization.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No autorizado para modificar proyectos de otra organización."
            )

    deleted_count = ReviewOrchestrator.clear_review_runs(
        db=db,
        project_id=project_id,
        discipline_code=discipline_code,
        topic_code=topic_code
    )

    return ClearReviewRunsResponse(
        message=f"Se eliminaron {deleted_count} corridas de revisión exitosamente.",
        deleted_count=deleted_count
    )


@router.post("/runs/{run_id}/exports", response_model=ReviewReportResponse, status_code=status.HTTP_201_CREATED)
def create_run_export(
    run_id: str,
    payload: ReviewExportCreateRequest,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_current_tenant)
):
    """Genera y persiste un reporte físico (JSON, XLSX o PDF) para una corrida de revisión."""
    run = db.query(ReviewRun).filter(ReviewRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Corrida '{run_id}' no encontrada.")

    # Validar pertenencia de organización
    if tenant and tenant.organization and run.project:
        if run.project.organization_id != tenant.organization.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No autorizado para generar exportaciones de otra organización."
            )

    try:
        report = ReviewExportService.create_report(db=db, review_run_id=run_id, export_format=payload.format)
        return report
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.error(f"Error generando reporte exportable: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error generando exportación: {str(e)}")


@router.get("/reports/{report_id}", response_model=ReviewReportResponse)
def get_review_report_metadata(
    report_id: str,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_current_tenant)
):
    """Retorna los metadatos y hash SHA-256 del reporte persistido."""
    report = ReviewExportService.get_report(db=db, report_id=report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Reporte '{report_id}' no encontrado.")
    
    if tenant and tenant.organization and report.organization_id != tenant.organization.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No autorizado para acceder a reportes de otra organización."
        )
    return report


@router.get("/reports/{report_id}/download")
def download_review_report(
    report_id: str,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_current_tenant)
):
    """Descarga el artefacto físico del reporte persistido con verificación de integridad y aislamiento tenant."""
    report = ReviewExportService.get_report(db=db, report_id=report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Reporte '{report_id}' no encontrado.")

    # Aislamiento multi-tenant estricto
    if tenant and tenant.organization and report.organization_id != tenant.organization.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No autorizado para acceder a reportes de otra organización."
        )

    try:
        file_path, filename, media_type = ReviewExportService.get_report_file(db=db, report_id=report_id)
        if not os.path.exists(file_path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archivo físico de reporte no encontrado en el servidor.")

        file_size = os.path.getsize(file_path)
        headers = {
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(file_size),
            "X-Report-SHA256": report.sha256 if report else ""
        }
        return FileResponse(path=file_path, filename=filename, media_type=media_type, headers=headers)
    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except FileNotFoundError as fe:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(fe))
    except Exception as e:
        logger.error(f"Error descargando reporte: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error en descarga del reporte.")
