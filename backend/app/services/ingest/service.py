import os
import hashlib
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.db.models.document_memory import Document, DocumentSheet
from app.db.repositories.document_repository import DocumentRepository
from app.core.settings import settings
from app.core.logging import logger

try:
    import fitz  # PyMuPDF
    FITZ_AVAILABLE = True
except ImportError:
    FITZ_AVAILABLE = False
    logger.warning("PyMuPDF (fitz) no esta instalado en el entorno actual. Las operaciones de PDF requeriran instalacion.")

class IngestService:
    """Servicio responsable de la ingesta de documentos PDF, cálculo de hash SHA-256,
    extracción de metadatos, enumeración de hojas y rasterizado a imágenes de alta resolución.
    """

    def __init__(self, db: Session):
        self.db = db
        self.repo = DocumentRepository(db)

    def calculate_file_hash(self, file_bytes: bytes) -> str:
        """Calcula el hash SHA-256 del contenido binario de un archivo."""
        return hashlib.sha256(file_bytes).hexdigest()

    def ingest_pdf(
        self,
        project_id: str,
        filename: str,
        file_bytes: bytes,
        version_id: Optional[str] = None,
        auto_process: bool = True,
        dpi: Optional[int] = None
    ) -> Document:
        """Ingesta un archivo PDF: valida contenido, guarda en disco, registra en BD y opcionalmente procesa."""
        if not file_bytes:
            raise ValueError("El archivo proporcionado está vacío.")

        # Validación básica de cabecera PDF (%PDF-)
        if not file_bytes.startswith(b"%PDF-"):
            raise ValueError(f"El archivo '{filename}' no tiene formato PDF válido.")

        file_hash = self.calculate_file_hash(file_bytes)
        
        # Verificar si ya existe el documento con el mismo hash en la base de datos
        existing = self.repo.get_by_hash(file_hash)
        if existing:
            logger.info(f"Documento '{filename}' ya existe con hash SHA-256: {file_hash} (ID: {existing.id})")
            if auto_process and existing.status in ["uploaded", "failed"]:
                return self.process_document(existing.id, dpi=dpi)
            return existing

        # Guardar archivo original en directorio raw
        os.makedirs(settings.RAW_DOCUMENTS_DIR, exist_ok=True)
        target_path = os.path.join(settings.RAW_DOCUMENTS_DIR, f"{file_hash}_{filename}")
        with open(target_path, "wb") as f:
            f.write(file_bytes)

        # Resolver organization_id a partir del proyecto
        from app.db.models.core import Project, Organization
        project = self.db.query(Project).filter(Project.id == project_id).first()
        org_id = project.organization_id if project else None
        if not org_id:
            org = self.db.query(Organization).first()
            if org:
                org_id = org.id
            else:
                import uuid
                default_org = Organization(id=str(uuid.uuid4()), name="Default Organization", slug="default-org")
                self.db.add(default_org)
                self.db.commit()
                self.db.refresh(default_org)
                org_id = default_org.id

        # Crear registro de documento
        doc = Document(
            organization_id=org_id,
            project_id=project_id,
            project_version_id=version_id,
            filename=filename,
            file_path=target_path,
            file_hash_sha256=file_hash,
            file_size_bytes=len(file_bytes),
            mime_type="application/pdf",
            status="uploaded",
            page_count=1
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        logger.info(f"Documento registrado exitosamente: {doc.filename} (ID: {doc.id})")

        # Disparar procesamiento / rasterizado síncrono si está habilitado
        if auto_process:
            return self.process_document(doc.id, dpi=dpi)

        return doc

    def process_document(self, document_id: str, dpi: Optional[int] = None) -> Document:
        """Procesa un PDF con PyMuPDF: extrae metadatos, enumera páginas y rasteriza cada hoja a imagen."""
        doc = self.repo.get_by_id(document_id)
        if not doc:
            raise ValueError(f"Documento con ID {document_id} no encontrado.")

        if not os.path.exists(doc.file_path):
            doc.status = "failed"
            self.db.commit()
            raise FileNotFoundError(f"Archivo no encontrado en ruta: {doc.file_path}")

        if not FITZ_AVAILABLE:
            error_msg = "PyMuPDF (fitz) no disponible para rasterizado de PDF."
            doc.status = "failed"
            self.db.commit()
            raise RuntimeError(error_msg)

        target_dpi = dpi or settings.DEFAULT_RENDER_DPI
        os.makedirs(settings.RENDERED_SHEETS_DIR, exist_ok=True)

        try:
            doc.status = "processing"
            self.db.commit()

            fitz_doc = fitz.open(doc.file_path)
            page_count = len(fitz_doc)
            if page_count == 0:
                raise ValueError("El archivo PDF no contiene páginas legibles.")

            # Extraer metadatos de PyMuPDF
            raw_meta = fitz_doc.metadata or {}

            # Limpiar hojas existentes si es un reprocesamiento
            self.repo.delete_sheets_by_document(doc.id)

            # Rasterizar cada página
            for page_idx in range(page_count):
                page = fitz_doc[page_idx]
                sheet_number = page_idx + 1

                # Dimensiones físicas en puntos tipográficos (72 pt = 1 pulgada = 25.4 mm)
                width_pt = page.rect.width
                height_pt = page.rect.height
                width_mm = round(width_pt * 25.4 / 72.0, 2)
                height_mm = round(height_pt * 25.4 / 72.0, 2)

                # Rasterizado a imagen maestra según DPI configurado
                zoom = target_dpi / 72.0
                matrix = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=matrix, alpha=False)
                
                raster_filename = f"{doc.id}_sheet_{sheet_number}.png"
                raster_path = os.path.join(settings.RENDERED_SHEETS_DIR, raster_filename)
                pix.save(raster_path)
                width_px = pix.width
                height_px = pix.height

                # Rasterizado de thumbnail a baja resolución
                thumb_zoom = settings.THUMBNAIL_RENDER_DPI / 72.0
                thumb_matrix = fitz.Matrix(thumb_zoom, thumb_zoom)
                thumb_pix = page.get_pixmap(matrix=thumb_matrix, alpha=False)
                
                thumb_filename = f"{doc.id}_sheet_{sheet_number}_thumb.png"
                thumb_path = os.path.join(settings.RENDERED_SHEETS_DIR, thumb_filename)
                thumb_pix.save(thumb_path)

                # Crear registro persistido de la hoja
                sheet = DocumentSheet(
                    document_id=doc.id,
                    sheet_number=sheet_number,
                    sheet_code=f"SHEET-{sheet_number:02d}",
                    title=raw_meta.get("title") or f"Lámina {sheet_number}",
                    width_px=width_px,
                    height_px=height_px,
                    width_mm=width_mm,
                    height_mm=height_mm,
                    dpi=target_dpi,
                    raster_image_path=raster_path,
                    thumbnail_path=thumb_path
                )
                self.db.add(sheet)

            fitz_doc.close()

            # Actualizar documento maestro
            doc.page_count = page_count
            doc.status = "ready"
            doc.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(doc)

            logger.info(f"Documento procesado exitosamente: {doc.filename} ({page_count} hojas rasterizadas a {target_dpi} DPI)")
            return doc

        except Exception as e:
            logger.error(f"Error procesando documento {doc.filename}: {e}", exc_info=True)
            doc.status = "failed"
            self.db.commit()
            raise e
