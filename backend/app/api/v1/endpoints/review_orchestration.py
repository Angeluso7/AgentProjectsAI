import os
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models.decision_memory import ReviewRun, ReviewReport
from app.services.review.taxonomy_service import TaxonomyService
from app.services.review.orchestrator import ReviewOrchestrator
from app.services.review.export_service import ReviewExportService
from app.schemas.review_orchestration import (
    ReviewDisciplineResponse,
    ReviewTopicResponse,
    ReviewPlanRequest,
    ReviewPlanResponse,
    ReviewRunCreateRequest,
    ReviewRunExecuteResponse,
    ReviewRunDetailsResponse,
    ReviewExportCreateRequest,
    ReviewReportResponse
)
from app.core.deps import get_current_tenant, TenantContext
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
    return details


@router.get("/runs", response_model=List[ReviewRunDetailsResponse])
def list_review_runs(
    project_id: str = Query(..., description="ID del proyecto"),
    limit: int = Query(20, description="Límite de corridas a listar"),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_current_tenant)
):
    """Lista las últimas corridas de auditoría ejecutadas para un proyecto."""
    runs = db.query(ReviewRun).filter(
        ReviewRun.project_id == project_id
    ).order_by(ReviewRun.created_at.desc()).limit(limit).all()

    results = []
    for r in runs:
        det = ReviewOrchestrator.get_review_run_details(db=db, review_run_id=r.id)
        if det:
            results.append(det)
    return results


@router.post("/runs/{run_id}/exports", response_model=ReviewReportResponse, status_code=status.HTTP_201_CREATED)
def create_run_export(
    run_id: str,
    payload: ReviewExportCreateRequest,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_current_tenant)
):
    """Genera y persiste un reporte físico (JSON, XLSX o PDF) para una corrida de revisión."""
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
    return report


@router.get("/reports/{report_id}/download")
def download_review_report(
    report_id: str,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_current_tenant)
):
    """Descarga el artefacto físico del reporte persistido con verificación de integridad."""
    try:
        file_path, filename, media_type = ReviewExportService.get_report_file(db=db, report_id=report_id)
        report = ReviewExportService.get_report(db=db, report_id=report_id)
        headers = {
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Report-SHA256": report.sha256 if report else ""
        }
        return FileResponse(path=file_path, filename=filename, media_type=media_type, headers=headers)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except FileNotFoundError as fe:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(fe))
    except Exception as e:
        logger.error(f"Error descargando reporte: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error en descarga del reporte.")
