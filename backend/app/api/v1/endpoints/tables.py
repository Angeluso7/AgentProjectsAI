from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.repositories.document_repository import DocumentRepository
from app.schemas.table import ExtractedTableRead, ExtractedTableCellRead, TableExtractProcessRequest
from app.schemas.operations import AsyncJobAcceptedResponse
from app.services.tables.service import TableService
from app.services.operations.service import OperationsService

router = APIRouter()

@router.get("/sheets/{sheet_id}", response_model=List[ExtractedTableRead])
def list_sheet_tables(sheet_id: str, db: Session = Depends(get_db)):
    """Lista las tablas técnicas extraídas pertenecientes a una lámina."""
    service = TableService(db)
    return service.list_tables_by_sheet(sheet_id)

@router.get("/{table_id}", response_model=ExtractedTableRead)
def get_table_detail(table_id: str, db: Session = Depends(get_db)):
    """Obtiene el detalle de una tabla técnica, incluyendo sus celdas estructuradas."""
    service = TableService(db)
    table = service.get_table(table_id)
    if not table:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Tabla '{table_id}' no encontrada.")
    return table

@router.get("/{table_id}/cells", response_model=List[ExtractedTableCellRead])
def list_table_cells(table_id: str, db: Session = Depends(get_db)):
    """Obtiene todas las celdas de una tabla ordenadas por fila y columna."""
    service = TableService(db)
    table = service.get_table(table_id)
    if not table:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Tabla '{table_id}' no encontrada.")
    return service.list_cells_by_table(table_id)

@router.post("/sheets/{sheet_id}", response_model=List[ExtractedTableRead])
def extract_sheet_tables_sync(
    sheet_id: str,
    request: Optional[TableExtractProcessRequest] = None,
    db: Session = Depends(get_db)
):
    """Ejecuta extracción síncrona de tablas sobre las regiones table_candidate de una lámina."""
    service = TableService(db)
    force = request.force_reprocess if request else False
    region_id = request.region_id if request else None

    try:
        return service.extract_tables_from_sheet(sheet_id=sheet_id, force_reprocess=force, region_id=region_id)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error en extracción tabular: {str(e)}")

@router.post("/sheets/{sheet_id}/async", response_model=AsyncJobAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
def extract_sheet_tables_async(
    sheet_id: str,
    request: Optional[TableExtractProcessRequest] = None,
    db: Session = Depends(get_db)
):
    """Encola extracción tabular asíncrona para una lámina (HTTP 202 Accepted)."""
    ops_svc = OperationsService(db)
    repo = DocumentRepository(db)
    sheet = repo.get_sheet_by_id(sheet_id)
    if not sheet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lámina '{sheet_id}' no encontrada.")

    job = ops_svc.submit_job(
        job_type="sheet_table_extract",
        target_type="sheet",
        target_id=sheet_id,
        project_id=sheet.document.project_id if sheet.document else None,
        input_payload=request.model_dump() if request else {},
        async_mode=True
    )
    return AsyncJobAcceptedResponse(
        job_id=job.id,
        status="queued",
        poll_url=f"/api/v1/jobs/{job.id}",
        message="Extracción tabular de lámina encolada para procesamiento asíncrono.",
        target_type="sheet",
        target_id=sheet_id
    )

@router.post("/documents/{document_id}/async", response_model=AsyncJobAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
def extract_document_tables_async(
    document_id: str,
    request: Optional[TableExtractProcessRequest] = None,
    db: Session = Depends(get_db)
):
    """Encola extracción tabular asíncrona para todas las hojas de un documento (HTTP 202 Accepted)."""
    ops_svc = OperationsService(db)
    repo = DocumentRepository(db)
    doc = repo.get_by_id(document_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Documento '{document_id}' no encontrado.")

    job = ops_svc.submit_job(
        job_type="document_table_extract",
        target_type="document",
        target_id=document_id,
        project_id=doc.project_id,
        input_payload=request.model_dump() if request else {},
        async_mode=True
    )
    return AsyncJobAcceptedResponse(
        job_id=job.id,
        status="queued",
        poll_url=f"/api/v1/jobs/{job.id}",
        message="Extracción tabular de documento encolada para procesamiento asíncrono.",
        target_type="document",
        target_id=document_id
    )
