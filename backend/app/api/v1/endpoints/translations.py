from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models.core import Organization
from app.core.deps import get_current_tenant, TenantContext
from app.schemas.translations import (
    LanguageDetectionRequest,
    LanguageDetectionResponse,
    TranslationRequest,
    TranslationResponse,
    BatchTranslationRequest,
    BatchTranslationResponse
)
from app.services.translation.translation_service import TranslationService

router = APIRouter()

def _resolve_org_id(requested_org_id: Optional[str], tenant: Optional[TenantContext], db: Session) -> str:
    """Resuelve la organización activa garantizando tenancy estricta."""
    if tenant and hasattr(tenant, "organization") and tenant.organization:
        return str(tenant.organization.id)
    if requested_org_id:
        # Validar existencia de la organización
        org = db.query(Organization).filter(Organization.id == requested_org_id).first()
        if org:
            return str(org.id)
    # Fallback determinístico a la primera organización del sistema (desarrollo / local)
    default_org = db.query(Organization).first()
    if default_org:
        return str(default_org.id)
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No se encontró una organización activa para tenancy.")


@router.post("/detect-language", response_model=LanguageDetectionResponse)
def detect_language(
    payload: LanguageDetectionRequest,
    db: Session = Depends(get_db)
):
    """Detecta el idioma de un texto técnico con puntuación de confianza."""
    svc = TranslationService(db)
    return svc.detect_language(payload.text)


@router.post("/translate", response_model=TranslationResponse)
def translate_entity(
    payload: TranslationRequest,
    db: Session = Depends(get_db)
):
    """
    Traduce los campos de una entidad técnica bajo demanda con caché por SHA-256
    y tenancy estricta. Marca versiones previas como 'stale' si el texto cambió.
    """
    svc = TranslationService(db)
    org_id = _resolve_org_id(payload.organization_id, None, db)
    try:
        return svc.translate_entity_fields(payload, organization_id=org_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error procesando traducción: {str(e)}")


@router.post("/translate-batch", response_model=BatchTranslationResponse)
def translate_batch(
    payload: BatchTranslationRequest,
    db: Session = Depends(get_db)
):
    """Traduce por lote múltiples elementos con caché independiente por cada entidad."""
    svc = TranslationService(db)
    org_id = _resolve_org_id(payload.organization_id, None, db)
    results = []
    cached_count = 0

    for item_req in payload.items:
        item_req.target_language = item_req.target_language or payload.target_language
        if not item_req.source_language or item_req.source_language == "auto":
            item_req.source_language = payload.source_language or "auto"
        res = svc.translate_entity_fields(item_req, organization_id=org_id)
        if res.cached:
            cached_count += 1
        results.append(res)

    return BatchTranslationResponse(
        total_requested=len(payload.items),
        total_completed=len(results),
        total_cached=cached_count,
        translations=results
    )


@router.get("/entity/{source_entity_type}/{source_entity_id}", response_model=TranslationResponse)
def get_entity_translation(
    source_entity_type: str,
    source_entity_id: str,
    target_language: str = Query("es", description="Idioma de destino solicitado"),
    organization_id: Optional[str] = Query(None, description="Organización activa"),
    db: Session = Depends(get_db)
):
    """Recupera la traducción activa (no stale) de una entidad bajo tenancy estricta."""
    svc = TranslationService(db)
    org_id = _resolve_org_id(organization_id, None, db)
    translation = svc.get_entity_translation(
        source_entity_type=source_entity_type,
        source_entity_id=source_entity_id,
        target_language=target_language,
        organization_id=org_id
    )
    if not translation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró traducción activa en idioma '{target_language}' para {source_entity_type} '{source_entity_id}'."
        )
    return translation
