import os
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, status
from fastapi.responses import JSONResponse, FileResponse
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models.document_memory import Document, DocumentStructuralNode
from app.db.repositories.document_repository import DocumentRepository
from app.db.repositories.project_repository import ProjectRepository
from app.schemas.document import (
    DocumentRead, DocumentUploadResponse, DocumentSheetRead, DocumentProcessRequest,
    BatchUploadResponse, BatchFileResultItem,
    DocumentStructuralNodeRead, CadEntitiesSummaryRead
)
from app.services.ingest.service import IngestService
from app.services.cad.dxf_service import DxfService
from app.core.deps import get_current_tenant, require_role, TenantContext

router = APIRouter()

@router.get("", response_model=List[DocumentRead], include_in_schema=False)
@router.get("/", response_model=List[DocumentRead])
def list_documents(
    project_id: Optional[str] = None,
    include_archived: bool = Query(False, description="Incluir documentos archivados"),
    db: Session = Depends(get_db)
):
    """Lista los documentos cargados, opcionalmente filtrados por proyecto."""
    query = db.query(Document)
    if not include_archived:
        query = query.filter(Document.status != "archived")
    if project_id:
        query = query.filter(Document.project_id == project_id)
    return query.order_by(Document.created_at.desc()).all()


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    project_id: str = Form(...),
    file: UploadFile = File(...),
    version_id: Optional[str] = Form(None),
    discipline: Optional[str] = Form(None),
    document_type: Optional[str] = Form(None),
    evidence_classification: Optional[str] = Form(None),
    execution_mode: Optional[str] = Form(None),
    metadata_json: Optional[str] = Form(None),
    auto_process: bool = Form(True),
    dpi: Optional[int] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Carga un archivo técnico (PDF, imagen, CAD, especificación):
    Valida tipo y tamaño, calcula hash SHA-256 en chunks, persiste en volumen y BD,
    y ejecuta rasterizado / extracción estructural según corresponda.
    """
    proj_repo = ProjectRepository(db)
    project = proj_repo.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proyecto no encontrado")

    if not file or not file.filename:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "code": "UPLOAD_VALIDATION_ERROR",
                "message": "Archivo no enviado o nombre de archivo vacío.",
                "detail": "Archivo no enviado o nombre de archivo vacío.",
                "details": {"field": "file", "reason": "No se recibió archivo válido."}
            }
        )

    content = await file.read()
    if not content or len(content) == 0:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "code": "UPLOAD_VALIDATION_ERROR",
                "message": "El archivo subido está vacío.",
                "detail": "El archivo subido está vacío.",
                "details": {"field": "file", "reason": "El archivo subido está vacío."}
            }
        )

    filename_lower = (file.filename or "").lower()
    allowed_extensions = (".pdf", ".dxf", ".dwg", ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".xlsx", ".csv", ".docx")
    if not any(filename_lower.endswith(ext) for ext in allowed_extensions) or filename_lower.endswith(".txt"):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "code": "UPLOAD_VALIDATION_ERROR",
                "message": "Tipo de archivo no permitido. El archivo no tiene formato PDF válido o extensión técnica soportada.",
                "detail": "Tipo de archivo no permitido. El archivo no tiene formato PDF válido o extensión técnica soportada.",
                "details": {"field": "file", "reason": "Extensión no permitida"}
            }
        )

    ingest_svc = IngestService(db)

    # Procesar metadatos adicionales
    meta_extra: dict = {}
    if metadata_json:
        try:
            import json
            parsed = json.loads(metadata_json)
            if isinstance(parsed, dict):
                meta_extra.update(parsed)
        except Exception:
            meta_extra["raw_metadata"] = metadata_json

    if discipline:
        meta_extra["discipline"] = discipline
    if document_type:
        meta_extra["document_type"] = document_type
    if evidence_classification:
        meta_extra["evidence_classification"] = evidence_classification
    if execution_mode:
        meta_extra["execution_mode"] = execution_mode

    try:
        doc = ingest_svc.ingest_file(
            project_id=project_id,
            filename=file.filename or "document.pdf",
            file_bytes=content,
            version_id=version_id,
            auto_process=auto_process,
            dpi=dpi,
            metadata_extra=meta_extra
        )

        warnings = []
        if doc.status == "failed" and doc.error_message:
            warnings.append(f"Procesamiento falló: {doc.error_message}")

        return DocumentUploadResponse(
            document_id=doc.id,
            id=doc.id,
            filename=doc.filename,
            content_type=doc.mime_type,
            mime_type=doc.mime_type,
            size_bytes=doc.file_size_bytes,
            file_size_bytes=doc.file_size_bytes,
            sha256=doc.file_hash_sha256,
            file_hash_sha256=doc.file_hash_sha256,
            storage_status="stored",
            processing_status=doc.status,
            status=doc.status,
            upload_timestamp=doc.created_at,
            created_at=doc.created_at,
            project_id=doc.project_id,
            discipline=discipline,
            document_type=document_type,
            evidence_classification=evidence_classification,
            execution_mode=execution_mode,
            warnings=warnings,
            page_count=doc.page_count or 1,
            sheets=doc.sheets or [],
            error_message=doc.error_message
        )
    except ValueError as ve:
        err_msg = str(ve)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "code": "UPLOAD_VALIDATION_ERROR",
                "message": err_msg,
                "detail": err_msg,
                "details": {"field": "file", "reason": err_msg}
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error durante la ingesta: {str(e)}"
        )


@router.post("/batch-upload", response_model=BatchUploadResponse, status_code=status.HTTP_201_CREATED)
async def batch_upload_documents(
    project_id: str = Form(...),
    version_id: Optional[str] = Form(None),
    auto_process: bool = Form(True),
    dpi: Optional[int] = Form(None),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    """
    Carga por lotes de documentos y planos técnicos:
    Procesa múltiples archivos registrando cada uno de forma individual dentro del proyecto.
    Un fallo en un archivo individual no aborta la carga del resto del lote.
    """
    proj_repo = ProjectRepository(db)
    project = proj_repo.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proyecto no encontrado")

    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No se enviaron archivos para la carga por lotes.")

    ingest_svc = IngestService(db)
    documents: List[Document] = []
    results: List[BatchFileResultItem] = []
    successful_count = 0
    duplicated_count = 0
    failed_count = 0

    for upload_file in files:
        filename = upload_file.filename or "unnamed_file"
        try:
            content = await upload_file.read()
            if not content:
                failed_count += 1
                results.append(BatchFileResultItem(
                    filename=filename,
                    status="failed",
                    error_message="El archivo está vacío."
                ))
                continue

            file_hash = ingest_svc.calculate_file_hash(content)
            existing = ingest_svc.repo.get_by_project_and_hash(project_id, file_hash)
            is_duplicate = existing is not None

            doc = ingest_svc.ingest_file(
                project_id=project_id,
                filename=filename,
                file_bytes=content,
                version_id=version_id,
                auto_process=auto_process,
                dpi=dpi
            )

            if is_duplicate:
                duplicated_count += 1
                status_label = "already_exists"
            else:
                successful_count += 1
                status_label = "ready" if doc.status == "ready" else "uploaded"

            documents.append(doc)
            results.append(BatchFileResultItem(
                filename=filename,
                status=status_label,
                document_id=doc.id,
                file_size_bytes=len(content),
                mime_type=doc.mime_type,
                page_count=doc.page_count or 1,
                sheets_count=len(doc.sheets) if doc.sheets else 0,
                error_message=None
            ))
        except Exception as err:
            failed_count += 1
            results.append(BatchFileResultItem(
                filename=filename,
                status="failed",
                error_message=str(err)
            ))

    return BatchUploadResponse(
        project_id=project_id,
        total_files=len(files),
        successful_count=successful_count,
        duplicated_count=duplicated_count,
        failed_count=failed_count,
        documents=documents,
        results=results
    )


@router.get("/{document_id}", response_model=DocumentRead)
def get_document(document_id: str, db: Session = Depends(get_db)):
    """Obtiene el detalle de un documento y sus hojas asociadas."""
    repo = DocumentRepository(db)
    doc = repo.get_by_id(document_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento no encontrado")
    return doc

@router.get("/{document_id}/sheets", response_model=List[DocumentSheetRead])
def list_document_sheets(document_id: str, db: Session = Depends(get_db)):
    """Lista todas las hojas o planos rasterizados de un documento."""
    repo = DocumentRepository(db)
    doc = repo.get_by_id(document_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento no encontrado")
    return repo.list_sheets_by_document(document_id)

@router.get("/sheets/{sheet_id}/image")
def get_sheet_image(sheet_id: str, db: Session = Depends(get_db)):
    """Retorna la imagen rasterizada maestra de la lámina técnica."""
    from fastapi.responses import FileResponse
    repo = DocumentRepository(db)
    sheet = repo.get_sheet_by_id(sheet_id)
    if not sheet or not sheet.raster_image_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lámina no encontrada o sin imagen rasterizada.")
    
    clean_path = sheet.raster_image_path
    if not os.path.isabs(clean_path):
        clean_path = os.path.normpath(clean_path)
    
    if not os.path.exists(clean_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Archivo raster no encontrado en disco: {sheet.raster_image_path}")
    
    return FileResponse(clean_path, media_type="image/png")

@router.get("/sheets/{sheet_id}/thumbnail")
def get_sheet_thumbnail(sheet_id: str, db: Session = Depends(get_db)):
    """Retorna la miniatura o thumbnail de la lámina técnica."""
    from fastapi.responses import FileResponse
    repo = DocumentRepository(db)
    sheet = repo.get_sheet_by_id(sheet_id)
    if not sheet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lámina no encontrada.")
    
    target_path = sheet.thumbnail_path or sheet.raster_image_path
    if not target_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sin archivo visual disponible.")
    
    clean_path = os.path.normpath(target_path) if not os.path.isabs(target_path) else target_path
    if not os.path.exists(clean_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Archivo thumbnail no encontrado en disco: {target_path}")
    
    return FileResponse(clean_path, media_type="image/png")

@router.post("/{document_id}/process", response_model=DocumentRead)
def process_document(
    document_id: str,
    request: Optional[DocumentProcessRequest] = None,
    db: Session = Depends(get_db)
):
    """Dispara el procesamiento / rasterizado manual o reprocesamiento de un documento."""
    ingest_svc = IngestService(db)
    target_dpi = request.dpi if request else None
    try:
        return ingest_svc.process_document(document_id=document_id, dpi=target_dpi)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error procesando documento: {str(e)}")

@router.get("/{document_id}/impact")
def get_document_impact(
    document_id: str,
    db: Session = Depends(get_db),
    tenant_ctx: TenantContext = Depends(get_current_tenant)
):
    """Obtiene el desglose de impacto de un documento antes de su eliminación o archivado."""
    repo = DocumentRepository(db)
    doc = repo.get_by_id(document_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento no encontrado.")
    
    # Validar tenant
    if not tenant_ctx.user.is_superuser and doc.organization_id != tenant_ctx.organization.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: El documento pertenece a otra organización."
        )

    impact = repo.get_impact_analysis(document_id)
    if not impact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No se pudo calcular el impacto del documento.")
    return impact

@router.get("/{document_id}/structural-nodes", response_model=List[DocumentStructuralNodeRead])
def get_document_structural_nodes(
    document_id: str,
    db: Session = Depends(get_db)
):
    """Retorna la jerarquía de secciones, tablas y notas extraídas por Docling/DXF."""
    repo = DocumentRepository(db)
    doc = repo.get_by_id(document_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento no encontrado.")
    
    nodes = db.query(DocumentStructuralNode).filter(
        DocumentStructuralNode.document_id == document_id
    ).order_by(DocumentStructuralNode.page_number.asc(), DocumentStructuralNode.level.asc()).all()
    return nodes

@router.get("/{document_id}/cad-entities", response_model=CadEntitiesSummaryRead)
def get_document_cad_entities(
    document_id: str,
    db: Session = Depends(get_db)
):
    """Retorna el resumen de entidades CAD (capas, bloques con atributos y textos) para un archivo DXF."""
    repo = DocumentRepository(db)
    doc = repo.get_by_id(document_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento no encontrado.")
    
    if not doc.filename.lower().endswith(".dxf"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El documento no es un archivo CAD DXF.")

    if not os.path.exists(doc.file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archivo binario DXF no encontrado en disco.")

    with open(doc.file_path, "rb") as f:
        file_bytes = f.read()

    dxf_svc = DxfService()
    return dxf_svc.parse_dxf_summary(file_bytes, doc.filename)

@router.delete("/{document_id}")
def delete_document(
    document_id: str,
    hard_delete: bool = Query(False, description="Si es True, realiza eliminación definitiva y física"),
    db: Session = Depends(get_db),
    tenant_ctx: TenantContext = Depends(require_role(["admin", "audit_lead", "reviewer"]))
):
    """
    Elimina o archiva un documento y limpia sus entidades dependientes de forma transaccional.
    - Soft-delete (por defecto): status = 'archived', preserva trazabilidad y archiva hallazgos.
    - Hard-delete: solo rol admin, purga registros dependientes y archivos en disco.
    """
    repo = DocumentRepository(db)
    doc = repo.get_by_id(document_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento no encontrado.")

    # Validar tenant
    if not tenant_ctx.user.is_superuser and doc.organization_id != tenant_ctx.organization.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: El documento pertenece a otra organización."
        )

    user_id = tenant_ctx.user.id

    if hard_delete:
        # Validar permiso de admin para hard-delete
        if not tenant_ctx.user.is_superuser and tenant_ctx.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permiso denegado: Solo usuarios con rol 'admin' pueden realizar la eliminación definitiva (hard-delete)."
            )
        result = repo.hard_delete_document(document_id=document_id, user_id=user_id)
        if not result:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Fallo durante la eliminación definitiva del documento.")
        return result
    else:
        archived_doc = repo.soft_delete_document(document_id=document_id, user_id=user_id)
        if not archived_doc:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Fallo al archivar el documento.")
        return {
            "success": True,
            "document_id": document_id,
            "delete_type": "soft_delete",
            "status": "archived",
            "message": f"Documento '{archived_doc.filename}' archivado exitosamente."
        }

