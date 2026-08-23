from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.deps import get_current_tenant, TenantContext
from app.schemas.acquisition import (
    DetectInformationGapRequest, DetectInformationGapResponse,
    InformationAcquisitionRequestRead, WebSearchPermissionActionRequest,
    ViewerKnowledgeCaptureRequest, IngestionChannelSummaryResponse,
    VisualDeduplicationCheckRequest, VisualDeduplicationCheckResponse
)
from app.schemas.knowledge_base import KnowledgeItemRead
from app.services.acquisition.service import InformationAcquisitionService

router = APIRouter()

@router.post("/detect-gap", response_model=DetectInformationGapResponse)
def detect_information_gap(
    req: DetectInformationGapRequest,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Paso 1 y Paso 2 de Adquisición:
    Evalúa si la consulta o tópico se resuelve en la Base de Conocimiento interna (RAG).
    Si no es suficiente, registra automáticamente un InformationAcquisitionRequest
    en estado 'pending_permission' solicitando permiso de búsqueda web al usuario.
    """
    service = InformationAcquisitionService(db)
    user_identifier = tenant.user.email if tenant.user else "system"
    return service.detect_information_gap(
        organization_id=tenant.organization.id,
        req=req,
        author=user_identifier
    )

@router.get("/requests", response_model=List[InformationAcquisitionRequestRead])
def list_acquisition_requests(
    project_id: Optional[str] = Query(None),
    permission_status: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Lista las solicitudes de adquisición de información registradas en la organización o proyecto.
    """
    service = InformationAcquisitionService(db)
    items = service.list_acquisition_requests(
        organization_id=tenant.organization.id,
        project_id=project_id,
        permission_status=permission_status,
        status=status,
        limit=limit
    )
    return [InformationAcquisitionRequestRead.model_validate(item) for item in items]

@router.get("/requests/{request_id}", response_model=InformationAcquisitionRequestRead)
def get_acquisition_request(
    request_id: str,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Obtiene el detalle completo y trazabilidad de una solicitud de adquisición de información.
    """
    from app.db.models.acquisition import InformationAcquisitionRequest
    item = db.query(InformationAcquisitionRequest).filter(
        InformationAcquisitionRequest.id == request_id,
        InformationAcquisitionRequest.organization_id == tenant.organization.id
    ).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Solicitud no encontrada.")
    return InformationAcquisitionRequestRead.model_validate(item)

@router.post("/requests/{request_id}/permission", response_model=InformationAcquisitionRequestRead)
def respond_web_search_permission(
    request_id: str,
    action_req: WebSearchPermissionActionRequest,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Paso 3 y Paso 4 de Adquisición:
    Procesa la decisión humana de autorizar o denegar la búsqueda web con IA.
    Al aprobarse, realiza la búsqueda, extrae conocimiento en estado 'extracted' (no aprobado aún)
    y evalúa si se requiere escalar a una solicitud formal de documentación técnica del proyecto.
    """
    service = InformationAcquisitionService(db)
    user_identifier = tenant.user.email if tenant.user else "usuario_auditor"
    try:
        updated_req = service.respond_web_search_permission(
            organization_id=tenant.organization.id,
            request_id=request_id,
            action_req=action_req,
            user_id=user_identifier
        )
        return InformationAcquisitionRequestRead.model_validate(updated_req)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error procesando permiso: {str(e)}")

@router.post("/capture-from-viewer", response_model=KnowledgeItemRead)
def capture_from_viewer_to_knowledge(
    req: ViewerKnowledgeCaptureRequest,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Canal de Ingesta Visual:
    Captura un símbolo, tabla, detalle técnico o leyenda directamente desde el visor de planos
    hacia la Base de Conocimiento Operacional con metadatos gráficos, bbox y recorte PNG.
    """
    service = InformationAcquisitionService(db)
    user_identifier = tenant.user.email if tenant.user else "auditor_visual"
    try:
        item = service.capture_from_viewer_to_knowledge(
            organization_id=tenant.organization.id,
            req=req,
            user_id=user_identifier
        )
        return KnowledgeItemRead.model_validate(item)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error capturando desde visor: {str(e)}")

@router.post("/visual-dedup-check", response_model=VisualDeduplicationCheckResponse)
def check_visual_deduplication(
    req: VisualDeduplicationCheckRequest,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Evalúa antes de guardar si el elemento visual capturado ya existe en el catálogo
    para sugerir vincular la ocurrencia o versionar el ítem.
    """
    service = InformationAcquisitionService(db)
    return service.check_visual_deduplication(
        organization_id=tenant.organization.id,
        req=req
    )

@router.get("/channels-summary", response_model=IngestionChannelSummaryResponse)
def get_ingestion_channels_summary(
    project_id: Optional[str] = Query(None),
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Retorna la matriz consolidada de canales de ingesta de información, modalidades
    y estado de gobernanza (reutilizables vs pendientes de aprobación).
    """
    service = InformationAcquisitionService(db)
    return service.get_ingestion_channels_summary(
        organization_id=tenant.organization.id,
        project_id=project_id
    )
