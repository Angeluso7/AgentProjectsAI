from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.deps import get_current_tenant, require_role, TenantContext
from app.services.observations.service import ObservationService
from app.schemas.observations import (
    AuditObservationRead, GenerateObservationsRequest,
    IssueObservationRequest, ObservationResponseCreate,
    ProvisionEvidenceRequest, DeltaReevaluationResponse,
    ReopenObservationRequest
)
from app.db.models.observations import AuditObservation
from app.db.models.document_memory import Document, DocumentSheet

router = APIRouter()

def _to_read_dto(obs: AuditObservation, db: Session) -> AuditObservationRead:
    doc_fn = None
    if obs.document_id:
        d = db.query(Document).filter(Document.id == obs.document_id).first()
        if d:
            doc_fn = d.filename

    sheet_t = None
    if obs.sheet_id:
        s = db.query(DocumentSheet).filter(DocumentSheet.id == obs.sheet_id).first()
        if s:
            sheet_t = s.title or s.sheet_code or f"Lámina {s.sheet_number}"

    prov_fn = None
    if obs.provisioned_document_id:
        pd = db.query(Document).filter(Document.id == obs.provisioned_document_id).first()
        if pd:
            prov_fn = pd.filename

    return AuditObservationRead(
        id=obs.id,
        organization_id=obs.organization_id,
        project_id=obs.project_id,
        stage=obs.stage,
        code=obs.code,
        item_type=obs.item_type,
        title=obs.title,
        description=obs.description,
        recommendation=obs.recommendation,
        discipline=obs.discipline,
        severity=obs.severity,
        status=obs.status,
        rule_finding_id=obs.rule_finding_id,
        rule_id=obs.rule_id,
        rule_code=obs.rule_code,
        document_id=obs.document_id,
        document_filename=doc_fn,
        sheet_id=obs.sheet_id,
        sheet_title=sheet_t,
        review_run_id=obs.review_run_id,
        required_deliverable_type=obs.required_deliverable_type,
        provisioned_document_id=obs.provisioned_document_id,
        provisioned_document_filename=prov_fn,
        resolution_notes=obs.resolution_notes,
        issued_by=obs.issued_by,
        assigned_to=obs.assigned_to,
        issued_at=obs.issued_at,
        answered_at=obs.answered_at,
        provisioned_at=obs.provisioned_at,
        closed_at=obs.closed_at,
        history_trace=obs.history_trace or [],
        responses=[
            {
                "id": r.id,
                "observation_id": r.observation_id,
                "author": r.author,
                "author_role": r.author_role,
                "response_text": r.response_text,
                "attached_document_id": r.attached_document_id,
                "created_at": r.created_at
            }
            for r in (obs.responses or [])
        ],
        created_at=obs.created_at,
        updated_at=obs.updated_at
    )

@router.get("/", response_model=List[AuditObservationRead])
def list_observations(
    project_id: Optional[str] = Query(None),
    item_type: Optional[str] = Query(None),
    discipline: Optional[str] = Query(None),
    stage: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Lista las observaciones técnicas, RFIs, bloqueos y faltantes menores del proyecto."""
    service = ObservationService(db)
    items = service.list_observations(
        project_id=project_id,
        item_type=item_type,
        discipline=discipline,
        stage=stage,
        status=status,
        severity=severity,
        search=search
    )
    return [_to_read_dto(item, db) for item in items]

@router.get("/{obs_id}", response_model=AuditObservationRead)
def get_observation(
    obs_id: str,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Obtiene el detalle completo de una observación con su historial y respuestas."""
    service = ObservationService(db)
    obs = service.get_by_id(obs_id)
    if not obs:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Observación no encontrada.")
    return _to_read_dto(obs, db)

@router.post("/generate-from-run", response_model=List[AuditObservationRead])
def generate_observations_from_run(
    payload: GenerateObservationsRequest,
    tenant: TenantContext = Depends(require_role(["admin", "audit_lead", "reviewer"])),
    db: Session = Depends(get_db)
):
    """Genera formalmente observaciones y RFIs a partir de los hallazgos de una corrida."""
    service = ObservationService(db)
    try:
        created = service.generate_observations_from_findings(
            project_id=payload.project_id,
            review_run_id=payload.review_run_id,
            stage_override=payload.stage,
            author=tenant.user.display_name or tenant.user.email
        )
        return [_to_read_dto(item, db) for item in created]
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@router.post("/{obs_id}/issue", response_model=AuditObservationRead)
def issue_observation(
    obs_id: str,
    payload: IssueObservationRequest,
    tenant: TenantContext = Depends(require_role(["admin", "audit_lead", "reviewer"])),
    db: Session = Depends(get_db)
):
    """Emite formalmente una observación o RFI hacia el proyectista."""
    service = ObservationService(db)
    try:
        updated = service.issue_observation(
            obs_id=obs_id,
            assigned_to=payload.assigned_to,
            author=tenant.user.display_name or tenant.user.email,
            notes=payload.notes
        )
        return _to_read_dto(updated, db)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@router.post("/{obs_id}/response", response_model=AuditObservationRead)
def submit_response(
    obs_id: str,
    payload: ObservationResponseCreate,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Registra una respuesta o aclaración técnica del proyectista/contratista."""
    service = ObservationService(db)
    try:
        updated = service.submit_response(
            obs_id=obs_id,
            response_text=payload.response_text,
            author=tenant.user.display_name or tenant.user.email,
            author_role=payload.author_role,
            attached_document_id=payload.attached_document_id
        )
        return _to_read_dto(updated, db)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@router.post("/{obs_id}/provision", response_model=AuditObservationRead)
def provision_evidence(
    obs_id: str,
    payload: ProvisionEvidenceRequest,
    tenant: TenantContext = Depends(require_role(["admin", "audit_lead", "reviewer"])),
    db: Session = Depends(get_db)
):
    """Vincula un documento o nueva versión como evidencia provisionada."""
    service = ObservationService(db)
    try:
        updated = service.provision_evidence(
            obs_id=obs_id,
            document_id=payload.document_id,
            author=tenant.user.display_name or tenant.user.email,
            notes=payload.notes
        )
        return _to_read_dto(updated, db)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@router.post("/{obs_id}/delta-reevaluation", response_model=DeltaReevaluationResponse)
def execute_delta_reevaluation(
    obs_id: str,
    tenant: TenantContext = Depends(require_role(["admin", "audit_lead", "reviewer"])),
    db: Session = Depends(get_db)
):
    """Ejecuta la revisión incremental o delta de las reglas afectadas por la nueva evidencia."""
    service = ObservationService(db)
    try:
        return service.execute_delta_reevaluation(
            obs_id=obs_id,
            author=tenant.user.display_name or tenant.user.email
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/{obs_id}/reopen", response_model=AuditObservationRead)
def reopen_observation(
    obs_id: str,
    payload: Optional[ReopenObservationRequest] = None,
    tenant: TenantContext = Depends(require_role(["admin", "audit_lead", "reviewer"])),
    db: Session = Depends(get_db)
):
    """Reabre formalmente una observación o RFI cerrada ante nueva evidencia o auditoría."""
    service = ObservationService(db)
    try:
        updated = service.reopen_observation(
            obs_id=obs_id,
            author=tenant.user.display_name or tenant.user.email,
            reason=payload.reason if payload else None
        )
        return _to_read_dto(updated, db)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
