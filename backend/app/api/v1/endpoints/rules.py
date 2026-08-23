from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models.decision_memory import RuleDefinition
from app.schemas.qa_rule import (
    RuleDefinitionRead, RuleFindingRead, RuleEvaluationSummaryResponse
)
from app.schemas.operations import AsyncJobAcceptedResponse
from app.schemas.intake_extractions import (
    RuleDocumentRead, RuleDocumentDetailRead, RuleDocumentUpdate,
    RuleDocumentItemRead, RuleDocumentItemUpdate,
    ConfirmRuleDocumentContentRequest, ConfirmRuleDocumentContentResponse,
    PromoteToBaselineResponse
)
from app.services.rules.engine import RuleEngine, RuleRegistry
from app.services.operations.service import OperationsService
from app.db.repositories.document_repository import DocumentRepository
from app.db.repositories.intake_extraction_repository import IntakeExtractionRepository

router = APIRouter()

# =========================================================
# DOCUMENTOS INCORPORADOS AL MOTOR DE REGLAS (RULE DOCUMENTS)
# (Deben preceder a /{rule_code} para evitar conflictos de routing)
# =========================================================

@router.get("/documents", response_model=List[RuleDocumentRead])
def list_rule_documents(
    discipline: Optional[str] = Query(None),
    document_type: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db)
):
    """Lista los documentos normativos y técnicos incorporados al Motor de Reglas QA/QC."""
    repo = IntakeExtractionRepository(db)
    return repo.list_rule_documents(
        discipline=discipline,
        document_type=document_type,
        status=status_filter
    )

@router.get("/documents/{doc_id}", response_model=RuleDocumentDetailRead)
def get_rule_document(doc_id: str, db: Session = Depends(get_db)):
    """Obtiene un documento de reglas con todos sus items estructurados (reglas, tablas, figuras)."""
    repo = IntakeExtractionRepository(db)
    doc = repo.get_rule_document_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento de reglas no encontrado.")
    return doc

@router.put("/documents/{doc_id}", response_model=RuleDocumentRead)
def update_rule_document(
    doc_id: str,
    payload: RuleDocumentUpdate,
    db: Session = Depends(get_db)
):
    """Actualiza los metadatos del documento de reglas (título, descripción, disciplina, versión, etc.)."""
    repo = IntakeExtractionRepository(db)
    doc = repo.update_rule_document(doc_id, payload.model_dump(exclude_unset=True))
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento de reglas no encontrado.")
    return doc

@router.delete("/documents/{doc_id}", status_code=status.HTTP_200_OK)
def delete_rule_document(doc_id: str, db: Session = Depends(get_db)):
    """Elimina un documento y sus reglas asociadas del Motor de Reglas."""
    repo = IntakeExtractionRepository(db)
    ok = repo.delete_rule_document(doc_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento de reglas no encontrado.")
    return {"message": "Documento de reglas eliminado exitosamente."}

@router.get("/documents/{doc_id}/items", response_model=List[RuleDocumentItemRead])
def list_rule_document_items(doc_id: str, db: Session = Depends(get_db)):
    """Obtiene los elementos específicos de un documento (para el modal 'Contenido')."""
    repo = IntakeExtractionRepository(db)
    return repo.get_rule_document_items(doc_id)

@router.put("/documents/{doc_id}/items/{item_id}", response_model=RuleDocumentItemRead)
def update_rule_document_item(
    doc_id: str,
    item_id: str,
    payload: RuleDocumentItemUpdate,
    db: Session = Depends(get_db)
):
    """Actualiza una regla o item específico dentro del documento normativo."""
    repo = IntakeExtractionRepository(db)
    item = repo.update_rule_document_item(item_id, payload.model_dump(exclude_unset=True))
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item de documento no encontrado.")
    return item

@router.delete("/documents/{doc_id}/items/{item_id}", status_code=status.HTTP_200_OK)
def delete_rule_document_item(
    doc_id: str,
    item_id: str,
    db: Session = Depends(get_db)
):
    """Elimina un elemento específico de un documento normativo."""
    repo = IntakeExtractionRepository(db)
    ok = repo.delete_rule_document_item(item_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item de documento no encontrado.")
    return {"message": "Item eliminado del documento exitosamente."}

@router.post("/documents/{doc_id}/confirm-content", response_model=ConfirmRuleDocumentContentResponse)
def confirm_rule_document_content(
    doc_id: str,
    payload: ConfirmRuleDocumentContentRequest,
    db: Session = Depends(get_db)
):
    """
    Confirma las reglas válidas dentro del contenido del documento normativo incorporado (Botón Aceptar dentro de Contenido).
    """
    repo = IntakeExtractionRepository(db)
    try:
        res = repo.confirm_rule_document_content(doc_id, payload.confirmed_item_ids)
        return ConfirmRuleDocumentContentResponse(**res)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error confirmando contenido: {str(e)}")

@router.post("/documents/{doc_id}/promote-to-baseline", response_model=PromoteToBaselineResponse)
def promote_rule_document_to_baseline(
    doc_id: str,
    db: Session = Depends(get_db)
):
    """
    Promueve las reglas confirmadas/validadas del documento normativo hacia el Baseline QA/QC del Sistema (Botón Aceptar del renglón).
    """
    repo = IntakeExtractionRepository(db)
    try:
        res = repo.promote_rule_document_to_baseline(doc_id)
        return PromoteToBaselineResponse(**res)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error promoviendo a baseline: {str(e)}")


# =========================================================
# REGLAS DETERMINÍSTICAS QA/QC DEL SISTEMA
# =========================================================

@router.get("", response_model=List[RuleDefinitionRead])
def list_rules(
    discipline: Optional[str] = Query(None, description="Filtrar por disciplina: architecture, electrical, general"),
    category: Optional[str] = Query(None, description="Filtrar por categoría"),
    db: Session = Depends(get_db)
):
    """Lista las definiciones de reglas QA/QC y normativas activas."""
    RuleRegistry.seed_database_definitions(db)
    query = db.query(RuleDefinition).filter(RuleDefinition.is_active == True)
    if discipline:
        query = query.filter(RuleDefinition.discipline == discipline)
    if category:
        query = query.filter(RuleDefinition.category == category)
    return query.all()

@router.get("/summary", response_model=RuleEvaluationSummaryResponse)
def get_rules_summary(
    document_id: Optional[str] = Query(None, description="Filtrar por ID de documento"),
    sheet_id: Optional[str] = Query(None, description="Filtrar por ID de lámina"),
    db: Session = Depends(get_db)
):
    """Obtiene el resumen de ejecuciones de reglas y conteo de hallazgos por severidad."""
    engine = RuleEngine(db)
    return engine.get_summary(document_id=document_id, sheet_id=sheet_id)

@router.post("/seed-defaults", response_model=List[RuleDefinitionRead])
def seed_default_rules(db: Session = Depends(get_db)):
    """Siembra y sincroniza las 6 reglas baseline determinísticas en la base de datos."""
    RuleRegistry.seed_database_definitions(db)
    return db.query(RuleDefinition).all()

@router.post("/sheets/{sheet_id}", response_model=List[RuleFindingRead])
def evaluate_sheet_rules_sync(sheet_id: str, db: Session = Depends(get_db)):
    """Ejecuta síncronamente todas las reglas determinísticas sobre una lámina y retorna los hallazgos."""
    engine = RuleEngine(db)
    try:
        return engine.evaluate_sheet(sheet_id=sheet_id)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error en evaluación de reglas: {str(e)}")

@router.post("/sheets/{sheet_id}/async", response_model=AsyncJobAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
def evaluate_sheet_rules_async(sheet_id: str, db: Session = Depends(get_db)):
    """Encola la evaluación de reglas determinísticas para una lámina (HTTP 202 Accepted)."""
    ops_svc = OperationsService(db)
    repo = DocumentRepository(db)
    sheet = repo.get_sheet_by_id(sheet_id)
    if not sheet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lámina '{sheet_id}' no encontrada.")

    job = ops_svc.submit_job(
        job_type="sheet_rules_eval",
        target_type="sheet",
        target_id=sheet_id,
        project_id=sheet.document.project_id if sheet.document else None,
        input_payload={},
        async_mode=True
    )
    return AsyncJobAcceptedResponse(
        job_id=job.id,
        status="queued",
        poll_url=f"/api/v1/jobs/{job.id}",
        message="Evaluación de reglas QA/QC para lámina encolada.",
        target_type="sheet",
        target_id=sheet_id
    )

@router.post("/documents/{document_id}/async", response_model=AsyncJobAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
def evaluate_document_rules_async(document_id: str, db: Session = Depends(get_db)):
    """Encola la evaluación de reglas determinísticas para todas las láminas de un documento (HTTP 202 Accepted)."""
    ops_svc = OperationsService(db)
    repo = DocumentRepository(db)
    doc = repo.get_by_id(document_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Documento '{document_id}' no encontrado.")

    job = ops_svc.submit_job(
        job_type="document_rules_eval",
        target_type="document",
        target_id=document_id,
        project_id=doc.project_id,
        input_payload={},
        async_mode=True
    )
    return AsyncJobAcceptedResponse(
        job_id=job.id,
        status="queued",
        poll_url=f"/api/v1/jobs/{job.id}",
        message="Evaluación de reglas QA/QC para documento encolada.",
        target_type="document",
        target_id=document_id
    )

@router.get("/{rule_code}", response_model=RuleDefinitionRead)
def get_rule_detail(rule_code: str, db: Session = Depends(get_db)):
    """Obtiene el detalle y especificación de requisitos de una regla determinística."""
    RuleRegistry.seed_database_definitions(db)
    rule = db.query(RuleDefinition).filter(RuleDefinition.code == rule_code).first()
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Regla '{rule_code}' no encontrada.")
    return rule
