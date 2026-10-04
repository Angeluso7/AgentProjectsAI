from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.evaluation import (
    EvaluationDatasetCreate, EvaluationDatasetRead,
    EvaluationSampleCreate, EvaluationSampleRead,
    AnnotationSetCreate, AnnotationSetRead, AnnotationStatusUpdate,
    EvaluationRunCreate, EvaluationRunRead, EvaluationMetricRead
)
from app.services.evaluation.service import EvaluationService
from app.core.deps import get_current_tenant, require_role, TenantContext

router = APIRouter()

# ============================================================================
# 1. GESTIÓN DE DATASETS
# ============================================================================

@router.get("/datasets", response_model=List[EvaluationDatasetRead])
def list_datasets(
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Lista todos los datasets de evaluación accesibles (privados del tenant y globales)."""
    svc = EvaluationService(db)
    datasets = svc.list_datasets(organization_id=tenant.organization.id)
    result = []
    for d in datasets:
        d_read = EvaluationDatasetRead.from_orm(d)
        d_read.samples_count = len(d.samples) if d.samples else 0
        result.append(d_read)
    return result

@router.post("/datasets", response_model=EvaluationDatasetRead, status_code=status.HTTP_201_CREATED)
def create_dataset(
    req: EvaluationDatasetCreate,
    tenant: TenantContext = Depends(require_role(["admin", "audit_lead"])),
    db: Session = Depends(get_db)
):
    """Crea un nuevo dataset de evaluación vinculado a la organización activa."""
    svc = EvaluationService(db)
    return svc.create_dataset(
        data=req,
        created_by=tenant.user.email,
        organization_id=tenant.organization.id
    )

@router.get("/datasets/{dataset_id}", response_model=EvaluationDatasetRead)
def get_dataset(
    dataset_id: str,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Obtiene el detalle y estado de un dataset de evaluación."""
    svc = EvaluationService(db)
    d = svc.get_dataset(dataset_id, organization_id=tenant.organization.id)
    if not d:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset no encontrado.")
    d_read = EvaluationDatasetRead.from_orm(d)
    d_read.samples_count = len(d.samples) if d.samples else 0
    return d_read

@router.post("/datasets/{dataset_id}/freeze", response_model=EvaluationDatasetRead)
def freeze_dataset(
    dataset_id: str,
    tenant: TenantContext = Depends(require_role(["admin", "audit_lead"])),
    db: Session = Depends(get_db)
):
    """Congela el dataset generando un snapshot SHA-256 inmutable de las muestras y anotaciones aprobadas."""
    svc = EvaluationService(db)
    try:
        return svc.freeze_dataset(dataset_id, organization_id=tenant.organization.id)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))

# ============================================================================
# 2. MUESTRAS Y ANOTACIONES
# ============================================================================

@router.post("/datasets/{dataset_id}/samples", response_model=EvaluationSampleRead, status_code=status.HTTP_201_CREATED)
def add_dataset_sample(
    dataset_id: str,
    sample_in: EvaluationSampleCreate,
    tenant: TenantContext = Depends(require_role(["admin", "audit_lead", "contributor"])),
    db: Session = Depends(get_db)
):
    """Agrega una muestra técnica al dataset de evaluación con checksum SHA-256."""
    svc = EvaluationService(db)
    try:
        return svc.add_sample(dataset_id, sample_in, organization_id=tenant.organization.id)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))

@router.get("/samples/{sample_id}", response_model=EvaluationSampleRead)
def get_sample(
    sample_id: str,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Obtiene el detalle de una muestra de evaluación."""
    from app.db.models.evaluation import EvaluationSample
    sample = db.query(EvaluationSample).filter(EvaluationSample.id == sample_id).first()
    if not sample:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Muestra no encontrada.")
    return sample

@router.get("/samples/{sample_id}/annotations", response_model=List[AnnotationSetRead])
def list_sample_annotations(
    sample_id: str,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Lista todos los conjuntos de anotaciones registrados para la muestra."""
    from app.db.models.evaluation import AnnotationSet
    return db.query(AnnotationSet).filter(AnnotationSet.sample_id == sample_id).all()

@router.post("/samples/{sample_id}/annotations", response_model=AnnotationSetRead, status_code=status.HTTP_201_CREATED)
def create_annotation(
    sample_id: str,
    ann_in: AnnotationSetCreate,
    tenant: TenantContext = Depends(require_role(["admin", "audit_lead", "reviewer", "contributor"])),
    db: Session = Depends(get_db)
):
    """Carga un conjunto de anotaciones validado contra el JSON Schema correspondiente."""
    svc = EvaluationService(db)
    try:
        return svc.add_annotation(sample_id, ann_in, annotator_id=tenant.user.email)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))

@router.patch("/annotations/{annotation_id}/status", response_model=AnnotationSetRead)
def update_annotation_status(
    annotation_id: str,
    req: AnnotationStatusUpdate,
    tenant: TenantContext = Depends(require_role(["admin", "audit_lead", "reviewer"])),
    db: Session = Depends(get_db)
):
    """Actualiza el estado de una anotación (submitted, reviewed, approved, rejected) y crea versión superseded si aplica."""
    svc = EvaluationService(db)
    try:
        return svc.update_annotation_status(annotation_id, req.status, reviewer_id=tenant.user.email)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))

# ============================================================================
# 3. CORRIDAS DE EVALUACIÓN Y SCORECARD
# ============================================================================

@router.post("/datasets/{dataset_id}/run", response_model=EvaluationRunRead, status_code=status.HTTP_201_CREATED)
def run_dataset_evaluation(
    dataset_id: str,
    req: EvaluationRunCreate = EvaluationRunCreate(),
    tenant: TenantContext = Depends(require_role(["admin", "audit_lead"])),
    db: Session = Depends(get_db)
):
    """Ejecuta una evaluación reproducible en sandbox sobre las muestras del split seleccionado."""
    svc = EvaluationService(db)
    try:
        return svc.run_evaluation(
            dataset_id=dataset_id,
            split=req.split_evaluated,
            config=req.config,
            created_by=tenant.user.email,
            organization_id=tenant.organization.id
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))

@router.get("/runs", response_model=List[EvaluationRunRead])
def list_evaluation_runs(
    dataset_id: Optional[str] = Query(None),
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Lista las corridas de evaluación históricas."""
    svc = EvaluationService(db)
    return svc.list_runs(dataset_id=dataset_id)

@router.get("/runs/{run_id}", response_model=EvaluationRunRead)
def get_evaluation_run(
    run_id: str,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Obtiene el resumen y resultados de una corrida de evaluación."""
    svc = EvaluationService(db)
    r = svc.get_run(run_id)
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Corrida de evaluación no encontrada.")
    return r

@router.get("/runs/{run_id}/metrics", response_model=List[EvaluationMetricRead])
def list_run_metrics(
    run_id: str,
    category: Optional[str] = Query(None, description="perceptual, decisional"),
    component: Optional[str] = Query(None, description="ocr, layout, title_block, table, symbol, rules, hitl"),
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Lista todas las métricas detalladas calculadas durante la corrida."""
    from app.db.models.evaluation import EvaluationMetric
    query = db.query(EvaluationMetric).filter(EvaluationMetric.evaluation_run_id == run_id)
    if category:
        query = query.filter(EvaluationMetric.category == category)
    if component:
        query = query.filter(EvaluationMetric.component == component)
    return query.all()
