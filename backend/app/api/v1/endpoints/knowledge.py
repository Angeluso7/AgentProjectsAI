from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.deps import get_current_tenant, TenantContext
from app.services.knowledge.service import KnowledgeBaseService
from app.schemas.knowledge_base import (
    KnowledgeItemCreate, KnowledgeItemUpdate, KnowledgeItemTransitionRequest,
    KnowledgeItemVersionRequest, KnowledgeItemRead, KnowledgeItemSummaryRead,
    KnowledgeSyncRequest, KnowledgeSyncResponse, KnowledgeSearchQuery,
    KnowledgeSearchResponse, KnowledgeBaseStatsRead
)

router = APIRouter()

@router.get("/items", response_model=List[KnowledgeItemSummaryRead])
def list_knowledge_items(
    project_id: Optional[str] = Query(None, description="Filtrar por proyecto activo (opcional)"),
    domain: Optional[str] = Query(None, description="Filtrar por dominio de conocimiento"),
    status: Optional[str] = Query(None, description="Filtrar por estado de ciclo de vida"),
    discipline: Optional[str] = Query(None, description="Filtrar por disciplina"),
    stage: Optional[str] = Query(None, description="Filtrar por etapa"),
    active_only: bool = Query(False, description="Solo unidades aprobadas/validadas para reutilización"),
    search: Optional[str] = Query(None, description="Búsqueda por texto libre"),
    include_global: bool = Query(True, description="Incluir conocimiento global de organización"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_current_tenant)
):
    """Lista unidades de conocimiento con filtros de dominio, estado, disciplina y gobernanza."""
    service = KnowledgeBaseService(db)
    items, _ = service.list_items(
        organization_id=tenant.organization.id,
        project_id=project_id,
        domain=domain,
        status=status,
        discipline=discipline,
        stage=stage,
        active_only=active_only,
        search=search,
        include_global=include_global,
        skip=skip,
        limit=limit
    )
    return items

@router.get("/items/{item_id}", response_model=KnowledgeItemRead)
def get_knowledge_item_detail(
    item_id: str,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_current_tenant)
):
    """Obtiene el detalle completo de una unidad de conocimiento con fragmentos (chunks) y trazabilidad."""
    service = KnowledgeBaseService(db)
    item = service.get_item(item_id, tenant.organization.id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unidad de conocimiento con id '{item_id}' no encontrada."
        )
    return item

@router.post("/items", response_model=KnowledgeItemRead, status_code=status.HTTP_201_CREATED)
def create_knowledge_item(
    payload: KnowledgeItemCreate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_current_tenant)
):
    """Crea manualmente una nueva unidad de conocimiento estructurada."""
    service = KnowledgeBaseService(db)
    author = getattr(tenant.user, "email", "system") if hasattr(tenant, "user") else "system"
    item = service.create_item(tenant.organization.id, payload, author=author)
    return item

@router.put("/items/{item_id}", response_model=KnowledgeItemRead)
def update_knowledge_item(
    item_id: str,
    payload: KnowledgeItemUpdate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_current_tenant)
):
    """Actualiza metadatos o contenido de una unidad de conocimiento."""
    service = KnowledgeBaseService(db)
    author = getattr(tenant.user, "email", "system") if hasattr(tenant, "user") else "system"
    item = service.update_item(item_id, tenant.organization.id, payload, author=author)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unidad de conocimiento con id '{item_id}' no encontrada."
        )
    return item

@router.post("/items/{item_id}/transition", response_model=KnowledgeItemRead)
def transition_knowledge_status(
    item_id: str,
    payload: KnowledgeItemTransitionRequest,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_current_tenant)
):
    """
    Ejecuta una transición de estado de ciclo de vida (draft -> reviewed -> validated -> approved_for_reuse -> superseded/rejected).
    Afecta inmediatamente la idoneidad de reutilización automática (is_active_for_reuse).
    """
    service = KnowledgeBaseService(db)
    author = payload.reviewer or (getattr(tenant.user, "email", "system") if hasattr(tenant, "user") else "system")
    item = service.transition_status(
        item_id=item_id,
        organization_id=tenant.organization.id,
        target_status=payload.target_status.value if hasattr(payload.target_status, "value") else str(payload.target_status),
        author=author,
        notes=payload.notes
    )
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unidad de conocimiento con id '{item_id}' no encontrada."
        )
    return item

@router.post("/items/{item_id}/version", response_model=KnowledgeItemRead)
def version_knowledge_item(
    item_id: str,
    payload: KnowledgeItemVersionRequest,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_current_tenant)
):
    """Crea una nueva versión formal de una unidad, marcando la anterior como superseded."""
    service = KnowledgeBaseService(db)
    author = payload.author or (getattr(tenant.user, "email", "system") if hasattr(tenant, "user") else "system")
    item = service.create_new_version(
        item_id=item_id,
        organization_id=tenant.organization.id,
        payload=payload,
        author=author
    )
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unidad de conocimiento con id '{item_id}' no encontrada."
        )
    return item

# =========================================================================
# SINCRONIZACIÓN DE MÓDULOS
# =========================================================================
@router.post("/sync/all", response_model=KnowledgeSyncResponse)
def sync_all_operational_knowledge(
    payload: KnowledgeSyncRequest,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_current_tenant)
):
    """Sincroniza conocimiento transversal desde Intake, Reglas QA/QC, Completitud, Observaciones y Snapshots."""
    service = KnowledgeBaseService(db)
    author = getattr(tenant.user, "email", "system") if hasattr(tenant, "user") else "system"
    return service.sync_all(
        organization_id=tenant.organization.id,
        project_id=payload.project_id,
        author=author,
        auto_approve=payload.auto_approve
    )

@router.post("/sync/sources", response_model=KnowledgeSyncResponse)
def sync_sources_knowledge(
    payload: KnowledgeSyncRequest,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_current_tenant)
):
    """Sincroniza fuentes y criterios normativos de Intake."""
    service = KnowledgeBaseService(db)
    author = getattr(tenant.user, "email", "system") if hasattr(tenant, "user") else "system"
    cnt = service.sync_from_intake_sources(tenant.organization.id, payload.project_id, author, payload.auto_approve)
    return KnowledgeSyncResponse(
        success=True,
        message=f"Sincronizados {cnt} criterios y fuentes normativas.",
        synced_counts={"sources": cnt},
        total_items_created=cnt,
        total_items_updated=0
    )

@router.post("/sync/rules", response_model=KnowledgeSyncResponse)
def sync_rules_knowledge(
    payload: KnowledgeSyncRequest,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_current_tenant)
):
    """Sincroniza reglas QA/QC baseline activas."""
    service = KnowledgeBaseService(db)
    author = getattr(tenant.user, "email", "system") if hasattr(tenant, "user") else "system"
    cnt = service.sync_from_rules_engine(tenant.organization.id, author, payload.auto_approve)
    return KnowledgeSyncResponse(
        success=True,
        message=f"Sincronizadas {cnt} definiciones de reglas QA/QC.",
        synced_counts={"rules": cnt},
        total_items_created=cnt,
        total_items_updated=0
    )

@router.post("/sync/completeness", response_model=KnowledgeSyncResponse)
def sync_completeness_knowledge(
    payload: KnowledgeSyncRequest,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_current_tenant)
):
    """Sincroniza especificaciones de entregables de la matriz de completitud."""
    service = KnowledgeBaseService(db)
    author = getattr(tenant.user, "email", "system") if hasattr(tenant, "user") else "system"
    cnt = service.sync_from_completeness_matrix(tenant.organization.id, payload.project_id, author, payload.auto_approve)
    return KnowledgeSyncResponse(
        success=True,
        message=f"Sincronizadas {cnt} especificaciones de entregables.",
        synced_counts={"completeness": cnt},
        total_items_created=cnt,
        total_items_updated=0
    )

@router.post("/sync/observations", response_model=KnowledgeSyncResponse)
def sync_observations_knowledge(
    payload: KnowledgeSyncRequest,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_current_tenant)
):
    """Sincroniza observaciones y RFIs resueltos/cerrados."""
    service = KnowledgeBaseService(db)
    author = getattr(tenant.user, "email", "system") if hasattr(tenant, "user") else "system"
    cnt = service.sync_from_observations(tenant.organization.id, payload.project_id, author, payload.auto_approve, only_closed=True)
    return KnowledgeSyncResponse(
        success=True,
        message=f"Sincronizadas {cnt} lecciones de observaciones resueltas.",
        synced_counts={"observations": cnt},
        total_items_created=cnt,
        total_items_updated=0
    )

@router.post("/sync/snapshots", response_model=KnowledgeSyncResponse)
def sync_snapshots_knowledge(
    payload: KnowledgeSyncRequest,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_current_tenant)
):
    """Sincroniza hitos y snapshots de corte consolidado."""
    service = KnowledgeBaseService(db)
    author = getattr(tenant.user, "email", "system") if hasattr(tenant, "user") else "system"
    cnt = service.sync_from_stage_snapshots(tenant.organization.id, payload.project_id, author, payload.auto_approve)
    return KnowledgeSyncResponse(
        success=True,
        message=f"Sincronizados {cnt} hitos consolidados de etapa.",
        synced_counts={"snapshots": cnt},
        total_items_created=cnt,
        total_items_updated=0
    )

@router.post("/sync-hybrid")
def sync_hybrid_knowledge(
    payload: KnowledgeSyncRequest,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_current_tenant)
):
    """
    Sincroniza todos los chunks aprobados y activos de la Base de Conocimiento hacia Qdrant.
    Excluye estrictamente borradores, rechazados o ítems inactivos.
    """
    service = KnowledgeBaseService(db)
    return service.sync_hybrid_vector_store(tenant.organization.id, payload.project_id)

# =========================================================================
# RECUPERACIÓN CONTEXTUAL (RAG) & ESTADÍSTICAS
# =========================================================================
@router.post("/search", response_model=KnowledgeSearchResponse)
def search_knowledge_context(
    query: KnowledgeSearchQuery,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_current_tenant)
):
    """
    Recuperador contextual de conocimiento operacional para el asistente (preparación RAG).
    Excluye automáticamente registros en draft, rejected o superseded si active_only=True.
    """
    service = KnowledgeBaseService(db)
    return service.search_knowledge(tenant.organization.id, query)

@router.get("/stats", response_model=KnowledgeBaseStatsRead)
def get_knowledge_base_stats(
    project_id: Optional[str] = Query(None, description="Filtrar por proyecto activo (opcional)"),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_current_tenant)
):
    """Retorna métricas y estadísticas agregadas de la Base de Conocimiento Operacional."""
    service = KnowledgeBaseService(db)
    return service.get_stats(tenant.organization.id, project_id)
