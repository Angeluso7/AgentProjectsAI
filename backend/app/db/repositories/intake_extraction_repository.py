import os
import uuid
import base64
import re
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_, and_

from app.core.settings import settings
from app.db.models.intake_extractions import (
    SourceExtraction, ExtractedItem, RuleDocument, RuleDocumentItem, SupportingKnowledgeItem, WebSearchHistory
)
from app.db.models.active_learning import KnowledgeLibraryEntry
from app.db.models.intake import SourceAsset
from app.db.models.core import Organization
from app.services.rules.deduplication_service import RuleDeduplicationService

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
                status="active"
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
        candidate_type: Optional[str] = None,
        code_or_number: Optional[str] = None,
        description: Optional[str] = None,
        content_text: Optional[str] = None,
        derived_text: Optional[str] = None,
        ocr_text: Optional[str] = None,
        caption_or_context: Optional[str] = None,
        disclaimer_notes: Optional[str] = None,
        crop_image_base64: Optional[str] = None,
        crop_image_path: Optional[str] = None,
        bbox_normalized: Optional[List[float]] = None,
        page_number: int = 1,
        parent_item_id: Optional[str] = None,
        is_derived: bool = False,
        split_mode: Optional[str] = None,
        evidence_references: Optional[List[str]] = None,
        technical_parameters: Optional[Dict[str, Any]] = None,
        target_destination: str = "rules_engine",
        review_status: str = "draft",
        structured_matrix: Optional[Dict[str, Any]] = None,
        validated_at: Optional[datetime] = None,
        validated_by: Optional[str] = None,
        source_origin: str = "document",
        source_reference: Optional[str] = None,
        item_nature: str = "official_rule",
        governance_note: Optional[str] = None,
        metadata_payload: Optional[Dict[str, Any]] = None,
        completeness_status: Optional[str] = None,
        enrichment_status: str = "not_enriched",
        requires_validation: bool = True,
        enriched_from_web: bool = False,
        enrichment_method: Optional[str] = None,
        match_confidence: float = 0.0,
        suggested_title: Optional[str] = None,
        suggested_description: Optional[str] = None,
        suggested_function: Optional[str] = None,
        suggested_source_url: Optional[str] = None,
        suggested_source_label: Optional[str] = None
    ) -> ExtractedItem:
        extraction = self.get_extraction_by_id(extraction_id)
        if not extraction:
            raise ValueError(f"Sesión de extracción {extraction_id} no encontrada.")

        item_id = str(uuid.uuid4())
        final_crop_path = crop_image_path

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
                final_crop_path = f"/data/crops/extractions/{filename}"
            except Exception as e:
                print(f"Error guardando recorte de extracción: {e}")

        # Evaluar Deduplicación y Matching contra Motor de Reglas QA/QC
        dedup_service = RuleDeduplicationService(self.db)
        existing_rules = dedup_service.get_existing_qaqc_rules(
            organization_id=extraction.organization_id,
            project_id=extraction.project_id
        )
        match_res = dedup_service.match_candidate(
            candidate_code=code_or_number,
            candidate_title=title,
            candidate_content=content_text or description,
            candidate_discipline=(technical_parameters or {}).get("primary_discipline") or extraction.discipline,
            candidate_item_type=item_type,
            existing_rules=existing_rules
        )

        # Determinar completitud si no fue provista explícitamente
        if not completeness_status:
            clean_t = (title or "").strip().lower()
            clean_d = (description or "").strip()
            clean_f = (technical_parameters or {}).get("function_or_role", "").strip() if technical_parameters else ""
            is_gen = not clean_t or clean_t.startswith("símbolo") or clean_t == "desconocido" or clean_t.startswith("imagen / equipo")
            if not is_gen and len(clean_d) >= 15 and len(clean_f) >= 10:
                completeness_status = "complete"
            elif not is_gen and (len(clean_d) >= 15 or len(clean_f) >= 10):
                completeness_status = "partial"
            else:
                completeness_status = "missing_data"

        # Inicializar linaje por campo
        initial_prov = {
            "title": {
                "original_raw": title,
                "ocr_extracted": ocr_text,
                "suggested_value": suggested_title,
                "suggestion_source": suggested_source_label or enrichment_method,
                "suggestion_confidence": match_confidence,
                "accepted_value": title,
                "accepted_from": "original_raw",
                "updated_by": "system",
                "updated_at": datetime.utcnow().isoformat()
            }
        }
        if description:
            initial_prov["description"] = {
                "original_raw": description,
                "ocr_extracted": ocr_text,
                "suggested_value": suggested_description,
                "suggestion_source": suggested_source_label or enrichment_method,
                "suggestion_confidence": match_confidence,
                "accepted_value": description,
                "accepted_from": "original_raw",
                "updated_by": "system",
                "updated_at": datetime.utcnow().isoformat()
            }

        item = ExtractedItem(
            id=item_id,
            extraction_id=extraction_id,
            item_type=item_type,
            candidate_type=candidate_type,
            title=title,
            code_or_number=code_or_number,
            description=description,
            content_text=content_text,
            derived_text=derived_text,
            ocr_text=ocr_text,
            caption_or_context=caption_or_context,
            disclaimer_notes=disclaimer_notes,
            crop_image_path=final_crop_path,
            bbox_normalized=bbox_normalized or [],
            page_number=page_number,
            discipline=(technical_parameters or {}).get("primary_discipline") or extraction.discipline or "general",
            source_asset_id=extraction.source_asset_id,
            parent_item_id=parent_item_id,
            is_derived=is_derived,
            split_mode=split_mode,
            evidence_references=evidence_references or [],
            technical_parameters=technical_parameters or {},
            target_destination=target_destination,
            review_status=review_status,
            duplicate_status=match_res["duplicate_status"],
            best_match_rule_id=match_res["best_match_rule_id"],
            best_match_rule_code=match_res["best_match_rule_code"],
            best_match_title=match_res["best_match_title"],
            best_match_discipline=match_res["best_match_discipline"],
            duplicate_reason=match_res["duplicate_reason"],
            duplicate_confidence=match_res["duplicate_confidence"],
            blocked_from_acceptance=match_res["blocked_from_acceptance"],
            completeness_status=completeness_status,
            enrichment_status=enrichment_status,
            requires_validation=requires_validation,
            enriched_from_web=enriched_from_web,
            enrichment_method=enrichment_method,
            match_confidence=match_confidence,
            suggested_title=suggested_title,
            suggested_description=suggested_description,
            suggested_function=suggested_function,
            suggested_source_url=suggested_source_url,
            suggested_source_label=suggested_source_label,
            field_provenance=initial_prov,
            structured_matrix=structured_matrix or {},
            validated_at=validated_at,
            validated_by=validated_by,
            source_origin=source_origin,
            source_reference=source_reference,
            item_nature=item_nature,
            governance_note=governance_note,
            metadata_payload={
                **(metadata_payload or {}),
                "duplicate_status": match_res["duplicate_status"],
                "best_match_rule_code": match_res["best_match_rule_code"],
                "best_match_title": match_res["best_match_title"],
                "blocked_from_acceptance": match_res["blocked_from_acceptance"],
                "duplicate_reason": match_res["duplicate_reason"]
            },
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        self.db.add(item)
        
        # Sincronizar persistencia estructurada tipada
        from app.services.extraction.candidate_enrichment_service import CandidateEnrichmentService
        CandidateEnrichmentService(self.db).sync_structured_models(item)

        # Actualizar contador
        extraction.total_items = (extraction.total_items or 0) + 1
        extraction.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(item)
        return item

    def list_extracted_items(
        self,
        extraction_id: str,
        item_type: Optional[str] = None,
        completeness_status: Optional[str] = None,
        review_status: Optional[str] = None,
        discipline: Optional[str] = None,
        source_origin: Optional[str] = None,
        query: Optional[str] = None
    ) -> List[ExtractedItem]:
        """Consulta con filtrado completo por tipo, completitud, revisión y búsqueda textual."""
        q = self.db.query(ExtractedItem).filter(ExtractedItem.extraction_id == extraction_id)
        if item_type and item_type != "all":
            q = q.filter(ExtractedItem.item_type == item_type)
        if completeness_status and completeness_status != "all":
            q = q.filter(ExtractedItem.completeness_status == completeness_status)
        if review_status and review_status != "all":
            q = q.filter(ExtractedItem.review_status == review_status)
        if discipline and discipline != "all":
            q = q.filter(ExtractedItem.discipline == discipline)
        if source_origin and source_origin != "all":
            q = q.filter(ExtractedItem.source_origin == source_origin)
        if query:
            pattern = f"%{query.strip()}%"
            from sqlalchemy import or_
            q = q.filter(
                or_(
                    ExtractedItem.title.ilike(pattern),
                    ExtractedItem.code_or_number.ilike(pattern),
                    ExtractedItem.description.ilike(pattern),
                    ExtractedItem.ocr_text.ilike(pattern)
                )
            )
        return q.order_by(ExtractedItem.page_number.asc(), ExtractedItem.created_at.asc()).all()

    def list_extracted_candidates(
        self,
        extraction_id: str,
        candidate_type: Optional[str] = None,
        review_status: Optional[str] = None,
        page_number: Optional[int] = None
    ) -> List[ExtractedItem]:
        """Consulta filtrada de candidatos generados en una sesión de extracción."""
        query = self.db.query(ExtractedItem).filter(ExtractedItem.extraction_id == extraction_id)
        if candidate_type:
            query = query.filter(ExtractedItem.candidate_type == candidate_type)
        if review_status:
            query = query.filter(ExtractedItem.review_status == review_status)
        if page_number:
            query = query.filter(ExtractedItem.page_number == page_number)
        return query.order_by(ExtractedItem.page_number.asc(), ExtractedItem.created_at.asc()).all()

    def get_extracted_item_by_id(self, item_id: str) -> Optional[ExtractedItem]:
        """Obtiene un elemento extraído por su ID único."""
        return self.db.query(ExtractedItem).filter(ExtractedItem.id == item_id).first()

    def update_extracted_item(
        self,
        item_id: str,
        update_data: Dict[str, Any]
    ) -> Optional[ExtractedItem]:
        item = self.db.query(ExtractedItem).filter(ExtractedItem.id == item_id).first()
        if not item:
            return None

        # Validación de bloqueo estricto: impedir aceptación de regla candidata si ya existe en el Motor QA/QC
        new_status = update_data.get("review_status")
        if new_status in ["accepted", "validada", "confirmado", "promovido_baseline"]:
            if item.blocked_from_acceptance or item.duplicate_status == "exact_match_existing_rule":
                raise ValueError(
                    f"La regla candidata '{item.title}' ya existe en el Motor de Reglas QA/QC "
                    f"(Código: {item.best_match_rule_code or 'REG-EXISTENTE'}) y no puede incorporarse nuevamente."
                )

        for k, v in update_data.items():
            if hasattr(item, k):
                setattr(item, k, v)
        item.updated_at = datetime.utcnow()

        # Sincronizar persistencia estructurada tipada
        from app.services.extraction.candidate_enrichment_service import CandidateEnrichmentService
        CandidateEnrichmentService(self.db).sync_structured_models(item)

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

        # Validación obligatoria de deduplicación: Ninguna regla bloqueada puede promoverse
        for it in items_to_commit:
            if it.blocked_from_acceptance or it.duplicate_status == "exact_match_existing_rule":
                raise ValueError(
                    f"La regla candidata '{it.title}' ya existe en el Motor de Reglas QA/QC "
                    f"(Código: {it.best_match_rule_code or 'REG-EXISTENTE'}) y no puede incorporarse nuevamente."
                )

        rules_count = sum(1 for it in items_to_commit if it.item_type in ["rule", "restriction", "requirement", "article", "chapter", "text_note", "definition", "procedure"])
        tables_count = sum(1 for it in items_to_commit if it.item_type == "table")
        symbols_count = sum(1 for it in items_to_commit if it.item_type in ["symbol", "simbolo", "symbol_candidate"])
        images_count = sum(1 for it in items_to_commit if it.item_type in ["image", "figure", "sello", "firma", "leyenda", "vineta", "foto", "otro"])

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
            symbols_count=symbols_count,
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
                    "candidate_type": it.candidate_type,
                    "derived_text": it.derived_text,
                    "disclaimer_notes": it.disclaimer_notes,
                    "technical_parameters": it.technical_parameters or {},
                    "evidence_references": it.evidence_references or [],
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
                        "candidate_type": it.candidate_type,
                        "derived_text": it.derived_text,
                        "disclaimer_notes": it.disclaimer_notes,
                        "technical_parameters": it.technical_parameters or {},
                        "evidence_references": it.evidence_references or [],
                        "source_origin": it.source_origin,
                        "source_reference": it.source_reference
                    },
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                self.db.add(sup_item)
                supporting_items_created += 1

                # C) Integración a Base de Conocimiento Reutilizable (KnowledgeItem) con gobernanza aprobada
                try:
                    from app.db.models.knowledge_base import KnowledgeItem
                    from app.services.knowledge.service import KnowledgeBaseService

                    k_domain = "normative_knowledge" if extraction.document_type == "norma" else "rule_knowledge"
                    k_modality = "table" if it.item_type in ["table", "tabla"] else ("symbol" if it.item_type in ["symbol", "simbolo"] else "text")

                    k_item = KnowledgeItem(
                        id=str(uuid.uuid4()),
                        organization_id=extraction.organization_id,
                        project_id=extraction.project_id,
                        domain=k_domain,
                        item_type=it.candidate_type or it.item_type,
                        title=it.title,
                        summary=it.description or it.derived_text,
                        content_text=it.content_text or it.title,
                        structured_payload=it.structured_matrix or it.technical_parameters or {},
                        discipline=extraction.discipline,
                        status="validated",
                        is_active_for_reuse=True,
                        confidence_score=1.0,
                        version_number=1,
                        author="user_reviewer",
                        origin_type="auto_extraction",
                        ingestion_channel="manual_intake",
                        modality=k_modality,
                        visual_crop_url=it.crop_image_path,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                    self.db.add(k_item)
                    self.db.flush()

                    kb_service = KnowledgeBaseService(self.db)
                    chunks = kb_service._generate_chunks_for_item(k_item)
                    self.db.flush()
                    kb_service.vector_store.upsert_approved_chunks(
                        organization_id=extraction.organization_id,
                        project_id=extraction.project_id,
                        chunks=chunks,
                        item=k_item
                    )
                except Exception as ex:
                    print(f"Aviso en sincronización de KnowledgeItem: {ex}")

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
        
        valid_rules = [it for it in items if it.status in ["validada", "active", "accepted"] and it.item_type not in ["symbol", "simbolo", "symbol_candidate", "table"]]
        valid_symbols = [it for it in items if it.status in ["validada", "active", "accepted"] and it.item_type in ["symbol", "simbolo", "symbol_candidate"]]
        doc.rules_count = len(valid_rules)
        doc.symbols_count = len(valid_symbols)
        doc.status = "confirmado"
        doc.metadata_info = {
            **(doc.metadata_info or {}),
            "content_confirmed_at": datetime.utcnow().isoformat(),
            "content_confirmed_by": user_id,
            "confirmed_rules_count": len(valid_rules),
            "confirmed_symbols_count": len(valid_symbols)
        }
        doc.updated_at = datetime.utcnow()
        self.db.commit()

        return {
            "message": f"Contenido del documento '{doc.title}' confirmado con {len(valid_rules)} reglas y {len(valid_symbols)} símbolos válidos.",
            "document_id": doc.id,
            "status": doc.status,
            "confirmed_rules_count": len(valid_rules)
        }

    def promote_rule_document_to_baseline(
        self,
        doc_id: str,
        user_id: str = "system"
    ) -> Dict[str, Any]:
        """
        Promueve las reglas validadas/confirmadas de un Documento Normativo
        hacia las Reglas Baseline QA/QC del Sistema utilizando el servicio canónico
        RulePromotionService.
        - Solo promueve reglas con status in ['validada', 'active', 'accepted'].
        - Reglas en 'por_confirmar' o 'eliminado' NO se promueven.
        - Excluye estrictamente elementos tipo 'symbol'/'simbolo'.
        - Crea RuleDefinition, RuleApplicability approved y registros de auditoría.
        """
        from app.services.rules.promotion_service import RulePromotionService
        from app.schemas.rule_candidates import PromoteRuleCandidateRequest
        from app.db.models.decision_memory import ReviewDiscipline, ReviewTopic

        doc = self.get_rule_document_by_id(doc_id)
        if not doc:
            raise ValueError(f"Documento normativo '{doc_id}' no encontrado.")

        items = self.get_rule_document_items(doc_id)
        valid_items = [
            it for it in items 
            if it.status in ["validada", "active", "accepted"] 
            and it.item_type not in ["symbol", "simbolo", "symbol_candidate", "table", "tabla", "figure", "figura", "image"]
        ]

        if not valid_items:
            raise ValueError("El documento no tiene reglas confirmadas/validadas para promover a Baseline (los símbolos se gestionan en Curación de Símbolos).")

        # Determinar especialidad técnica y tópico para aplicabilidad canónica
        doc_disc_str = (doc.discipline or "general").upper()
        matched_disc = self.db.query(ReviewDiscipline).filter(
            or_(ReviewDiscipline.code == doc_disc_str, ReviewDiscipline.code == "GENERAL")
        ).first()
        disc_code = matched_disc.code if matched_disc else "GENERAL"

        # Buscar tópico correspondiente o transversal
        topic = self.db.query(ReviewTopic).filter(
            or_(
                ReviewTopic.discipline_id == (matched_disc.id if matched_disc else None),
                ReviewTopic.is_transversal.is_(True),
                ReviewTopic.code == "PID_SYMBOLS"
            )
        ).first()
        topic_code = topic.code if topic else "PID_SYMBOLS"

        promoted_codes: List[str] = []
        for idx, item in enumerate(valid_items, 1):
            code = item.code_or_number
            if not code or not code.strip():
                disc_prefix = (doc.discipline or "GEN").upper()[:3]
                code = f"RULE_{disc_prefix}_{doc.id[:6].upper()}_{idx:02d}"

            payload = PromoteRuleCandidateRequest(
                decision="approve",
                action="promote_and_activate",
                reviewer_rationale=f"Promoción masiva aprobada desde documento '{doc.title}'.",
                rule_code=code,
                title=item.title,
                severity="high" if any(w in (item.title + " " + (item.description or "")).lower() for w in ["fuego", "incendio", "evacuacion", "seguridad", "peligro"]) else "medium",
                discipline_ids=[disc_code],
                topic_ids=[topic_code],
                execution_phase=6,
                enabled=True
            )

            res = RulePromotionService.promote_candidate(
                db=self.db,
                candidate_id=item.id,
                payload=payload,
                user_id=user_id,
                user_role="admin",
                organization_id=doc.organization_id
            )
            if res.rule_code:
                promoted_codes.append(res.rule_code)

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

    # =========================================================
    # HISTORIAL DE BÚSQUEDAS WEB & AUDITORÍA DE INGESTA
    # =========================================================

    def create_web_search_history_entry(
        self,
        search_prompt: str,
        discipline: str = "general",
        document_type: str = "any_web_doc",
        provider_used: str = "duckduckgo",
        detected_language: str = "es",
        results_found: Optional[List[Dict[str, Any]]] = None,
        discarded_sources: Optional[List[Dict[str, Any]]] = None,
        selected_sources: Optional[List[Dict[str, Any]]] = None,
        stage_applied: str = "stage_1_strict",
        extraction_status: str = "searched",
        project_id: Optional[str] = None,
        user_id: Optional[str] = None,
        source_extraction_id: Optional[str] = None,
        metadata_payload: Optional[Dict[str, Any]] = None
    ) -> WebSearchHistory:
        """Crea y persiste un registro de auditoría de búsqueda web."""
        org = self.get_or_create_default_org()
        entry = WebSearchHistory(
            id=str(uuid.uuid4()),
            organization_id=org.id,
            project_id=project_id,
            user_id=user_id,
            search_prompt=search_prompt,
            discipline=discipline,
            document_type=document_type,
            provider_used=provider_used,
            detected_language=detected_language,
            results_found=results_found or [],
            discarded_sources=discarded_sources or [],
            selected_sources=selected_sources or [],
            stage_applied=stage_applied,
            extraction_status=extraction_status,
            source_extraction_id=source_extraction_id,
            metadata_payload=metadata_payload or {},
            created_at=datetime.utcnow()
        )
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def list_web_search_history(
        self,
        project_id: Optional[str] = None,
        discipline: Optional[str] = None,
        limit: int = 50
    ) -> List[WebSearchHistory]:
        """Obtiene el historial de búsquedas web ordenado cronológicamente desc."""
        query = self.db.query(WebSearchHistory)
        if project_id:
            query = query.filter(WebSearchHistory.project_id == project_id)
        if discipline:
            query = query.filter(WebSearchHistory.discipline == discipline)
        return query.order_by(desc(WebSearchHistory.created_at)).limit(limit).all()

    def get_web_search_history_by_id(self, history_id: str) -> Optional[WebSearchHistory]:
        """Recupera un registro de historial por ID."""
        return self.db.query(WebSearchHistory).filter(WebSearchHistory.id == history_id).first()

    def update_web_search_history_extraction(
        self,
        history_id: str,
        source_extraction_id: str,
        selected_sources: Optional[List[Dict[str, Any]]] = None,
        status: str = "extracted"
    ) -> Optional[WebSearchHistory]:
        """Actualiza un registro de historial tras la extracción."""
        entry = self.get_web_search_history_by_id(history_id)
        if entry:
            entry.source_extraction_id = source_extraction_id
            entry.extraction_status = status
            if selected_sources is not None:
                entry.selected_sources = selected_sources
            self.db.commit()
            self.db.refresh(entry)
        return entry

