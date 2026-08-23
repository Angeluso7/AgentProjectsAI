import os
import uuid
import hashlib
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.db.models.intake import SourceAsset
from app.db.models.normative_memory import NormativeDocument, NormativeClause
from app.db.models.template_memory import TitleBlockTemplate, SymbolLibrary
from app.db.repositories.intake_repository import IntakeRepository
from app.services.ingest.service import IngestService
from app.core.settings import settings
from app.core.logging import logger

VALID_SOURCE_TYPES = [
    "analysis_document",
    "template_document",
    "symbol_reference",
    "normative_document",
    "web_normative_source"
]

TARGET_MEMORY_MAPPING = {
    "analysis_document": "document_memory",
    "template_document": "template_memory",
    "symbol_reference": "template_memory",
    "normative_document": "normative_memory",
    "web_normative_source": "normative_memory"
}

class IntakeService:
    """Servicio centralizado de intake, clasificación, gobierno, almacenamiento físico y direccionamiento."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = IntakeRepository(db)

    def calculate_hash(self, data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def register_source(
        self,
        source_type: str,
        title: str,
        organization_id: Optional[str] = None,
        project_id: Optional[str] = None,
        source_origin: str = "local_upload",
        document_type: Optional[str] = None,
        discipline: str = "general",
        description: Optional[str] = None,
        source_url: Optional[str] = None,
        file_bytes: Optional[bytes] = None,
        filename: Optional[str] = None,
        mime_type: Optional[str] = None,
        version: str = "1.0",
        owner: str = "system",
        metadata_payload: Optional[Dict[str, Any]] = None
    ) -> SourceAsset:
        """Registra, almacena físicamente y cataloga en BD una nueva fuente."""
        if source_type not in VALID_SOURCE_TYPES:
            raise ValueError(
                f"Tipo de fuente '{source_type}' no válido. Opciones permitidas: {VALID_SOURCE_TYPES}"
            )

        linked_target = TARGET_MEMORY_MAPPING[source_type]
        meta = metadata_payload or {}

        org_id = organization_id
        if not org_id:
            from app.db.models.core import Organization
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

        # Determinar estado de aprobación inicial
        if source_type == "web_normative_source" or source_origin == "web_scrape":
            approval_status = "pending_review"
        elif source_type == "analysis_document":
            approval_status = "not_required"
        else:
            approval_status = "approved"

        file_path = None
        sha256_hash = None
        file_size = None
        m_type = mime_type or ("application/pdf" if file_bytes else "text/html" if source_url else "application/json")

        if file_bytes:
            sha256_hash = self.calculate_hash(file_bytes)
            file_size = len(file_bytes)
            
            # Guardar físicamente en carpeta persistente asociada al volumen
            intake_dir = os.path.join(settings.STORAGE_LOCAL_ROOT, "intake_sources", str(org_id))
            os.makedirs(intake_dir, exist_ok=True)
            
            safe_name = filename or f"{sha256_hash[:16]}.bin"
            clean_filename = "".join(c for c in safe_name if c.isalnum() or c in "._- ")
            file_path = os.path.join(intake_dir, f"{sha256_hash[:12]}_{clean_filename}")
            
            with open(file_path, "wb") as f:
                f.write(file_bytes)
            logger.info(f"Archivo de fuente guardado físicamente en: {file_path} ({file_size} bytes)")

        source = SourceAsset(
            organization_id=org_id,
            project_id=project_id,
            source_type=source_type,
            source_origin=source_origin,
            document_type=document_type or ("blueprint_pdf" if source_type == "analysis_document" else "standard_doc"),
            discipline=discipline,
            title=title,
            description=description,
            file_path=file_path,
            original_filename=filename,
            file_size_bytes=file_size,
            source_url=source_url,
            sha256=sha256_hash,
            mime_type=m_type,
            version=version,
            status="registered",
            approval_status=approval_status,
            linked_memory_target=linked_target,
            owner=owner,
            metadata_payload=meta
        )

        created = self.repo.create(source)
        logger.info(
            f"Fuente registrada: '{title}' [{source_type}] -> Destino: {linked_target} (Aprobación: {approval_status})"
        )
        return created

    def get_source_dependencies(self, source_id: str) -> Dict[str, Any]:
        """Obtiene las dependencias vinculadas a la fuente para advertencia previa al borrado."""
        return self.repo.get_source_dependencies(source_id)

    def delete_source(self, source_id: str, hard_delete: bool = False) -> Dict[str, Any]:
        """Elimina una fuente de forma segura y consistente entre UI, BD y almacenamiento en disco."""
        source = self.repo.get_by_id(source_id)
        if not source:
            raise ValueError(f"Fuente con ID '{source_id}' no encontrada.")

        deps = self.repo.get_source_dependencies(source_id)
        has_dependents = (deps["extractions_count"] > 0 or deps["rule_documents_count"] > 0)

        file_removed = False

        if hard_delete or not has_dependents:
            # Borrado físico en disco si el archivo existe
            if source.file_path and os.path.exists(source.file_path):
                try:
                    os.remove(source.file_path)
                    file_removed = True
                    logger.info(f"Archivo físico eliminado de disco: {source.file_path}")
                except Exception as e:
                    logger.warning(f"No se pudo eliminar el archivo físico en disco '{source.file_path}': {e}")

            # Borrado en base de datos
            self.db.delete(source)
            self.db.commit()
            logger.info(f"Fuente '{source.title}' eliminada completamente (Hard-Delete).")

            return {
                "source_id": source_id,
                "deleted": True,
                "mode": "hard_delete",
                "file_removed": file_removed,
                "message": f"Fuente '{source.title}' y su archivo físico fueron eliminados exitosamente."
            }
        else:
            # Soft delete / Archivo para preservar integridad de datos
            source.status = "archived"
            source.approval_status = "rejected"
            self.db.commit()
            logger.info(f"Fuente '{source.title}' archivada (Soft-Delete por dependencias activas).")

            return {
                "source_id": source_id,
                "deleted": True,
                "mode": "soft_delete_archived",
                "file_removed": False,
                "message": f"Fuente '{source.title}' fue archivada para preservar {deps['extractions_count']} extracción(es) y {deps['rule_documents_count']} regla(s) asociada(s)."
            }

    def approve_or_reject_source(
        self,
        source_id: str,
        approved: bool,
        notes: Optional[str] = None,
        reviewer: str = "lead_reviewer"
    ) -> SourceAsset:
        """Flujo de gobierno: Aprueba o rechaza una fuente para su posterior alimentación a memoria."""
        source = self.repo.get_by_id(source_id)
        if not source:
            raise ValueError(f"Fuente con ID '{source_id}' no encontrada.")

        new_status = "approved" if approved else "rejected"
        updated = self.repo.update_approval(
            source_id=source_id,
            approval_status=new_status,
            notes=notes,
            reviewer=reviewer
        )
        logger.info(f"Gobierno de entrada: Fuente '{source.title}' marcada como '{new_status}' por {reviewer}.")
        return updated

    def ingest_source(
        self,
        source_id: str,
        project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Direcciona e ingesta la fuente a su memoria correspondiente, aplicando candados de gobierno."""
        source = self.repo.get_by_id(source_id)
        if not source:
            raise ValueError(f"Fuente con ID '{source_id}' no encontrada.")

        if source.approval_status not in ["approved", "not_required"]:
            raise PermissionError(
                f"La fuente '{source.title}' está en estado '{source.approval_status}'. "
                f"Debe ser revisada y aprobada antes de alimentar '{source.linked_memory_target}'."
            )

        target_memory = source.linked_memory_target
        details: Dict[str, Any] = {}

        self.repo.update_status(source.id, "ingesting")

        try:
            if target_memory == "document_memory":
                if not project_id:
                    raise ValueError("Se requiere 'project_id' para direccionar a document_memory.")
                if not source.file_path or not os.path.exists(source.file_path):
                    raise FileNotFoundError(f"Archivo de plano no encontrado en '{source.file_path}'")
                
                with open(source.file_path, "rb") as f:
                    content = f.read()

                ingest_svc = IngestService(self.db)
                doc = ingest_svc.ingest_pdf(
                    project_id=project_id,
                    filename=source.original_filename or (source.title if source.title.endswith(".pdf") else f"{source.title}.pdf"),
                    file_bytes=content,
                    auto_process=True
                )
                details = {"document_id": doc.id, "pages": doc.page_count, "status": doc.status}

            elif target_memory == "normative_memory":
                code = source.metadata_payload.get("code") or f"NORM-{source.id[:8].upper()}"
                norm_doc = self.db.query(NormativeDocument).filter(NormativeDocument.code == code).first()
                if not norm_doc:
                    norm_doc = NormativeDocument(
                        code=code,
                        title=source.title,
                        authority=source.metadata_payload.get("authority", "Organismo Técnico"),
                        country=source.metadata_payload.get("country", "CL"),
                        discipline=source.discipline,
                        version_year=int(source.version.split(".")[0]) if source.version.isdigit() else 2024
                    )
                    self.db.add(norm_doc)
                    self.db.commit()
                    self.db.refresh(norm_doc)

                clauses_data = source.metadata_payload.get("clauses", [])
                for c in clauses_data:
                    clause = NormativeClause(
                        document_id=norm_doc.id,
                        clause_number=c.get("clause_number", "Art. 1"),
                        title=c.get("title", "Artículo"),
                        content_text=c.get("content_text", ""),
                        summary=c.get("summary")
                    )
                    self.db.add(clause)
                self.db.commit()
                details = {"normative_document_id": norm_doc.id, "code": code, "clauses_added": len(clauses_data)}

            elif target_memory == "template_memory":
                if source.source_type == "template_document":
                    tpl_name = source.metadata_payload.get("template_name") or source.title
                    tb_tpl = self.db.query(TitleBlockTemplate).filter(TitleBlockTemplate.name == tpl_name).first()
                    if not tb_tpl:
                        tb_tpl = TitleBlockTemplate(
                            name=tpl_name,
                            client_or_standard=source.metadata_payload.get("standard", "Standard"),
                            discipline=source.discipline,
                            relative_position=source.metadata_payload.get("relative_position", "bottom_right"),
                            expected_bbox=source.metadata_payload.get("expected_bbox", [0.72, 0.72, 0.98, 0.98]),
                            field_anchors=source.metadata_payload.get("field_anchors", {})
                        )
                        self.db.add(tb_tpl)
                        self.db.commit()
                    details = {"template_name": tpl_name, "type": "title_block_template"}

            self.repo.update_status(source.id, "ingested")
            logger.info(f"Fuente '{source.title}' ingestada exitosamente a '{target_memory}'.")
            return {
                "source_id": source.id,
                "status": "ingested",
                "target_memory": target_memory,
                "message": f"Fuente ingestada exitosamente a {target_memory}.",
                "details": details
            }

        except Exception as e:
            self.repo.update_status(source.id, "failed")
            logger.error(f"Fallo en ingestión de fuente {source.id}: {e}", exc_info=True)
            raise e

    # =========================================================
    # VISOR DOCUMENTAL REAL: RASTERIZADO, RECORTES Y RESUMEN
    # =========================================================

    def get_source_pages(self, source_id: str) -> Dict[str, Any]:
        """
        Obtiene y renderiza las páginas reales de un documento PDF o imagen cargado al sistema.
        Retorna las URLs de las páginas de alta resolución para el visor continuo.
        """
        source = self.repo.get_by_id(source_id)
        if not source:
            raise ValueError(f"Fuente con ID '{source_id}' no encontrada.")

        org_id = str(source.organization_id)
        pages_list = []
        file_path = source.file_path

        if file_path and os.path.exists(file_path):
            # Caso A: Archivo PDF real
            if file_path.lower().endswith(".pdf") or source.mime_type == "application/pdf":
                try:
                    import fitz
                    doc = fitz.open(file_path)
                    total_pages = len(doc)
                    
                    rendered_dir = os.path.join(settings.STORAGE_LOCAL_ROOT, "intake_sources", org_id, "rendered_pages")
                    os.makedirs(rendered_dir, exist_ok=True)

                    for page_idx in range(total_pages):
                        page_num = page_idx + 1
                        page = doc[page_idx]
                        
                        img_filename = f"{source.id}_p{page_num}.png"
                        img_path = os.path.join(rendered_dir, img_filename)
                        
                        # Renderizar a 150 DPI si no existe
                        if not os.path.exists(img_path):
                            pix = page.get_pixmap(dpi=150)
                            pix.save(img_path)
                            w_px, h_px = pix.width, pix.height
                        else:
                            import fitz
                            pix = page.get_pixmap(dpi=150)
                            w_px, h_px = pix.width, pix.height

                        text_preview = page.get_text()[:400].strip() or None
                        url_path = f"/data/intake_sources/{org_id}/rendered_pages/{img_filename}"

                        pages_list.append({
                            "page_number": page_num,
                            "image_url": url_path,
                            "width_px": w_px,
                            "height_px": h_px,
                            "width_pt": float(page.rect.width),
                            "height_pt": float(page.rect.height),
                            "text_preview": text_preview
                        })

                    doc.close()
                    return {
                        "source_id": source.id,
                        "title": source.title,
                        "document_type": source.document_type or "norma",
                        "discipline": source.discipline or "general",
                        "total_pages": total_pages,
                        "file_exists": True,
                        "mime_type": source.mime_type,
                        "pages": pages_list
                    }

                except Exception as e:
                    logger.error(f"Error renderizando páginas de PDF '{file_path}': {e}", exc_info=True)

            # Caso B: Archivo Imagen real (PNG, JPG)
            elif any(file_path.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp"]):
                try:
                    import fitz
                    img_doc = fitz.open(file_path)
                    page = img_doc[0]
                    w_pt, h_pt = float(page.rect.width), float(page.rect.height)
                    img_doc.close()
                    
                    rel_path = file_path.replace("\\", "/")
                    if "data/" in rel_path:
                        rel_path = "/data/" + rel_path.split("data/", 1)[1]
                    else:
                        rel_path = f"/data/intake_sources/{org_id}/{os.path.basename(file_path)}"

                    pages_list.append({
                        "page_number": 1,
                        "image_url": rel_path,
                        "width_px": int(w_pt),
                        "height_px": int(h_pt),
                        "width_pt": w_pt,
                        "height_pt": h_pt,
                        "text_preview": "Imagen técnica / lámina gráfica incorporada."
                    })
                    return {
                        "source_id": source.id,
                        "title": source.title,
                        "document_type": source.document_type or "standard_doc",
                        "discipline": source.discipline or "general",
                        "total_pages": 1,
                        "file_exists": True,
                        "mime_type": source.mime_type,
                        "pages": pages_list
                    }
                except Exception as e:
                    logger.error(f"Error procesando imagen '{file_path}': {e}")

        # Fallback estructurado si no hay archivo físico o es texto puro
        return {
            "source_id": source.id,
            "title": source.title,
            "document_type": source.document_type or "norma",
            "discipline": source.discipline or "general",
            "total_pages": 3,
            "file_exists": False,
            "mime_type": source.mime_type or "text/plain",
            "pages": [
                {
                    "page_number": 1,
                    "image_url": "",
                    "width_px": 800,
                    "height_px": 1100,
                    "width_pt": 612.0,
                    "height_pt": 792.0,
                    "text_preview": f"Disposiciones generales y alcance técnico de {source.title}."
                },
                {
                    "page_number": 2,
                    "image_url": "",
                    "width_px": 800,
                    "height_px": 1100,
                    "width_pt": 612.0,
                    "height_pt": 792.0,
                    "text_preview": "Criterios técnicos, cuadros de exigencias y tablas de dimensionamiento."
                },
                {
                    "page_number": 3,
                    "image_url": "",
                    "width_px": 800,
                    "height_px": 1100,
                    "width_pt": 612.0,
                    "height_pt": 792.0,
                    "text_preview": "Detalles constructivos, figuras normativas y simbología reglamentaria."
                }
            ]
        }

    def crop_source_page(
        self,
        source_id: str,
        page_number: int,
        bbox: List[float],
        title: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Recorta con precisión una región rectangular de la página real del PDF.
        Retorna la imagen en base64 para preview instantáneo y la guarda en disco.
        """
        source = self.repo.get_by_id(source_id)
        if not source:
            raise ValueError(f"Fuente con ID '{source_id}' no encontrada.")

        org_id = str(source.organization_id)
        file_path = source.file_path
        
        # Validar y normalizar bbox [x0, y0, x1, y1]
        x0 = max(0.0, min(1.0, float(bbox[0])))
        y0 = max(0.0, min(1.0, float(bbox[1])))
        x1 = max(0.0, min(1.0, float(bbox[2])))
        y1 = max(0.0, min(1.0, float(bbox[3])))
        
        if x0 > x1:
            x0, x1 = x1, x0
        if y0 > y1:
            y0, y1 = y1, y0

        crop_dir = os.path.join(settings.STORAGE_LOCAL_ROOT, "intake_sources", org_id, "crops")
        os.makedirs(crop_dir, exist_ok=True)
        
        crop_id = uuid.uuid4().hex[:10]
        crop_filename = f"{source.id}_p{page_number}_{crop_id}.png"
        crop_path = os.path.join(crop_dir, crop_filename)
        crop_url = f"/data/intake_sources/{org_id}/crops/{crop_filename}"
        
        ocr_text = ""
        b64_data = ""
        width_px, height_px = 300, 200

        if file_path and os.path.exists(file_path):
            try:
                import fitz
                import base64
                doc = fitz.open(file_path)
                page_idx = max(0, min(page_number - 1, len(doc) - 1))
                page = doc[page_idx]
                
                # Rectángulo en puntos tipográficos
                rect = fitz.Rect(
                    x0 * page.rect.width,
                    y0 * page.rect.height,
                    x1 * page.rect.width,
                    y1 * page.rect.height
                )
                
                # Renderizar crop a 200 DPI para alta nitidez
                pix = page.get_pixmap(dpi=200, clip=rect)
                pix.save(crop_path)
                
                width_px = pix.width
                height_px = pix.height
                
                img_bytes = pix.tobytes("png")
                b64_data = f"data:image/png;base64,{base64.b64encode(img_bytes).decode('ascii')}"
                
                # Extraer texto OCR dentro del área recortada
                ocr_text = page.get_textbox(rect).strip()
                doc.close()
                
            except Exception as e:
                logger.error(f"Error recortando página PDF '{file_path}': {e}", exc_info=True)

        return {
            "source_id": source.id,
            "page_number": page_number,
            "bbox": [x0, y0, x1, y1],
            "crop_image_url": crop_url,
            "crop_image_base64": b64_data or None,
            "ocr_text": ocr_text or None,
            "width_px": width_px,
            "height_px": height_px
        }

    def summarize_rule(
        self,
        text_content: str,
        discipline: str = "general",
        title: Optional[str] = None,
        item_type: str = "rule"
    ) -> Dict[str, Any]:
        """
        Transforma un fragmento o artículo técnico largo en un enunciado resumido,
        claro y estructurado tipo regla QA/QC con parámetros cuantificables.
        """
        import re

        clean_text = text_content.strip()
        
        # Extracción de parámetros técnicos comunes (dimensiones, distancias, porcentajes, tiempos)
        parameters = {}
        
        # Buscar medidas tipo 1.20 m, 0.90m, 50 cm, 25 m, etc.
        measures = re.findall(r'(\d+(?:[.,]\d+)?)\s*(m|cm|mm|metros|centimetros|kg|m2|minutos|min|hrs|horas|F-\d+)', clean_text, re.IGNORECASE)
        if measures:
            for idx, (val, unit) in enumerate(measures[:3]):
                param_key = f"param_{unit.lower()}_{idx+1}"
                parameters[param_key] = f"{val} {unit}"

        # Generar código de regla
        disc_prefix = {
            "arquitectura": "ARQ",
            "estructuras": "EST",
            "mecanica": "MEC",
            "electrica": "ELE",
            "sanitaria": "SAN",
            "seguridad_incendio": "INC"
        }.get(discipline.lower(), "GEN")
        
        code_match = re.search(r'(Art\.\s*\d+(?:\.\d+)*|Cap[ií]tulo\s*\d+|Tabla\s*\d+(?:\.[A-Z0-9]+)*|REG-[A-Z0-9-]+)', clean_text, re.IGNORECASE)
        rule_code = code_match.group(0).upper() if code_match else f"REG-{disc_prefix}-{uuid.uuid4().hex[:4].upper()}"

        # Sintetizar enunciado de regla
        # Si contiene "deberá", "no inferior a", "mínimo", estructurar proposición técnica
        first_sentence = clean_text.split(".")[0].strip()
        if len(first_sentence) < 15:
            first_sentence = clean_text[:180]
            
        rule_statement = f"Exigencia técnica [{rule_code}]: {first_sentence}."
        summary = f"Regla QA/QC para {discipline}: verificación de cumplimiento según {title or 'documento normativo'}."

        return {
            "rule_code": rule_code,
            "rule_statement": rule_statement,
            "summary": summary,
            "discipline": discipline,
            "item_nature": "official_rule" if "art" in rule_code.lower() or "oguc" in (title or "").lower() else "proposed_rule",
            "extracted_parameters": parameters
        }
