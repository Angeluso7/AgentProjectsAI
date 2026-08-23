from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models.core import User
from app.core.deps import get_current_user, get_current_tenant, TenantContext
from app.schemas.annotations import (
    CropOcrRequest, CropOcrResponse,
    ManualAnnotationCreate, ManualAnnotationRead, ManualAnnotationUpdate,
    KnowledgeLibraryEntryCreate, KnowledgeLibraryEntryRead,
    ActiveLearningPromotionCreate, ActiveLearningPromotionRead,
    IncorporateProjectSelectionsRequest, IncorporateProjectSelectionsResponse
)
from app.db.repositories.annotation_repository import AnnotationRepository
from app.db.models.active_learning import ManualAnnotation

router = APIRouter()

@router.post("/crop-ocr", response_model=CropOcrResponse)
def run_ocr_on_crop(
    req: CropOcrRequest,
    current_user: User = Depends(get_current_user)
):
    """Ejecuta OCR sobre un recorte en Base64 y retorna el texto extraído."""
    text, confidence, engine = AnnotationRepository.run_crop_ocr(req.image_base64)
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    return CropOcrResponse(
        text=text,
        confidence=confidence,
        engine_used=engine,
        line_count=len(lines)
    )


@router.post("", response_model=ManualAnnotationRead)
def create_manual_annotation(
    req: ManualAnnotationCreate,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Crea y persiste una nueva anotación manual y guarda el archivo PNG recortado."""
    annotation = AnnotationRepository.create_annotation(
        db=db,
        organization_id=tenant.organization.id,
        user_id=tenant.user.id,
        data=req.model_dump()
    )
    return ManualAnnotationRead.model_validate(annotation)


@router.get("/disciplines", response_model=List[str])
def list_annotation_disciplines(
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Retorna todas las disciplinas distintas registradas en anotaciones manuales del tenant."""
    return AnnotationRepository.list_distinct_disciplines(db, tenant.organization.id)


@router.get("", response_model=List[ManualAnnotationRead])
def list_manual_annotations(
    sheet_id: Optional[str] = Query(None),
    document_id: Optional[str] = Query(None),
    project_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Lista las anotaciones manuales del tenant filtradas por lámina, documento o proyecto."""
    items = AnnotationRepository.list_annotations(
        db=db,
        organization_id=tenant.organization.id,
        sheet_id=sheet_id,
        document_id=document_id,
        project_id=project_id,
        status=status
    )
    return [ManualAnnotationRead.model_validate(item) for item in items]


@router.put("/{annotation_id}", response_model=ManualAnnotationRead)
def update_manual_annotation(
    annotation_id: str,
    req: ManualAnnotationUpdate,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Actualiza una anotación manual existente."""
    updated = AnnotationRepository.update_annotation(
        db=db,
        organization_id=tenant.organization.id,
        annotation_id=annotation_id,
        user_id=tenant.user.id,
        data=req.model_dump(exclude_unset=True)
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Anotación no encontrada.")
    return ManualAnnotationRead.model_validate(updated)


@router.delete("/{annotation_id}")
def delete_manual_annotation(
    annotation_id: str,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Elimina una anotación manual."""
    annotation = db.query(ManualAnnotation).filter(
        ManualAnnotation.id == annotation_id,
        ManualAnnotation.organization_id == tenant.organization.id
    ).first()
    if not annotation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Anotación no encontrada.")

    db.delete(annotation)
    db.commit()
    return {"message": "Anotación eliminada exitosamente."}



# ==========================================
# NIVEL 1: BASE DE CONOCIMIENTO GUÍA & PLANTILLAS
# ==========================================

@router.post("/knowledge-library", response_model=KnowledgeLibraryEntryRead)
def add_to_knowledge_library(
    req: KnowledgeLibraryEntryCreate,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Nivel 1: Guarda un elemento curado en la Base de Conocimiento Guía & Plantillas."""
    entry = AnnotationRepository.promote_to_knowledge_library(
        db=db,
        organization_id=tenant.organization.id,
        user_id=tenant.user.id,
        data=req.model_dump()
    )
    return KnowledgeLibraryEntryRead.model_validate(entry)


@router.get("/knowledge-library", response_model=List[KnowledgeLibraryEntryRead])
def list_knowledge_library_entries(
    entry_type: Optional[str] = Query(None),
    discipline: Optional[str] = Query(None),
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Consulta las entradas de la Base de Conocimiento Guía."""
    entries = AnnotationRepository.list_knowledge_entries(
        db=db,
        organization_id=tenant.organization.id,
        entry_type=entry_type,
        discipline=discipline
    )
    return [KnowledgeLibraryEntryRead.model_validate(e) for e in entries]


# ==========================================
# NIVEL 2: MLOPS & ACTIVE LEARNING
# ==========================================

@router.post("/active-learning/promote", response_model=ActiveLearningPromotionRead)
def promote_to_active_learning(
    req: ActiveLearningPromotionCreate,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Nivel 2: Promueve un elemento hacia el pool de entrenamiento de Active Learning."""
    promotion = AnnotationRepository.promote_to_active_learning(
        db=db,
        organization_id=tenant.organization.id,
        user_id=tenant.user.id,
        data=req.model_dump()
    )
    return ActiveLearningPromotionRead.model_validate(promotion)


@router.get("/active-learning", response_model=List[ActiveLearningPromotionRead])
def list_active_learning_promotions(
    target_engine: Optional[str] = Query(None),
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Lista los elementos promovidos al pool de Active Learning."""
    promotions = AnnotationRepository.list_active_learning_promotions(
        db=db,
        organization_id=tenant.organization.id,
        target_engine=target_engine
    )
    return [ActiveLearningPromotionRead.model_validate(p) for p in promotions]


# =========================================================
# INTEGRACIÓN: INCORPORAR SELECCIONES A INFORMACIÓN BASADA EN PROYECTO
# =========================================================

@router.post("/incorporate-to-project-document", response_model=IncorporateProjectSelectionsResponse)
def incorporate_selections_to_project_document(
    req: IncorporateProjectSelectionsRequest,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Incorpora las selecciones validadas del visor de planos hacia un RuleDocument
    'Información basada en proyecto XXXXXXXXX' en Documentos Nativos & Fuentes Incorporados.
    """
    try:
        res = AnnotationRepository.incorporate_selections_to_project_document(
            db=db,
            organization_id=tenant.organization.id,
            project_id=req.project_id,
            user_id=tenant.user.id,
            annotation_ids=req.annotation_ids
        )
        return IncorporateProjectSelectionsResponse(**res)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error incorporando selecciones: {str(e)}")

