import os
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models.reporting import AuditReport
from app.schemas.report import (
    AuditReportRead, EvidenceManifestRead, AuditReportCreateRequest
)
from app.schemas.operations import AsyncJobAcceptedResponse
from app.services.reporting.service import ReportingService
from app.services.operations.service import OperationsService
from app.db.repositories.document_repository import DocumentRepository
from app.core.config import settings
from app.core.deps import get_current_tenant, require_role, TenantContext

router = APIRouter()

@router.get("", response_model=List[AuditReportRead])
def list_reports(
    document_id: Optional[str] = Query(None, description="Filtrar por documento"),
    sheet_id: Optional[str] = Query(None, description="Filtrar por lámina"),
    report_type: Optional[str] = Query(None, description="technical_audit_qaqc, normative_compliance_matrix, etc."),
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Lista todos los reportes técnicos de auditoría generados en la organización activa."""
    svc = ReportingService(db)
    return svc.list_reports(
        organization_id=tenant.organization.id,
        document_id=document_id,
        sheet_id=sheet_id,
        report_type=report_type
    )

@router.get("/{report_id}", response_model=AuditReportRead)
def get_report(
    report_id: str,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Obtiene el detalle y resumen estructurado de un reporte de auditoría dentro de la organización activa."""
    svc = ReportingService(db)
    rep = svc.get_report(report_id, organization_id=tenant.organization.id)
    if not rep:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Reporte '{report_id}' no encontrado.")
    return rep

@router.get("/{report_id}/manifest", response_model=EvidenceManifestRead)
def get_report_manifest(
    report_id: str,
    tenant: TenantContext = Depends(require_role(["admin", "audit_lead", "reviewer"])),
    db: Session = Depends(get_db)
):
    """Obtiene el manifiesto de integridad basado en hashes SHA-256 de las evidencias (Solo Admin, Audit Lead, Reviewer)."""
    svc = ReportingService(db)
    manifest = svc.get_manifest(report_id, organization_id=tenant.organization.id)
    if not manifest:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Manifiesto para el reporte '{report_id}' no encontrado.")
    return manifest

@router.get("/{report_id}/download/pdf")
def download_report_pdf(
    report_id: str,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Descarga el informe técnico en formato PDF estándar."""
    svc = ReportingService(db)
    rep = svc.get_report(report_id, organization_id=tenant.organization.id)
    if not rep or not rep.artifact_pdf_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archivo PDF no disponible.")
    
    # Política de Artefactos: Viewer no puede descargar PDF si no tiene rol de visualización activa
    abs_path = os.path.join(settings.BASE_DIR, rep.artifact_pdf_path)
    if not os.path.exists(abs_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El archivo PDF no existe en disco.")
    
    return FileResponse(
        abs_path,
        media_type="application/pdf",
        filename=f"auditoria_{rep.sheet_id or rep.document_id}_{report_id[:8]}.pdf"
    )

@router.get("/{report_id}/download/json")
def download_report_json(
    report_id: str,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Descarga la auditoría estructurada en formato JSON."""
    svc = ReportingService(db)
    rep = svc.get_report(report_id, organization_id=tenant.organization.id)
    if not rep or not rep.artifact_json_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archivo JSON no disponible.")
    
    abs_path = os.path.join(settings.BASE_DIR, rep.artifact_json_path)
    if not os.path.exists(abs_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El archivo JSON no existe en disco.")
    
    return FileResponse(
        abs_path,
        media_type="application/json",
        filename=f"auditoria_{rep.sheet_id or rep.document_id}_{report_id[:8]}.json"
    )

@router.get("/{report_id}/download/bundle")
def download_report_bundle(
    report_id: str,
    tenant: TenantContext = Depends(require_role(["admin", "audit_lead", "reviewer"])),
    db: Session = Depends(get_db)
):
    """Descarga el paquete completo de evidencia con manifiesto de integridad (ZIP) (Admin, Audit Lead, Reviewer)."""
    svc = ReportingService(db)
    rep = svc.get_report(report_id, organization_id=tenant.organization.id)
    if not rep or not rep.artifact_bundle_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paquete ZIP no disponible.")
    
    abs_path = os.path.join(settings.BASE_DIR, rep.artifact_bundle_path)
    if not os.path.exists(abs_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El archivo ZIP no existe en disco.")
    
    return FileResponse(
        abs_path,
        media_type="application/zip",
        filename=f"evidencias_auditoria_{report_id[:8]}.zip"
    )

@router.post("/sheets/{sheet_id}", response_model=AuditReportRead)
def generate_sheet_report_sync(
    sheet_id: str,
    req: AuditReportCreateRequest = AuditReportCreateRequest(),
    tenant: TenantContext = Depends(require_role(["admin", "audit_lead"])),
    db: Session = Depends(get_db)
):
    """Genera síncronamente el reporte técnico de auditoría de una lámina."""
    doc_repo = DocumentRepository(db)
    sheet = doc_repo.get_sheet_by_id(sheet_id)
    if not sheet or (sheet.document and sheet.document.organization_id and sheet.document.organization_id != tenant.organization.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lámina '{sheet_id}' no encontrada.")

    svc = ReportingService(db)
    try:
        return svc.generate_sheet_report(
            sheet_id=sheet_id,
            report_type=req.report_type or "technical_audit_qaqc",
            generated_by=req.generated_by or tenant.user.email
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error generando reporte: {str(e)}")

@router.post("/sheets/{sheet_id}/async", response_model=AsyncJobAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
def generate_sheet_report_async(
    sheet_id: str,
    req: AuditReportCreateRequest = AuditReportCreateRequest(),
    tenant: TenantContext = Depends(require_role(["admin", "audit_lead"])),
    db: Session = Depends(get_db)
):
    """Encola asíncronamente la generación del reporte técnico de una lámina (HTTP 202 Accepted)."""
    doc_repo = DocumentRepository(db)
    sheet = doc_repo.get_sheet_by_id(sheet_id)
    if not sheet or (sheet.document and sheet.document.organization_id and sheet.document.organization_id != tenant.organization.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lámina '{sheet_id}' no encontrada.")

    ops_svc = OperationsService(db)
    job = ops_svc.submit_job(
        job_type="sheet_report_generate",
        target_type="sheet",
        target_id=sheet_id,
        project_id=sheet.document.project_id if sheet.document else None,
        input_payload={
            "report_type": req.report_type or "technical_audit_qaqc",
            "generated_by": req.generated_by or tenant.user.email,
            "organization_id": tenant.organization.id
        },
        requested_by=tenant.user.email,
        async_mode=True
    )

    return AsyncJobAcceptedResponse(
        job_id=job.id,
        status="queued",
        target_id=sheet_id,
        target_type="sheet",
        poll_url=f"/api/v1/jobs/{job.id}",
        message="Generación de reporte técnico de lámina encolada exitosamente."
    )

@router.post("/documents/{document_id}/async", response_model=AsyncJobAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
def generate_document_report_async(
    document_id: str,
    req: AuditReportCreateRequest = AuditReportCreateRequest(),
    tenant: TenantContext = Depends(require_role(["admin", "audit_lead"])),
    db: Session = Depends(get_db)
):
    """Encola asíncronamente la generación del reporte consolidado de documento (HTTP 202 Accepted)."""
    doc_repo = DocumentRepository(db)
    doc = doc_repo.get_by_id(document_id)
    if not doc or (doc.organization_id and doc.organization_id != tenant.organization.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Documento '{document_id}' no encontrado.")

    ops_svc = OperationsService(db)
    job = ops_svc.submit_job(
        job_type="document_report_generate",
        target_type="document",
        target_id=document_id,
        project_id=doc.project_id,
        input_payload={
            "report_type": req.report_type or "technical_audit_qaqc",
            "generated_by": req.generated_by or tenant.user.email,
            "organization_id": tenant.organization.id
        },
        requested_by=tenant.user.email,
        async_mode=True
    )

    return AsyncJobAcceptedResponse(
        job_id=job.id,
        status="queued",
        target_id=document_id,
        target_type="document",
        poll_url=f"/api/v1/jobs/{job.id}",
        message="Generación de reporte consolidado de documento encolada exitosamente."
    )
