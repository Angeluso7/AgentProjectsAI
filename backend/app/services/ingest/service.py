import os
import io
import hashlib
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from PIL import Image

from app.db.models.document_memory import Document, DocumentSheet, DocumentStructuralNode
from app.db.repositories.document_repository import DocumentRepository
from app.services.document_processing.docling_service import DoclingService
from app.services.cad.dxf_service import DxfService
from app.core.settings import settings
from app.core.logging import logger

try:
    import fitz  # PyMuPDF
    FITZ_AVAILABLE = True
except ImportError:
    FITZ_AVAILABLE = False
    logger.warning("PyMuPDF (fitz) no esta instalado en el entorno actual. Las operaciones de PDF requeriran instalacion.")

class IngestService:
    """Servicio responsable de la ingesta de documentos técnicos (PDF, Imágenes, CAD, Especificaciones),
    cálculo de hash SHA-256, extracción de metadatos, enumeración de hojas y rasterizado a imágenes de alta resolución.
    """

    def __init__(self, db: Session):
        self.db = db
        self.repo = DocumentRepository(db)
        self.docling_service = DoclingService()
        self.dxf_service = DxfService()

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitiza el nombre de archivo eliminando secuencias de path traversal y caracteres no deseados."""
        if not filename:
            return "unnamed_document.pdf"
        import re
        clean = os.path.basename(filename.replace("\\", "/").strip())
        clean = clean.replace("..", "").replace("\x00", "")
        clean = re.sub(r'[^\w\s\.-]', '_', clean)
        clean = clean.strip()
        return clean or "unnamed_document.pdf"

    def validate_file(self, filename: str, file_bytes: bytes, mime_type: Optional[str] = None):
        """Valida que el archivo no esté vacío, no supere MAX_UPLOAD_SIZE_MB y su formato sea admitido."""
        if not file_bytes or len(file_bytes) == 0:
            raise ValueError(f"El archivo '{filename}' está vacío.")

        max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        if len(file_bytes) > max_bytes:
            raise ValueError(
                f"El archivo '{filename}' ({len(file_bytes) / (1024*1024):.2f} MB) excede el tamaño máximo permitido de {settings.MAX_UPLOAD_SIZE_MB} MB."
            )

        lower_name = filename.lower()
        has_allowed_ext = any(lower_name.endswith(ext) for ext in settings.ALLOWED_EXTENSIONS)
        if not has_allowed_ext:
            if not file_bytes.startswith(b"%PDF-"):
                raise ValueError(
                    f"Tipo de archivo no permitido para '{filename}'. Formatos aceptados: {', '.join(settings.ALLOWED_EXTENSIONS[:8])}..."
                )

    def calculate_file_hash(self, file_bytes: bytes) -> str:
        """Calcula el hash SHA-256 en chunks para prevenir sobrecarga de memoria."""
        hasher = hashlib.sha256()
        chunk_size = 65536
        for i in range(0, len(file_bytes), chunk_size):
            hasher.update(file_bytes[i:i + chunk_size])
        return hasher.hexdigest()

    def _resolve_organization_id(self, project_id: str) -> str:
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
        return org_id

    def ingest_file(
        self,
        project_id: str,
        filename: str,
        file_bytes: bytes,
        version_id: Optional[str] = None,
        auto_process: bool = True,
        dpi: Optional[int] = None,
        metadata_extra: Optional[Dict[str, Any]] = None
    ) -> Document:
        """Ingesta cualquier tipo de archivo técnico delegando según formato."""
        clean_filename = self.sanitize_filename(filename)
        self.validate_file(clean_filename, file_bytes)

        lower_name = clean_filename.lower()
        
        # 1. Si es PDF o contiene encabezado PDF
        if lower_name.endswith(".pdf") or file_bytes.startswith(b"%PDF-"):
            return self.ingest_pdf(
                project_id=project_id,
                filename=clean_filename,
                file_bytes=file_bytes,
                version_id=version_id,
                auto_process=auto_process,
                dpi=dpi,
                metadata_extra=metadata_extra
            )

        # 2. Si es imagen raster (PNG, JPG, JPEG, WEBP, BMP, TIFF)
        image_extensions = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff")
        if lower_name.endswith(image_extensions):
            return self.ingest_image(
                project_id=project_id,
                filename=clean_filename,
                file_bytes=file_bytes,
                version_id=version_id,
                dpi=dpi,
                metadata_extra=metadata_extra
            )

        # 3. Si es otro archivo técnico (CAD, DXF, DWG, DOCX, XLSX, TXT, CSV, etc.)
        return self.ingest_generic_doc(
            project_id=project_id,
            filename=clean_filename,
            file_bytes=file_bytes,
            version_id=version_id,
            metadata_extra=metadata_extra
        )

    def ingest_image(
        self,
        project_id: str,
        filename: str,
        file_bytes: bytes,
        version_id: Optional[str] = None,
        dpi: Optional[int] = None,
        metadata_extra: Optional[Dict[str, Any]] = None
    ) -> Document:
        """Ingesta una imagen de plano/croquis, creando una lámina lista para el visor."""
        file_hash = self.calculate_file_hash(file_bytes)
        
        # Verificar duplicado exclusivamente en el ámbito del proyecto
        existing = self.repo.get_by_project_and_hash(project_id, file_hash)
        if existing:
            logger.info(f"Imagen '{filename}' ya existe en el proyecto {project_id} con hash: {file_hash} (ID: {existing.id})")
            return existing

        try:
            pil_img = Image.open(io.BytesIO(file_bytes))
            width_px, height_px = pil_img.size
            img_format = (pil_img.format or "PNG").upper()
            mime_type = f"image/{img_format.lower()}"
        except Exception as e:
            raise ValueError(f"No se pudo decodificar la imagen '{filename}': {str(e)}")

        # Guardar archivo original
        os.makedirs(settings.RAW_DOCUMENTS_DIR, exist_ok=True)
        target_path = os.path.join(settings.RAW_DOCUMENTS_DIR, f"{file_hash}_{filename}")
        with open(target_path, "wb") as f:
            f.write(file_bytes)

        org_id = self._resolve_organization_id(project_id)
        target_dpi = dpi or settings.DEFAULT_RENDER_DPI

        doc = Document(
            organization_id=org_id,
            project_id=project_id,
            project_version_id=version_id,
            filename=filename,
            file_path=target_path,
            file_hash_sha256=file_hash,
            file_size_bytes=len(file_bytes),
            mime_type=mime_type,
            status="ready",
            page_count=1,
            metadata_info=metadata_extra or {}
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)

        # Generar lámina renderizada y thumbnail
        os.makedirs(settings.RENDERED_SHEETS_DIR, exist_ok=True)
        raster_filename = f"{doc.id}_sheet_1.png"
        raster_path = os.path.join(settings.RENDERED_SHEETS_DIR, raster_filename)
        pil_img.convert("RGB").save(raster_path, "PNG")

        thumb_filename = f"{doc.id}_sheet_1_thumb.png"
        thumb_path = os.path.join(settings.RENDERED_SHEETS_DIR, thumb_filename)
        thumb_img = pil_img.copy()
        thumb_img.thumbnail((300, 300))
        thumb_img.convert("RGB").save(thumb_path, "PNG")

        # Calcular dimensiones físicas estimadas a target_dpi
        width_mm = round(width_px * 25.4 / target_dpi, 2)
        height_mm = round(height_px * 25.4 / target_dpi, 2)

        sheet = DocumentSheet(
            document_id=doc.id,
            sheet_number=1,
            sheet_code="IMG-01",
            title=filename,
            width_px=width_px,
            height_px=height_px,
            width_mm=width_mm,
            height_mm=height_mm,
            dpi=target_dpi,
            raster_image_path=raster_path,
            thumbnail_path=thumb_path
        )
        self.db.add(sheet)
        self.db.commit()
        self.db.refresh(doc)
        logger.info(f"Imagen técnica ingresada e indexada: {doc.filename} (ID: {doc.id})")
        return doc

    def ingest_generic_doc(
        self,
        project_id: str,
        filename: str,
        file_bytes: bytes,
        version_id: Optional[str] = None,
        metadata_extra: Optional[Dict[str, Any]] = None
    ) -> Document:
        """Ingesta un documento técnico no gráfico (CAD, especificación, cálculo)."""
        file_hash = self.calculate_file_hash(file_bytes)
        
        # Verificar duplicado exclusivamente en el ámbito del proyecto
        existing = self.repo.get_by_project_and_hash(project_id, file_hash)
        if existing:
            logger.info(f"Documento '{filename}' ya existe en el proyecto {project_id} con hash: {file_hash} (ID: {existing.id})")
            return existing

        # Determinar mime_type según extensión
        lower_name = (filename or "").lower()
        if lower_name.endswith((".dxf", ".dwg")):
            mime_type = "application/acad"
        elif lower_name.endswith((".docx", ".doc")):
            mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        elif lower_name.endswith((".xlsx", ".xls")):
            mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        elif lower_name.endswith(".csv"):
            mime_type = "text/csv"
        elif lower_name.endswith(".txt"):
            mime_type = "text/plain"
        elif lower_name.endswith(".zip"):
            mime_type = "application/zip"
        else:
            mime_type = "application/octet-stream"

        # Guardar archivo original en directorio raw
        os.makedirs(settings.RAW_DOCUMENTS_DIR, exist_ok=True)
        target_path = os.path.join(settings.RAW_DOCUMENTS_DIR, f"{file_hash}_{filename}")
        with open(target_path, "wb") as f:
            f.write(file_bytes)

        org_id = self._resolve_organization_id(project_id)

        doc = Document(
            organization_id=org_id,
            project_id=project_id,
            project_version_id=version_id,
            filename=filename,
            file_path=target_path,
            file_hash_sha256=file_hash,
            file_size_bytes=len(file_bytes),
            mime_type=mime_type,
            status="ready",
            page_count=1,
            metadata_info=metadata_extra or {}
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)

        # Extracción estructural (Docling / ezdxf)
        try:
            if lower_name.endswith(".dxf"):
                nodes = self.dxf_service.extract_structural_nodes(file_bytes, filename, doc.id)
                if nodes:
                    self.db.add_all(nodes)
                    self.db.commit()
            elif lower_name.endswith((".docx", ".doc", ".xlsx", ".xls", ".csv", ".txt")):
                nodes = self.docling_service.extract_structural_nodes(file_bytes, filename, doc.id)
                if nodes:
                    self.db.add_all(nodes)
                    self.db.commit()
        except Exception as e:
            logger.warning(f"Extracción estructural secundaria para '{filename}' registró excepción: {e}")

        logger.info(f"Documento técnico entregable registrado: {doc.filename} (ID: {doc.id})")
        return doc

    def ingest_pdf(
        self,
        project_id: str,
        filename: str,
        file_bytes: bytes,
        version_id: Optional[str] = None,
        auto_process: bool = True,
        dpi: Optional[int] = None,
        metadata_extra: Optional[Dict[str, Any]] = None
    ) -> Document:
        """Ingesta un archivo PDF: valida contenido, guarda en disco, registra en BD y opcionalmente procesa."""
        if not file_bytes:
            raise ValueError("El archivo proporcionado está vacío.")

        # Validación básica de cabecera PDF (%PDF-)
        if not file_bytes.startswith(b"%PDF-"):
            raise ValueError(f"El archivo '{filename}' no tiene formato PDF válido.")

        file_hash = self.calculate_file_hash(file_bytes)
        
        # Verificar si ya existe el documento con el mismo hash dentro de este proyecto
        existing = self.repo.get_by_project_and_hash(project_id, file_hash)
        if existing:
            logger.info(f"Documento '{filename}' ya existe en el proyecto {project_id} con hash: {file_hash} (ID: {existing.id})")
            if auto_process and existing.status in ["uploaded", "failed"]:
                return self.process_document(existing.id, dpi=dpi)
            return existing

        # Guardar archivo original en directorio raw
        os.makedirs(settings.RAW_DOCUMENTS_DIR, exist_ok=True)
        target_path = os.path.join(settings.RAW_DOCUMENTS_DIR, f"{file_hash}_{filename}")
        with open(target_path, "wb") as f:
            f.write(file_bytes)

        org_id = self._resolve_organization_id(project_id)

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
            page_count=1,
            metadata_info=metadata_extra or {}
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        logger.info(f"Documento registrado exitosamente: {doc.filename} (ID: {doc.id})")

        # Disparar procesamiento / rasterizado síncrono si está habilitado
        if auto_process:
            try:
                return self.process_document(doc.id, dpi=dpi)
            except Exception as e:
                logger.error(f"Error procesando documento {doc.id} tras ingesta: {e}")
                doc.status = "failed"
                doc.error_message = str(e)
                self.db.commit()
                self.db.refresh(doc)
                return doc

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

            # Extracción estructural de secciones y tablas con Docling
            try:
                if os.path.exists(doc.file_path):
                    with open(doc.file_path, "rb") as f:
                        raw_bytes = f.read()
                    nodes = self.docling_service.extract_structural_nodes(raw_bytes, doc.filename, doc.id)
                    if nodes:
                        self.db.add_all(nodes)
                        self.db.commit()
            except Exception as e:
                logger.warning(f"Extracción de secciones/tablas PDF falló para '{doc.filename}': {e}")

            logger.info(f"Documento procesado exitosamente: {doc.filename} ({page_count} hojas rasterizadas a {target_dpi} DPI)")
            return doc

        except Exception as e:
            logger.error(f"Error procesando documento {doc.filename}: {e}", exc_info=True)
            doc.status = "failed"
            doc.error_message = str(e)
            self.db.commit()
            raise e
