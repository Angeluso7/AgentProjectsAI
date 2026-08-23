import os
import uuid
import base64
import re
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.settings import settings
from app.db.models.intake_extractions import (
    SourceExtraction, ExtractedItem, RuleDocument, RuleDocumentItem, SupportingKnowledgeItem
)
from app.db.models.active_learning import KnowledgeLibraryEntry
from app.db.models.intake import SourceAsset
from app.db.models.core import Organization

class IntakeExtractionRepository:
    """Repositorio para la gestión de extracciones estructuradas y documentos del Motor de Reglas."""

    def __init__(self, db: Session):
        self.db = db
        self.crops_dir = os.path.join(settings.STORAGE_LOCAL_ROOT, "crops", "extractions")
        os.makedirs(self.crops_dir, exist_ok=True)

    def get_or_create_default_org(self) -> Organization:
        org = self.db.query(Organization).first()
        if not org:
            org = Organization(
                id=str(uuid.uuid4()),
                name="Organización Principal",
                slug="org-principal",
                is_active=True
            )
            self.db.add(org)
            self.db.commit()
            self.db.refresh(org)
        return org

    # =========================================================
    # SESIONES DE EXTRACCIÓN (SOURCE EXTRACTIONS)
    # =========================================================

    def create_extraction_session(
        self,
        title: str,
        document_type: str = "norma",
        authority: Optional[str] = None,
        discipline: str = "general",
        extraction_mode: str = "ai_document",
        source_origin: str = "document",
        search_query: Optional[str] = None,
        search_citations: Optional[List[Dict[str, Any]]] = None,
        source_asset_id: Optional[str] = None,
        project_id: Optional[str] = None,
        source_file_path: Optional[str] = None,
        source_url: Optional[str] = None,
        summary: Optional[str] = None,
        metadata_info: Optional[Dict[str, Any]] = None
    ) -> SourceExtraction:
        org = self.get_or_create_default_org()
        
        session = SourceExtraction(
            id=str(uuid.uuid4()),
            organization_id=org.id,
            project_id=project_id,
            source_asset_id=source_asset_id,
            title=title,
            document_type=document_type,
            authority=authority,
            discipline=discipline,
            extraction_mode=extraction_mode,
            source_origin=source_origin,
            search_query=search_query,
            search_citations=search_citations or [],
            source_file_path=source_file_path,
            source_url=source_url,
            status="extracting" if extraction_mode in ["ai_document", "ai_web_research", "with_ai"] else "draft",
            summary=summary,
            total_items=0,
            metadata_info=metadata_info or {},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_extraction_by_id(self, extraction_id: str) -> Optional[SourceExtraction]:
        return self.db.query(SourceExtraction).filter(SourceExtraction.id == extraction_id).first()

    def list_extractions(
        self,
        discipline: Optional[str] = None,
        document_type: Optional[str] = None,
        extraction_mode: Optional[str] = None,
        source_origin: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[SourceExtraction]:
        query = self.db.query(SourceExtraction)
        if discipline:
            query = query.filter(SourceExtraction.discipline == discipline)
        if document_type:
            query = query.filter(SourceExtraction.document_type == document_type)
        if extraction_mode:
            query = query.filter(SourceExtraction.extraction_mode == extraction_mode)
        if source_origin:
            query = query.filter(SourceExtraction.source_origin == source_origin)
        if status:
            query = query.filter(SourceExtraction.status == status)
        return query.order_by(desc(SourceExtraction.created_at)).all()

    # =========================================================
    # ELEMENTOS EXTRAÍDOS (EXTRACTED ITEMS)
    # =========================================================

    def add_extracted_item(
        self,
        extraction_id: str,
        item_type: str,
        title: str,
        code_or_number: Optional[str] = None,
        description: Optional[str] = None,
        content_text: Optional[str] = None,
        ocr_text: Optional[str] = None,
        crop_image_base64: Optional[str] = None,
        bbox_normalized: Optional[List[float]] = None,
        page_number: int = 1,
        target_destination: str = "rules_engine",
        review_status: str = "draft",
        structured_matrix: Optional[Dict[str, Any]] = None,
        validated_at: Optional[datetime] = None,
        validated_by: Optional[str] = None,
        source_origin: str = "document",
        source_reference: Optional[str] = None,
        item_nature: str = "official_rule",
        governance_note: Optional[str] = None,
        metadata_payload: Optional[Dict[str, Any]] = None
    ) -> ExtractedItem:
        extraction = self.get_extraction_by_id(extraction_id)
        if not extraction:
            raise ValueError(f"Sesión de extracción {extraction_id} no encontrada.")

        item_id = str(uuid.uuid4())
        crop_image_path = None

        if crop_image_base64:
            try:
                data_str = crop_image_base64
                if "," in data_str:
                    data_str = data_str.split(",")[1]
                img_bytes = base64.b64decode(data_str)
                filename = f"ext_{extraction_id}_{item_id}.png"
                full_path = os.path.join(self.crops_dir, filename)
                with open(full_path, "wb") as f:
                    f.write(img_bytes)
                crop_image_path = f"/data/crops/extractions/{filename}"
            except Exception as e:
                print(f"Error guardando recorte de extracción: {e}")

        item = ExtractedItem(
            id=item_id,
            extraction_id=extraction_id,
            item_type=item_type,
            title=title,
            code_or_number=code_or_number,
            description=description,
            content_text=content_text,
            ocr_text=ocr_text,
            crop_image_path=crop_image_path,
            bbox_normalized=bbox_normalized or [],
            page_number=page_number,
            target_destination=target_destination,
            review_status=review_status,
            structured_matrix=structured_matrix or {},
            validated_at=validated_at,
            validated_by=validated_by,
            source_origin=source_origin,
            source_reference=source_reference,
            item_nature=item_nature,
            governance_note=governance_note,
            metadata_payload=metadata_payload or {},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        self.db.add(item)
        
        # Actualizar contador
        extraction.total_items = (extraction.total_items or 0) + 1
        extraction.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(item)
        return item

    def update_extracted_item(
        self,
        item_id: str,
        update_data: Dict[str, Any]
    ) -> Optional[ExtractedItem]:
        item = self.db.query(ExtractedItem).filter(ExtractedItem.id == item_id).first()
        if not item:
            return None
        for k, v in update_data.items():
            if hasattr(item, k):
                setattr(item, k, v)
        item.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(item)
        return item

    def delete_extracted_item(self, item_id: str) -> bool:
        item = self.db.query(ExtractedItem).filter(ExtractedItem.id == item_id).first()
        if not item:
            return False
        extraction = item.extraction
        self.db.delete(item)
        if extraction and extraction.total_items > 0:
            extraction.total_items -= 1
        self.db.commit()
        return True

    # =========================================================
    # INCORPORACIÓN / COMMIT HACIA EL MOTOR DE REGLAS QA/QC
    # =========================================================

    def commit_extraction_to_rules(
        self,
        extraction_id: str,
        approved_item_ids: Optional[List[str]] = None,
        target_rule_document_title: Optional[str] = None,
        target_rule_document_description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Incorpora los elementos validados de una sesión de extracción:
        - Reglas/Texto -> Motor de Reglas QA/QC (RuleDocument y RuleDocumentItem).
        - Elementos visuales (símbolos, sellos, firmas, tablas, figuras) -> Base de Conocimiento de Apoyo (SupportingKnowledgeItem).
        - Items en 'por_confirmar' permanecen en la sesión de extracción pendientes.
        """
        extraction = self.get_extraction_by_id(extraction_id)
        if not extraction:
            raise ValueError(f"Extracción {extraction_id} no encontrada.")

        # Obtener items de la extracción
        all_items = self.db.query(ExtractedItem).filter(ExtractedItem.extraction_id == extraction_id).all()
        
        if approved_item_ids:
            items_to_commit = [it for it in all_items if it.id in approved_item_ids and it.review_status not in ["eliminado", "rejected"]]
        else:
            items_to_commit = [it for it in all_items if it.review_status not in ["eliminado", "rejected"]]

        if not items_to_commit:
            raise ValueError("No hay elementos aprobados para incorporar al Motor de Reglas.")

        rules_count = sum(1 for it in items_to_commit if it.item_type in ["rule", "restriction", "requirement", "article", "chapter", "text_note", "definition", "procedure"])
        tables_count = sum(1 for it in items_to_commit if it.item_type == "table")
        images_count = sum(1 for it in items_to_commit if it.item_type in ["image", "figure", "symbol", "sello", "firma", "leyenda", "vineta", "foto", "otro"])

        rule_doc_id = str(uuid.uuid4())
        doc_title = target_rule_document_title or extraction.title
        doc_desc = target_rule_document_description or extraction.summary

        # Determinar source_origin para trazabilidad
        if extraction.extraction_mode == "ai_web_research" or extraction.source_origin == "web":
            source_origin_label = "con_ia_web"
        elif extraction.extraction_mode in ["ai_document", "with_ai"]:
            source_origin_label = "con_ia_documento"
        else:
            source_origin_label = "sin_ia"

        # 1. Crear RuleDocument en Motor de Reglas
        rule_doc = RuleDocument(
            id=rule_doc_id,
            organization_id=extraction.organization_id,
            project_id=extraction.project_id,
            source_extraction_id=extraction.id,
            source_asset_id=extraction.source_asset_id,
            title=doc_title,
            description=doc_desc,
            document_type=extraction.document_type,
            source_origin=source_origin_label,
            authority=extraction.authority,
            discipline=extraction.discipline,
            version="1.0",
            status="active",
            items_count=len(items_to_commit),
            rules_count=rules_count,
            tables_count=tables_count,
            images_count=images_count,
            metadata_info={
                **extraction.metadata_info,
                "search_query": extraction.search_query,
                "search_citations": extraction.search_citations,
            },
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        self.db.add(rule_doc)

        supporting_items_created = 0

        # 2. Crear elementos individuales según su naturaleza
        for it in items_to_commit:
            it.review_status = "validada"
            it.validated_at = datetime.utcnow()
            it.validated_by = "user_reviewer"

            # A) Crear RuleDocumentItem en Motor de Reglas QA/QC
            r_item = RuleDocumentItem(
                id=str(uuid.uuid4()),
                rule_document_id=rule_doc_id,
                extracted_item_id=it.id,
                item_type=it.item_type,
                source_origin=it.source_origin,
                source_reference=it.source_reference,
                item_nature=it.item_nature,
                title=it.title,
                code_or_number=it.code_or_number,
                description=it.description,
                content_text=it.content_text,
                ocr_text=it.ocr_text,
                crop_image_path=it.crop_image_path,
                target_destination=it.target_destination,
                status="active",
                metadata_payload={
                    **it.metadata_payload,
                    "governance_note": it.governance_note,
                    "structured_matrix": it.structured_matrix or {}
                },
                created_at=datetime.utcnow()
            )
            self.db.add(r_item)

            # B) Si es elemento visual/gráfico (o tabla) -> Crear SupportingKnowledgeItem
            if it.item_type in ["simbolo", "foto", "imagen", "tabla", "figura", "sello", "firma", "leyenda", "vineta", "otro", "image", "figure", "symbol", "table"] or it.target_destination in ["knowledge_base", "both"]:
                sup_item = SupportingKnowledgeItem(
                    id=str(uuid.uuid4()),
                    organization_id=extraction.organization_id,
                    project_id=extraction.project_id,
                    source_asset_id=extraction.source_asset_id,
                    source_extraction_id=extraction.id,
                    extracted_item_id=it.id,
                    item_type=it.item_type,
                    title=it.title,
                    code_or_number=it.code_or_number,
                    description=it.description or it.content_text,
                    discipline=extraction.discipline,
                    page_number=it.page_number,
                    bbox_normalized=it.bbox_normalized or [],
                    crop_image_path=it.crop_image_path,
                    ocr_text=it.ocr_text,
                    structured_matrix=it.structured_matrix or {},
                    status="validada",
                    validated_by="user_reviewer",
                    validated_at=datetime.utcnow(),
                    metadata_payload={
                        **it.metadata_payload,
                        "source_origin": it.source_origin,
                        "source_reference": it.source_reference
                    },
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                self.db.add(sup_item)
                supporting_items_created += 1

        # Verificar si quedan items pendientes en 'por_confirmar'
        remaining_pending = sum(1 for it in all_items if it.id not in [x.id for x in items_to_commit] and it.review_status not in ["eliminado", "rejected"])
        
        if remaining_pending == 0:
            extraction.status = "incorporated"
        else:
            extraction.status = "reviewed"
        
        extraction.updated_at = datetime.utcnow()
        self.db.commit()

        return {
            "extraction_id": extraction.id,
            "rule_document_id": rule_doc_id,
            "rules_incorporated_count": len(items_to_commit),
            "knowledge_entries_created_count": supporting_items_created,
            "message": f"Incorporados {len(items_to_commit)} elementos ({source_origin_label}) al Motor de Reglas QA/QC y {supporting_items_created} elementos a la Base de Conocimiento de Apoyo. ({remaining_pending} pendientes por confirmar)."
        }

    # =========================================================
    # DOCUMENTOS DE REGLAS QA/QC (RULE DOCUMENTS)
    # =========================================================

    def list_rule_documents(
        self,
        discipline: Optional[str] = None,
        document_type: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[RuleDocument]:
        query = self.db.query(RuleDocument)
        if discipline:
            query = query.filter(RuleDocument.discipline == discipline)
        if document_type:
            query = query.filter(RuleDocument.document_type == document_type)
        if status:
            query = query.filter(RuleDocument.status == status)
        return query.order_by(desc(RuleDocument.created_at)).all()

    def get_rule_document_by_id(self, doc_id: str) -> Optional[RuleDocument]:
        return self.db.query(RuleDocument).filter(RuleDocument.id == doc_id).first()

    def update_rule_document(self, doc_id: str, update_data: Dict[str, Any]) -> Optional[RuleDocument]:
        doc = self.get_rule_document_by_id(doc_id)
        if not doc:
            return None
        for k, v in update_data.items():
            if v is not None and hasattr(doc, k):
                setattr(doc, k, v)
        doc.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(doc)
        return doc

    def delete_rule_document(self, doc_id: str) -> bool:
        doc = self.get_rule_document_by_id(doc_id)
        if not doc:
            return False
        self.db.delete(doc)
        self.db.commit()
        return True

    def get_rule_document_items(self, doc_id: str) -> List[RuleDocumentItem]:
        return self.db.query(RuleDocumentItem).filter(RuleDocumentItem.rule_document_id == doc_id).all()

    def get_rule_document_item_by_id(self, item_id: str) -> Optional[RuleDocumentItem]:
        return self.db.query(RuleDocumentItem).filter(RuleDocumentItem.id == item_id).first()

    def update_rule_document_item(self, item_id: str, update_data: Dict[str, Any]) -> Optional[RuleDocumentItem]:
        item = self.get_rule_document_item_by_id(item_id)
        if not item:
            return None
        for k, v in update_data.items():
            if v is not None and hasattr(item, k):
                setattr(item, k, v)
        self.db.commit()
        self.db.refresh(item)
        return item

    def delete_rule_document_item(self, item_id: str) -> bool:
        item = self.get_rule_document_item_by_id(item_id)
        if not item:
            return False
        doc = item.document
        self.db.delete(item)
        if doc:
            doc.items_count = max(0, doc.items_count - 1)
            if item.item_type in ["rule", "regla", "article"]:
                doc.rules_count = max(0, doc.rules_count - 1)
            doc.updated_at = datetime.utcnow()
        self.db.commit()
        return True

    def confirm_rule_document_content(
        self,
        doc_id: str,
        confirmed_item_ids: Optional[List[str]] = None,
        user_id: str = "system"
    ) -> Dict[str, Any]:
        """
        Confirma las reglas válidas dentro del documento normativo incorporado.
        Actualiza el estado del documento a 'confirmado'.
        """
        doc = self.get_rule_document_by_id(doc_id)
        if not doc:
            raise ValueError(f"Documento normativo '{doc_id}' no encontrado.")

        items = self.get_rule_document_items(doc_id)
        
        if confirmed_item_ids is not None:
            for it in items:
                if it.id in confirmed_item_ids:
                    it.status = "validada"
                else:
                    if it.status != "eliminado":
                        it.status = "por_confirmar"
        
        valid_count = sum(1 for it in items if it.status in ["validada", "active", "accepted"])
        doc.rules_count = valid_count
        doc.status = "confirmado"
        doc.metadata_info = {
            **(doc.metadata_info or {}),
            "content_confirmed_at": datetime.utcnow().isoformat(),
            "content_confirmed_by": user_id,
            "confirmed_rules_count": valid_count
        }
        doc.updated_at = datetime.utcnow()
        self.db.commit()

        return {
            "message": f"Contenido del documento '{doc.title}' confirmado con {valid_count} reglas válidas.",
            "document_id": doc.id,
            "status": doc.status,
            "confirmed_rules_count": valid_count
        }

    def promote_rule_document_to_baseline(
        self,
        doc_id: str,
        user_id: str = "system"
    ) -> Dict[str, Any]:
        """
        Promueve las reglas validadas/confirmadas de un Documento Normativo
        hacia las Reglas Baseline QA/QC del Sistema (tabla rule_definitions).
        - Solo promueve reglas con status in ['validada', 'active', 'accepted'].
        - Reglas en 'por_confirmar' o 'eliminado' NO se promueven.
        - Genera auditoría y trazabilidad completa.
        """
        from app.db.models.decision_memory import RuleDefinition

        doc = self.get_rule_document_by_id(doc_id)
        if not doc:
            raise ValueError(f"Documento normativo '{doc_id}' no encontrado.")

        items = self.get_rule_document_items(doc_id)
        valid_items = [it for it in items if it.status in ["validada", "active", "accepted"]]

        if not valid_items:
            raise ValueError("El documento no tiene reglas confirmadas/validadas para promover a Baseline.")

        promoted_codes: List[str] = []
        for idx, item in enumerate(valid_items, 1):
            # Formatear código de regla determinística
            code = item.code_or_number
            if not code or not code.strip():
                disc_code = (doc.discipline or "GEN").upper()[:3]
                code = f"RULE_{disc_code}_{doc.id[:6].upper()}_{idx:02d}"
            
            clean_code = re.sub(r"[^A-Za-z0-9_]+", "_", code).upper()

            # Buscar si ya existe la definición
            existing_rule = self.db.query(RuleDefinition).filter(RuleDefinition.code == clean_code).first()
            if existing_rule:
                existing_rule.name = item.title
                existing_rule.description = item.description or item.content_text or item.title
                existing_rule.discipline = doc.discipline or "general"
                existing_rule.version = doc.version or "1.0"
                existing_rule.category = "normative_compliance"
                existing_rule.input_requirements = {
                    "source_document_id": doc.id,
                    "source_document_title": doc.title,
                    "rule_document_item_id": item.id,
                    "authority": doc.authority
                }
                existing_rule.is_active = True
                existing_rule.updated_at = datetime.utcnow()
                rule_def_id = existing_rule.id
            else:
                new_rule = RuleDefinition(
                    code=clean_code,
                    name=item.title,
                    category="normative_compliance",
                    discipline=doc.discipline or "general",
                    severity_default="high" if any(w in (item.title + " " + (item.description or "")).lower() for w in ["fuego", "incendio", "evacuacion", "seguridad", "peligro"]) else "medium",
                    description=item.description or item.content_text or item.title,
                    input_requirements={
                        "source_document_id": doc.id,
                        "source_document_title": doc.title,
                        "rule_document_item_id": item.id,
                        "authority": doc.authority
                    },
                    rule_logic_type="normative_check",
                    is_active=True,
                    version=doc.version or "1.0",
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                self.db.add(new_rule)
                self.db.flush()
                rule_def_id = new_rule.id

            # Guardar metadatos de auditoría en el item
            item.metadata_payload = {
                **(item.metadata_payload or {}),
                "promoted_to_baseline": True,
                "promoted_at": datetime.utcnow().isoformat(),
                "promoted_by": user_id,
                "rule_definition_id": rule_def_id,
                "baseline_code": clean_code
            }
            promoted_codes.append(clean_code)

        # Actualizar estado del documento
        doc.status = "promovido_baseline"
        doc.metadata_info = {
            **(doc.metadata_info or {}),
            "promoted_to_baseline_at": datetime.utcnow().isoformat(),
            "promoted_by": user_id,
            "promoted_rules_count": len(promoted_codes),
            "promoted_codes": promoted_codes
        }
        doc.updated_at = datetime.utcnow()
        self.db.commit()

        return {
            "message": f"Se promovieron exitosamente {len(promoted_codes)} reglas al Baseline QA/QC del Sistema.",
            "document_id": doc.id,
            "promoted_count": len(promoted_codes),
            "rule_codes": promoted_codes
        }
