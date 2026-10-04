from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.deps import get_current_tenant, require_role, TenantContext
from app.services.completeness.service import CompletenessService
from app.schemas.completeness import (
    DeliverableRequirementRead, DocumentDeliverableRead,
    ClassifyDocumentDeliverableRequest, UpdateDocumentReadinessRequest,
    ProjectCompletenessEvaluationRead
)
from app.db.models.completeness import DocumentDeliverable, ProjectDeliverableRequirement
from app.db.models.document_memory import Document

router = APIRouter()

@router.get("/requirements", response_model=List[DeliverableRequirementRead])
def get_requirements(
    stage: Optional[str] = Query(None, description="Ingeniería Básica, Ingeniería de Detalle"),
    discipline: Optional[str] = Query(None, description="architecture, structural, etc."),
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Lista los requisitos de entregables por etapa y disciplina."""
    service = CompletenessService(db)
    return service.get_requirements(stage=stage, discipline=discipline)

@router.get("/projects/{project_id}")
def get_project_completeness(
    project_id: str,
    stage: Optional[str] = Query(None, description="Override de etapa para evaluar"),
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Obtiene el estado de completitud documental, matriz de entregables y bloqueos del proyecto."""
    service = CompletenessService(db)
    try:
        return service.evaluate_project_completeness(project_id=project_id, stage_override=stage)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@router.post("/projects/{project_id}/evaluate")
def evaluate_project_completeness(
    project_id: str,
    stage: Optional[str] = Query(None, description="Override de etapa"),
    tenant: TenantContext = Depends(require_role(["admin", "audit_lead", "reviewer"])),
    db: Session = Depends(get_db)
):
    """Ejecuta y persiste el chequeo de completitud documental (Gatekeeper) para el proyecto."""
    service = CompletenessService(db)
    try:
        return service.evaluate_project_completeness(project_id=project_id, stage_override=stage)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@router.post("/documents/{document_id}/classify", response_model=DocumentDeliverableRead)
def classify_document(
    document_id: str,
    payload: ClassifyDocumentDeliverableRequest,
    tenant: TenantContext = Depends(require_role(["admin", "audit_lead", "reviewer"])),
    db: Session = Depends(get_db)
):
    """Clasifica un documento en su tipo de entregable y define su estado de evidencia."""
    service = CompletenessService(db)
    try:
        deliv = service.classify_document_deliverable(
            document_id=document_id,
            deliverable_type=payload.deliverable_type.value if hasattr(payload.deliverable_type, "value") else str(payload.deliverable_type),
            readiness_status=payload.readiness_status.value if payload.readiness_status and hasattr(payload.readiness_status, "value") else (str(payload.readiness_status) if payload.readiness_status else "classified"),
            validation_notes=payload.validation_notes,
            classified_by=tenant.user.display_name or tenant.user.email
        )
        doc = db.query(Document).filter(Document.id == document_id).first()
        return DocumentDeliverableRead(
            id=deliv.id,
            project_id=deliv.project_id,
            document_id=deliv.document_id,
            deliverable_type=deliv.deliverable_type,
            readiness_status=deliv.readiness_status,
            validation_notes=deliv.validation_notes,
            classified_by=deliv.classified_by,
            validated_at=deliv.validated_at,
            document_filename=doc.filename if doc else None,
            document_title=doc.filename if doc else None,
            created_at=deliv.created_at,
            updated_at=deliv.updated_at
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@router.put("/documents/{document_id}/readiness", response_model=DocumentDeliverableRead)
def update_document_readiness(
    document_id: str,
    payload: UpdateDocumentReadinessRequest,
    tenant: TenantContext = Depends(require_role(["admin", "audit_lead", "reviewer"])),
    db: Session = Depends(get_db)
):
    """Actualiza el estado de evidencia de un documento (uploaded, classified, validated, eligible_as_evidence, rejected)."""
    service = CompletenessService(db)
    deliv = db.query(DocumentDeliverable).filter(DocumentDeliverable.document_id == document_id).first()
    deliv_type = deliv.deliverable_type if deliv else "plano_general"
    
    try:
        updated = service.classify_document_deliverable(
            document_id=document_id,
            deliverable_type=deliv_type,
            readiness_status=payload.readiness_status.value if hasattr(payload.readiness_status, "value") else str(payload.readiness_status),
            validation_notes=payload.validation_notes,
            classified_by=tenant.user.display_name or tenant.user.email
        )
        doc = db.query(Document).filter(Document.id == document_id).first()
        return DocumentDeliverableRead(
            id=updated.id,
            project_id=updated.project_id,
            document_id=updated.document_id,
            deliverable_type=updated.deliverable_type,
            readiness_status=updated.readiness_status,
            validation_notes=updated.validation_notes,
            classified_by=updated.classified_by,
            validated_at=updated.validated_at,
            document_filename=doc.filename if doc else None,
            document_title=doc.filename if doc else None,
            created_at=updated.created_at,
            updated_at=updated.updated_at
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
