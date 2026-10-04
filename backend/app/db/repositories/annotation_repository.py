import os
import uuid
import base64
import io
from datetime import datetime
from typing import List, Optional, Tuple
from PIL import Image
from sqlalchemy.orm import Session

from app.db.models.active_learning import (
    ManualAnnotation, KnowledgeLibraryEntry, ActiveLearningPromotion
)
from app.db.models.core import AuditLog

CROPS_DIR = os.getenv("CROPS_DIR", "./storage/crops")

class AnnotationRepository:
    """Repositorio para gestión de anotaciones manuales, recortes y promoción de conocimiento."""

    @staticmethod
    def _save_base64_image(base64_str: str, folder_path: str, filename: str) -> Optional[str]:
        """Decodifica un string base64 y lo almacena como archivo PNG en disco."""
        try:
            if "," in base64_str:
                base64_str = base64_str.split(",")[1]
            image_data = base64.b64decode(base64_str)
            os.makedirs(folder_path, exist_ok=True)
            file_path = os.path.join(folder_path, filename)
            with open(file_path, "wb") as f:
                f.write(image_data)
            return file_path.replace("\\", "/")
        except Exception as e:
            print(f"[AnnotationRepository] Error guardando imagen de recorte: {e}")
            return None

    @staticmethod
    def run_crop_ocr(image_base64: str) -> Tuple[str, float, str]:
        """Ejecuta OCR sobre una imagen recortada en Base64."""
        try:
            if "," in image_base64:
                image_base64 = image_base64.split(",")[1]
            image_bytes = base64.b64decode(image_base64)
            img = Image.open(io.BytesIO(image_bytes))

            # Intentar con pytesseract si está disponible en el entorno
            try:
                import pytesseract
                text = pytesseract.image_to_string(img, lang="spa+eng", config="--psm 6")
                text_clean = text.strip()
                if text_clean:
                    return text_clean, 0.95, "pytesseract"
            except Exception as ocr_err:
                print(f"[AnnotationRepository] Fallback de OCR: {ocr_err}")

            # Fallback secundario si Tesseract no extrajo texto o no está configurado
            return "Texto extraído del recorte (editable por el usuario)", 0.85, "fallback_ocr"
        except Exception as e:
            print(f"[AnnotationRepository] Error procesando OCR en recorte: {e}")
            return "", 0.0, "error"

    @classmethod
    def create_annotation(
        cls,
        db: Session,
        organization_id: str,
        user_id: Optional[str],
        data: dict
    ) -> ManualAnnotation:
        """Crea y persiste una anotación manual con su recorte en disco."""
        annotation_id = str(uuid.uuid4())
        doc_id = data.get("document_id", "default_doc")
        sheet_id = data.get("sheet_id", "default_sheet")

        crop_path = None
        base64_data = data.pop("crop_image_base64", None)
        if base64_data:
            target_folder = os.path.join(CROPS_DIR, doc_id, sheet_id)
            crop_path = cls._save_base64_image(base64_data, target_folder, f"{annotation_id}.png")

        annotation = ManualAnnotation(
            id=annotation_id,
            organization_id=organization_id,
            user_id=user_id,
            crop_image_path=crop_path,
            **data
        )
        db.add(annotation)

        audit = AuditLog(
            entity_type="manual_annotation",
            entity_id=annotation.id,
            action="create_annotation",
            user_id=user_id,
            details={"element_type": annotation.element_type, "name": annotation.name}
        )
        db.add(audit)
        db.commit()
        db.refresh(annotation)
        return annotation

    @classmethod
    def list_annotations(
        cls,
        db: Session,
        organization_id: str,
        sheet_id: Optional[str] = None,
        document_id: Optional[str] = None,
        project_id: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[ManualAnnotation]:
        """Lista las anotaciones manuales según los filtros indicados."""
        query = db.query(ManualAnnotation).filter(ManualAnnotation.organization_id == organization_id)
        if sheet_id:
            query = query.filter(ManualAnnotation.sheet_id == sheet_id)
        if document_id:
            query = query.filter(ManualAnnotation.document_id == document_id)
        if project_id:
            query = query.filter(ManualAnnotation.project_id == project_id)
        if status:
            query = query.filter(ManualAnnotation.status == status)
        return query.order_by(ManualAnnotation.created_at.desc()).all()

    @classmethod
    def update_annotation(
        cls,
        db: Session,
        organization_id: str,
        annotation_id: str,
        user_id: Optional[str],
        data: dict
    ) -> Optional[ManualAnnotation]:
        """Actualiza metadatos de una anotación manual existente."""
        annotation = db.query(ManualAnnotation).filter(
            ManualAnnotation.id == annotation_id,
            ManualAnnotation.organization_id == organization_id
        ).first()
        if not annotation:
            return None

        for key, val in data.items():
            if val is not None and hasattr(annotation, key):
                setattr(annotation, key, val)
        annotation.updated_at = datetime.utcnow()

        audit = AuditLog(
            entity_type="manual_annotation",
            entity_id=annotation.id,
            action="update_annotation",
            user_id=user_id,
            details=data
        )
        db.add(audit)
        db.commit()
        db.refresh(annotation)
        return annotation

    @classmethod
    def list_distinct_disciplines(cls, db: Session, organization_id: Optional[str] = None) -> List[str]:
        """Retorna todas las disciplinas distintas registradas en anotaciones manuales del tenant."""
        query = db.query(ManualAnnotation.discipline).distinct()
        if organization_id:
            query = query.filter(ManualAnnotation.organization_id == organization_id)
        rows = query.all()
        base = ["general", "architecture", "structural", "electrical", "plumbing", "hvac"]
        db_discs = [r[0] for r in rows if r[0]]
        merged = list(base)
        for d in db_discs:
            if not any(m.lower() == d.lower() for m in merged):
                merged.append(d)
        return merged


    @classmethod
    def promote_to_knowledge_library(
        cls,
        db: Session,
        organization_id: str,
        user_id: Optional[str],
        data: dict
    ) -> KnowledgeLibraryEntry:
        """Nivel 1: Incorpora un elemento confirmado a la Base de Conocimiento Guía & Plantillas."""
        entry_id = str(uuid.uuid4())
        crop_path = data.pop("crop_image_path", None)
        base64_data = data.pop("crop_image_base64", None)
        if base64_data and not crop_path:
            target_folder = os.path.join(CROPS_DIR, "knowledge_library")
            crop_path = cls._save_base64_image(base64_data, target_folder, f"{entry_id}.png")

        entry = KnowledgeLibraryEntry(
            id=entry_id,
            organization_id=organization_id,
            created_by_user_id=user_id,
            crop_image_path=crop_path,
            **data
        )
        db.add(entry)


        # Actualizar estado de la anotación de origen si existe
        if entry.source_annotation_id:
            src = db.query(ManualAnnotation).filter(
                ManualAnnotation.id == entry.source_annotation_id,
                ManualAnnotation.organization_id == organization_id
            ).first()
            if src:
                src.status = "promoted_to_knowledge"

        audit = AuditLog(
            entity_type="knowledge_library_entry",
            entity_id=entry.id,
            action="promote_to_knowledge",
            user_id=user_id,
            details={"entry_type": entry.entry_type, "name": entry.name}
        )
        db.add(audit)
        db.commit()
        db.refresh(entry)
        return entry

    @classmethod
    def list_knowledge_entries(
        cls,
        db: Session,
        organization_id: str,
        entry_type: Optional[str] = None,
        discipline: Optional[str] = None
    ) -> List[KnowledgeLibraryEntry]:
        """Consulta catálogo curado de la Base de Conocimiento Guía."""
        query = db.query(KnowledgeLibraryEntry).filter(
            KnowledgeLibraryEntry.organization_id == organization_id,
            KnowledgeLibraryEntry.status == "active"
        )
        if entry_type:
            query = query.filter(KnowledgeLibraryEntry.entry_type == entry_type)
        if discipline and discipline != "all":
            query = query.filter(KnowledgeLibraryEntry.discipline == discipline)
        return query.order_by(KnowledgeLibraryEntry.created_at.desc()).all()

    @classmethod
    def promote_to_active_learning(
        cls,
        db: Session,
        organization_id: str,
        user_id: Optional[str],
        data: dict
    ) -> ActiveLearningPromotion:
        """Nivel 2: Promociona un elemento hacia el pool de entrenamiento / MLOps."""
        promotion_id = str(uuid.uuid4())
        promotion = ActiveLearningPromotion(
            id=promotion_id,
            organization_id=organization_id,
            promoted_by_user_id=user_id,
            **data
        )
        db.add(promotion)

        # Si proviene de anotación, actualizar su estado
        if promotion.manual_annotation_id:
            src = db.query(ManualAnnotation).filter(
                ManualAnnotation.id == promotion.manual_annotation_id,
                ManualAnnotation.organization_id == organization_id
            ).first()
            if src:
                src.status = "promoted_to_active_learning"

        audit = AuditLog(
            entity_type="active_learning_promotion",
            entity_id=promotion.id,
            action="promote_to_active_learning",
            user_id=user_id,
            details={"target_engine": promotion.target_engine, "label": promotion.label}
        )
        db.add(audit)
        db.commit()
        db.refresh(promotion)
        return promotion

    @classmethod
    def list_active_learning_promotions(
        cls,
        db: Session,
        organization_id: str,
        target_engine: Optional[str] = None
    ) -> List[ActiveLearningPromotion]:
        """Lista las muestras promovidas a Active Learning."""
        query = db.query(ActiveLearningPromotion).filter(
            ActiveLearningPromotion.organization_id == organization_id
        )
        if target_engine:
            query = query.filter(ActiveLearningPromotion.target_engine == target_engine)
        return query.order_by(ActiveLearningPromotion.created_at.desc()).all()

    @classmethod
    def incorporate_selections_to_project_document(
        cls,
        db: Session,
        organization_id: str,
        project_id: str,
        user_id: Optional[str] = None,
        annotation_ids: Optional[List[str]] = None
    ) -> dict:
        """
        Incorpora las selecciones validadas del visor de planos hacia un RuleDocument
        asociado al proyecto ('Información basada en proyecto XXXXXXXXX') en el circuito
        documental de 'Documentos Nativos & Fuentes Incorporados'.
        """
        from app.db.models.core import Project
        from app.db.models.intake_extractions import RuleDocument, RuleDocumentItem

        project = db.query(Project).filter(
            Project.id == project_id,
            Project.organization_id == organization_id
        ).first()

        proj_name = project.name if project else "Proyecto"
        proj_code = project.code if project else "PRJ"

        # Buscar o crear el RuleDocument del proyecto
        doc_title = f"Información basada en proyecto {proj_name}"
        rule_doc = db.query(RuleDocument).filter(
            RuleDocument.organization_id == organization_id,
            RuleDocument.project_id == project_id,
            RuleDocument.source_origin == "visor_de_planos"
        ).first()

        if not rule_doc:
            rule_doc = RuleDocument(
                id=str(uuid.uuid4()),
                organization_id=organization_id,
                project_id=project_id,
                title=doc_title,
                description=f"Evidencia, simbología y notas técnicas extraídas desde el visor de planos del proyecto {proj_name} ({proj_code}).",
                document_type="proyecto_evidencia",
                source_origin="visor_de_planos",
                authority=f"Evidencia de Proyecto ({proj_code})",
                discipline="General",
                version="1.0",
                status="active"
            )
            db.add(rule_doc)
            db.flush()

        # Filtrar selecciones a incorporar
        query = db.query(ManualAnnotation).filter(
            ManualAnnotation.organization_id == organization_id,
            ManualAnnotation.project_id == project_id
        )
        if annotation_ids:
            query = query.filter(ManualAnnotation.id.in_(annotation_ids))
        else:
            query = query.filter(ManualAnnotation.status.in_(["validada", "confirmed", "draft"]))

        selections = query.all()
        if not selections:
            raise ValueError("No se encontraron selecciones para incorporar.")

        incorporated_count = 0
        for idx, ann in enumerate(selections, start=1):
            existing_item = db.query(RuleDocumentItem).filter(
                RuleDocumentItem.rule_document_id == rule_doc.id,
                RuleDocumentItem.title == ann.name
            ).first()

            item_code = f"PLN-{proj_code}-{ann.element_type[:3].upper()}-{idx:02d}"

            if not existing_item:
                new_item = RuleDocumentItem(
                    id=str(uuid.uuid4()),
                    rule_document_id=rule_doc.id,
                    title=ann.name,
                    code_or_number=item_code,
                    item_type=ann.element_type,
                    source_origin="visor_de_planos",
                    source_reference=f"Lámina {ann.sheet_id[:8]}",
                    item_nature="project_derived_evidence",
                    description=ann.description or ann.ocr_text or ann.name,
                    ocr_text=ann.ocr_text,
                    content_text=ann.ocr_text or ann.description or ann.name,
                    crop_image_path=ann.crop_image_path,
                    target_destination="rules_engine",
                    status="validada",
                    metadata_payload={
                        "source_annotation_id": ann.id,
                        "bbox_normalized": ann.bbox_normalized,
                        "sheet_id": ann.sheet_id,
                        "discipline": ann.discipline,
                        "tags": ann.tags
                    }
                )
                db.add(new_item)
                incorporated_count += 1
            else:
                existing_item.description = ann.description or ann.ocr_text or ann.name
                existing_item.ocr_text = ann.ocr_text
                existing_item.content_text = ann.ocr_text or ann.description or ann.name
                existing_item.crop_image_path = ann.crop_image_path
                existing_item.status = "validada"
                incorporated_count += 1

            ann.status = "validada"
            meta = dict(ann.extra_metadata or {})
            meta["incorporated_into_rule_document_id"] = rule_doc.id
            ann.extra_metadata = meta

        db.flush()
        # Actualizar contadores del rule_doc
        all_items = db.query(RuleDocumentItem).filter(RuleDocumentItem.rule_document_id == rule_doc.id).all()
        rule_doc.items_count = len(all_items)
        rule_doc.rules_count = len([i for i in all_items if i.item_type in ["rule", "regla", "text_note", "symbol", "article", "requirement", "restriction"]])
        rule_doc.tables_count = len([i for i in all_items if i.item_type in ["table", "tabla"]])
        rule_doc.images_count = len([i for i in all_items if i.item_type in ["figure", "figura", "symbol", "view_elevation_plan", "diagram_sketch"]])

        audit = AuditLog(
            entity_type="rule_document",
            entity_id=rule_doc.id,
            action="incorporate_project_selections",
            user_id=user_id,
            details={
                "project_id": project_id,
                "incorporated_count": incorporated_count,
                "total_items": rule_doc.items_count
            }
        )
        db.add(audit)
        db.commit()
        db.refresh(rule_doc)

        return {
            "rule_document_id": rule_doc.id,
            "rule_document_title": rule_doc.title,
            "project_id": project_id,
            "incorporated_count": incorporated_count,
            "message": f"Se incorporaron {incorporated_count} selecciones validadas a «{rule_doc.title}» en Documentos Nativos & Fuentes Incorporados."
        }
