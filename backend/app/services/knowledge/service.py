import uuid
import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc

from app.db.models.knowledge_base import KnowledgeItem, KnowledgeChunk
from app.db.models.core import Project
from app.db.models.intake import SourceAsset
from app.db.models.normative_memory import NormativeCriterion, NormativeDocument, NormativeClause
from app.db.models.decision_memory import RuleDefinition
from app.db.models.completeness import ProjectDeliverableRequirement
from app.db.models.observations import AuditObservation
from app.db.models.reporting import ProjectStageReportSnapshot
from app.schemas.knowledge_base import (
    KnowledgeItemCreate, KnowledgeItemUpdate, KnowledgeItemTransitionRequest,
    KnowledgeItemVersionRequest, KnowledgeSearchQuery, KnowledgeSearchResultItem,
    KnowledgeSearchResponse, KnowledgeBaseStatsRead, KnowledgeSyncResponse
)
from app.services.knowledge.vector_store import VectorStore
from app.core.logging import logger

class KnowledgeBaseService:
    def __init__(self, db: Session, in_memory_vector: bool = False, vector_store: Optional[VectorStore] = None):
        self.db = db
        self.vector_store = vector_store or VectorStore(in_memory=in_memory_vector)

    def sync_seed_knowledge(self) -> Dict[str, Any]:
        """Sincroniza archivos o recursos de semilla para la base de conocimiento."""
        return {"yaml": 0, "json": 0, "items": 0, "chunks": 0}

    # =========================================================================
    # CHUNKING ESTRUCTURAL Y METADATOS
    # =========================================================================
    def _build_chunk_metadata(self, item: KnowledgeItem, chunk_type: str) -> Dict[str, Any]:
        return {
            "item_id": item.id,
            "domain": item.domain,
            "item_type": item.item_type,
            "title": item.title,
            "discipline": item.discipline,
            "stage": item.stage,
            "project_id": item.project_id,
            "tags": item.tags or [],
            "version_number": item.version_number,
            "is_active_for_reuse": item.is_active_for_reuse,
            "chunk_type": chunk_type
        }

    def _build_markdown_table_snippet(self, headers: List[str], rows: List[List[Any]]) -> str:
        if not headers and not rows:
            return ""
        clean_headers = [str(h).replace("|", "/") for h in headers]
        if not clean_headers and rows:
            clean_headers = [f"Col {i+1}" for i in range(len(rows[0]))]
        header_line = "| " + " | ".join(clean_headers) + " |"
        sep_line = "| " + " | ".join(["---"] * len(clean_headers)) + " |"
        row_lines = []
        for r in rows:
            padded = list(r) + [""] * (len(clean_headers) - len(r))
            clean_r = [str(c).replace("|", "/").replace("\n", " ") for c in padded[:len(clean_headers)]]
            row_lines.append("| " + " | ".join(clean_r) + " |")
        return "\n".join([header_line, sep_line] + row_lines)

    def _generate_chunks_for_item(self, item: KnowledgeItem) -> List[KnowledgeChunk]:
        """Divide el contenido en fragmentos indexables con chunking estructural para piping y specs."""
        # Eliminar chunks previos si existen
        self.db.query(KnowledgeChunk).filter(KnowledgeChunk.knowledge_item_id == item.id).delete()
        
        text = (item.content_text or "").strip()
        if not text:
            return []

        created_chunks: List[KnowledgeChunk] = []
        payload = item.structured_payload or {}

        # 1. Chunking de Tablas Técnicas (Line Lists, Valve Schedules, Specs)
        if item.modality == "table" or "headers" in payload or "rows" in payload:
            headers = payload.get("headers", [])
            rows = payload.get("rows", [])
            table_name = payload.get("table_name", item.title)
            
            if rows:
                batch_size = 5 # Bloques de 5 filas por chunk para mantener granularidad técnica
                for b_idx in range(0, len(rows), batch_size):
                    batch_rows = rows[b_idx:b_idx + batch_size]
                    md_chunk = self._build_markdown_table_snippet(headers, batch_rows)
                    c_idx = len(created_chunks)
                    
                    chunk = KnowledgeChunk(
                        id=str(uuid.uuid4()),
                        knowledge_item_id=item.id,
                        chunk_index=c_idx,
                        chunk_title=f"{item.title} - Filas {b_idx + 1} a {min(b_idx + len(batch_rows), len(rows))}",
                        chunk_type="table_chunk",
                        hierarchy_path=f"/{table_name}/Filas_{b_idx + 1}_{min(b_idx + len(batch_rows), len(rows))}",
                        chunk_text=md_chunk,
                        token_count=int(len(md_chunk.split()) * 1.35),
                        structured_data={
                            "table_name": table_name,
                            "headers": headers,
                            "rows": batch_rows,
                            "row_start": b_idx + 1,
                            "row_end": min(b_idx + len(batch_rows), len(rows))
                        },
                        metadata_payload=self._build_chunk_metadata(item, "table_chunk")
                    )
                    self.db.add(chunk)
                    created_chunks.append(chunk)

        # 2. Chunking por Secciones Normativas / Técnicas
        elif "CAPÍTULO" in text.upper() or "## " in text or "SECCIÓN" in text.upper():
            raw_sections = re.split(r"(?=(?:^|\n)#{1,3}\s+|(?:^|\n)(?:CAP[ÍI]TULO|SECCI[ÓO]N)\s+)", text, flags=re.IGNORECASE)
            for s_idx, sec_text in enumerate(raw_sections):
                s_clean = sec_text.strip()
                if not s_clean:
                    continue
                first_line = s_clean.split("\n")[0].replace("#", "").strip()
                chunk = KnowledgeChunk(
                    id=str(uuid.uuid4()),
                    knowledge_item_id=item.id,
                    chunk_index=s_idx,
                    chunk_title=f"{item.title}: {first_line[:60]}",
                    chunk_type="section_chunk",
                    hierarchy_path=f"/{item.title}/{first_line[:40].replace(' ', '_')}",
                    chunk_text=s_clean,
                    token_count=int(len(s_clean.split()) * 1.35),
                    structured_data={"section_title": first_line},
                    metadata_payload=self._build_chunk_metadata(item, "section_chunk")
                )
                self.db.add(chunk)
                created_chunks.append(chunk)

        # 3. Chunking de Bloques CAD / DXF
        elif item.domain == "cad_knowledge" or "blocks_inserted" in payload:
            blocks = payload.get("blocks_inserted", [])
            chunk = KnowledgeChunk(
                id=str(uuid.uuid4()),
                knowledge_item_id=item.id,
                chunk_index=0,
                chunk_title=f"Bloques CAD: {item.title}",
                chunk_type="dxf_block_summary",
                hierarchy_path=f"/{item.title}/CAD_Blocks",
                chunk_text=text,
                token_count=int(len(text.split()) * 1.35),
                structured_data={"blocks_count": len(blocks)},
                metadata_payload=self._build_chunk_metadata(item, "dxf_block_summary")
            )
            self.db.add(chunk)
            created_chunks.append(chunk)

        # 4. Fallback Párrafos Estructurados
        if not created_chunks:
            raw_paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
            chunks_text_list: List[str] = []
            current_block = ""
            for p in raw_paragraphs:
                if len(current_block) + len(p) < 800:
                    current_block = f"{current_block}\n\n{p}".strip() if current_block else p
                else:
                    if current_block:
                        chunks_text_list.append(current_block)
                    current_block = p
            if current_block:
                chunks_text_list.append(current_block)

            for idx, c_text in enumerate(chunks_text_list):
                words = len(c_text.split())
                chunk = KnowledgeChunk(
                    id=str(uuid.uuid4()),
                    knowledge_item_id=item.id,
                    chunk_index=idx,
                    chunk_title=f"{item.title} (Parte {idx + 1})" if len(chunks_text_list) > 1 else item.title,
                    chunk_type="technical_note",
                    hierarchy_path=f"/{item.title}/Parte_{idx + 1}",
                    chunk_text=c_text,
                    token_count=int(words * 1.35),
                    structured_data={},
                    metadata_payload=self._build_chunk_metadata(item, "technical_note")
                )
                self.db.add(chunk)
                created_chunks.append(chunk)

        self.db.flush()

        # Si el item cumple gobernanza activa de reuso, indexar en Qdrant
        if item.is_active_for_reuse and item.status in ["validated", "approved_for_reuse"]:
            self.vector_store.upsert_approved_chunks(
                organization_id=item.organization_id,
                project_id=item.project_id,
                chunks=created_chunks,
                item=item
            )

        return created_chunks

    # =========================================================================
    # CRUD & LIFECYCLE
    # =========================================================================
    def list_items(
        self,
        organization_id: str,
        project_id: Optional[str] = None,
        domain: Optional[str] = None,
        status: Optional[str] = None,
        discipline: Optional[str] = None,
        stage: Optional[str] = None,
        active_only: bool = False,
        search: Optional[str] = None,
        include_global: bool = True,
        skip: int = 0,
        limit: int = 100
    ) -> Tuple[List[KnowledgeItem], int]:
        """Lista unidades de conocimiento con filtros de gobernanza y aislamiento."""
        q = self.db.query(KnowledgeItem).filter(KnowledgeItem.organization_id == organization_id)

        # Filtro de Proyecto vs Global
        if project_id:
            if include_global:
                q = q.filter(or_(KnowledgeItem.project_id == project_id, KnowledgeItem.project_id.is_(None)))
            else:
                q = q.filter(KnowledgeItem.project_id == project_id)
        elif not include_global:
            q = q.filter(KnowledgeItem.project_id.is_(None))

        if domain:
            q = q.filter(KnowledgeItem.domain == domain)
        if status:
            q = q.filter(KnowledgeItem.status == status)
        if discipline:
            q = q.filter(KnowledgeItem.discipline == discipline)
        if stage:
            q = q.filter(KnowledgeItem.stage == stage)
        if active_only:
            q = q.filter(KnowledgeItem.is_active_for_reuse.is_(True))

        if search:
            search_pattern = f"%{search}%"
            q = q.filter(
                or_(
                    KnowledgeItem.title.ilike(search_pattern),
                    KnowledgeItem.summary.ilike(search_pattern),
                    KnowledgeItem.content_text.ilike(search_pattern)
                )
            )

        total = q.count()
        items = q.order_by(desc(KnowledgeItem.created_at)).offset(skip).limit(limit).all()
        return items, total

    def get_item(self, item_id: str, organization_id: str) -> Optional[KnowledgeItem]:
        return self.db.query(KnowledgeItem).filter(
            KnowledgeItem.id == item_id,
            KnowledgeItem.organization_id == organization_id
        ).first()

    def create_item(self, organization_id: str, payload: KnowledgeItemCreate, author: str = "system") -> KnowledgeItem:
        now = datetime.utcnow()
        is_reusable = payload.status in ["approved_for_reuse", "validated"]

        item = KnowledgeItem(
            id=str(uuid.uuid4()),
            organization_id=organization_id,
            project_id=payload.project_id,
            domain=payload.domain.value if hasattr(payload.domain, "value") else str(payload.domain),
            item_type=payload.item_type,
            title=payload.title,
            summary=payload.summary,
            content_text=payload.content_text,
            structured_payload=payload.structured_payload or {},
            discipline=payload.discipline or "general",
            stage=payload.stage,
            status=payload.status.value if hasattr(payload.status, "value") else str(payload.status),
            is_active_for_reuse=is_reusable,
            confidence_score=payload.confidence_score,
            version_number=1,
            source_asset_id=payload.source_asset_id,
            document_id=payload.document_id,
            sheet_id=payload.sheet_id,
            rule_id=payload.rule_id,
            observation_id=payload.observation_id,
            review_run_id=payload.review_run_id,
            author=author,
            origin_type=payload.origin_type or "manual_entry",
            ingestion_channel=payload.ingestion_channel or "manual_entry",
            modality=payload.modality or "text",
            visual_crop_url=payload.visual_crop_url,
            legend_reference=payload.legend_reference,
            provenance_trace=[{
                "action": "create",
                "from_status": None,
                "to_status": payload.status.value if hasattr(payload.status, "value") else str(payload.status),
                "author": author,
                "timestamp": now.isoformat(),
                "notes": f"Unidad creada con estado inicial '{payload.status}'"
            }],
            tags=payload.tags or []
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)

        # Generar chunks para indexación
        self._generate_chunks_for_item(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def update_item(self, item_id: str, organization_id: str, payload: KnowledgeItemUpdate, author: str = "system") -> Optional[KnowledgeItem]:
        item = self.get_item(item_id, organization_id)
        if not item:
            return None

        update_dict = payload.model_dump(exclude_unset=True)
        content_changed = "content_text" in update_dict and update_dict["content_text"] != item.content_text

        for k, v in update_dict.items():
            setattr(item, k, v)

        item.updated_at = datetime.utcnow()
        trace = list(item.provenance_trace or [])
        trace.append({
            "action": "update",
            "author": author,
            "timestamp": datetime.utcnow().isoformat(),
            "notes": "Actualización de contenido/metadatos"
        })
        item.provenance_trace = trace

        if content_changed:
            self._generate_chunks_for_item(item)

        self.db.commit()
        self.db.refresh(item)
        return item

    def transition_status(
        self,
        item_id: str,
        organization_id: str,
        target_status: str,
        author: str = "system",
        notes: Optional[str] = None
    ) -> Optional[KnowledgeItem]:
        """Aplica una transición de ciclo de vida con gobernanza estricta."""
        item = self.get_item(item_id, organization_id)
        if not item:
            return None

        old_status = item.status
        item.status = target_status
        # Solo approved_for_reuse o validated son activos para recuperación automática
        item.is_active_for_reuse = target_status in ["approved_for_reuse", "validated"]
        item.updated_at = datetime.utcnow()

        trace = list(item.provenance_trace or [])
        trace.append({
            "action": "transition_status",
            "from_status": old_status,
            "to_status": target_status,
            "author": author,
            "timestamp": datetime.utcnow().isoformat(),
            "notes": notes or f"Transición de estado de {old_status} a {target_status}"
        })
        item.provenance_trace = trace

        # Actualizar flag en chunks
        for c in item.chunks:
            meta = dict(c.metadata_payload or {})
            meta["is_active_for_reuse"] = item.is_active_for_reuse
            c.metadata_payload = meta

        # Sincronización vectorial atómica
        payload_data = dict(item.structured_payload or {})
        if item.is_active_for_reuse:
            if not item.chunks:
                self._generate_chunks_for_item(item)
            ok = self.vector_store.upsert_approved_chunks(item.organization_id, item.project_id, item.chunks, item)
            payload_data["qdrant_sync_status"] = "synced" if ok else "failed"
            payload_data["qdrant_last_synced_at"] = datetime.utcnow().isoformat()
        else:
            # Desindexación inmediata ante rechazo, archivo, retiro o superseded
            self.vector_store.delete_item_vectors(item.id)
            payload_data["qdrant_sync_status"] = "purged"
            payload_data["qdrant_purged_at"] = datetime.utcnow().isoformat()

        item.structured_payload = payload_data
        self.db.commit()
        self.db.refresh(item)
        return item

    def delete_item(self, item_id: str, organization_id: str) -> bool:
        """Elimina físicamente una unidad de conocimiento y purga sus vectores en Qdrant."""
        item = self.get_item(item_id, organization_id)
        if not item:
            return False

        # Purgar vectores en Qdrant
        self.vector_store.delete_item_vectors(item.id)

        # Eliminar chunks y registro en SQL
        self.db.query(KnowledgeChunk).filter(KnowledgeChunk.knowledge_item_id == item.id).delete()
        self.db.delete(item)
        self.db.commit()
        return True

    def create_new_version(
        self,
        item_id: str,
        organization_id: str,
        payload: KnowledgeItemVersionRequest,
        author: str = "system"
    ) -> Optional[KnowledgeItem]:
        """Crea una nueva versión formal de una unidad, marcando la anterior como superseded y purgándola de Qdrant."""
        parent_item = self.get_item(item_id, organization_id)
        if not parent_item:
            return None

        now = datetime.utcnow()
        new_version_num = parent_item.version_number + 1

        new_item = KnowledgeItem(
            id=str(uuid.uuid4()),
            organization_id=organization_id,
            project_id=parent_item.project_id,
            domain=parent_item.domain,
            item_type=parent_item.item_type,
            title=payload.new_title or parent_item.title,
            summary=payload.new_summary or parent_item.summary,
            content_text=payload.new_content_text,
            structured_payload=payload.new_structured_payload or parent_item.structured_payload or {},
            discipline=parent_item.discipline,
            stage=parent_item.stage,
            status="reviewed", # Nueva versión entra en revisión
            is_active_for_reuse=False,
            confidence_score=parent_item.confidence_score,
            version_number=new_version_num,
            parent_item_id=parent_item.id,
            source_asset_id=parent_item.source_asset_id,
            document_id=parent_item.document_id,
            sheet_id=parent_item.sheet_id,
            rule_id=parent_item.rule_id,
            observation_id=parent_item.observation_id,
            review_run_id=parent_item.review_run_id,
            stage_snapshot_id=parent_item.stage_snapshot_id,
            author=author or payload.author or "system",
            origin_type=parent_item.origin_type,
            provenance_trace=[{
                "action": "new_version_created",
                "from_parent_id": parent_item.id,
                "from_version": parent_item.version_number,
                "to_version": new_version_num,
                "author": author or payload.author or "system",
                "timestamp": now.isoformat(),
                "notes": payload.change_notes
            }],
            tags=parent_item.tags or []
        )
        self.db.add(new_item)
        self.db.flush()

        # Superseder versión anterior y purgarla de Qdrant
        parent_item.status = "superseded"
        parent_item.is_active_for_reuse = False
        parent_item.superseded_by_id = new_item.id
        self.vector_store.delete_item_vectors(parent_item.id)

        p_trace = list(parent_item.provenance_trace or [])
        p_trace.append({
            "action": "superseded_by_new_version",
            "superseded_by_id": new_item.id,
            "new_version": new_version_num,
            "author": author,
            "timestamp": now.isoformat(),
            "notes": f"Reemplazado por versión {new_version_num}"
        })
        parent_item.provenance_trace = p_trace

        self._generate_chunks_for_item(new_item)
        self.db.commit()
        self.db.refresh(new_item)
        return new_item

    # =========================================================================
    # SINCRONIZACIÓN TRANSVERSAL DE MÓDULOS
    # =========================================================================
    def sync_from_intake_sources(self, organization_id: str, project_id: Optional[str] = None, author: str = "system", auto_approve: bool = False) -> int:
        """Sincroniza fuentes y criterios normativos de Intake & Fuentes hacia la Base de Conocimiento."""
        synced_count = 0
        status_target = "approved_for_reuse" if auto_approve else "extracted"
        is_reusable = auto_approve

        criteria = self.db.query(NormativeCriterion).all()
        for crit in criteria:
            crit_code = getattr(crit, "criterion_code", None) or getattr(crit, "code", "CRIT")
            standard_name = (crit.clause.document.title if crit.clause and crit.clause.document else None) or "Normativa Técnica"
            
            # Comprobar si ya existe unidad para este criterio
            existing = self.db.query(KnowledgeItem).filter(
                KnowledgeItem.organization_id == organization_id,
                KnowledgeItem.domain == "normative_knowledge",
                KnowledgeItem.structured_payload["criterion_id"].as_string() == crit.id
            ).first()

            content = (
                f"Estándar: {standard_name}\n"
                f"Código: {crit_code}\n"
                f"Nombre: {crit.name}\n"
                f"Descripción: {crit.description or 'Sin descripción'}\n"
                f"Criterio Lógico: {getattr(crit, 'evaluation_logic_type', 'threshold')}"
            )

            if not existing:
                item = KnowledgeItem(
                    id=str(uuid.uuid4()),
                    organization_id=organization_id,
                    project_id=project_id,
                    domain="normative_knowledge",
                    item_type="normative_article",
                    title=f"{crit_code}: {crit.name}",
                    summary=crit.description[:200] if crit.description else None,
                    content_text=content,
                    structured_payload={
                        "criterion_id": crit.id,
                        "code": crit_code,
                        "standard": standard_name,
                        "logic_type": getattr(crit, 'evaluation_logic_type', 'threshold'),
                        "parameters": getattr(crit, 'parameter_thresholds', {}) or {}
                    },
                    discipline="general",
                    status=status_target,
                    is_active_for_reuse=is_reusable,
                    confidence_score=1.0,
                    author=author,
                    origin_type="intake_normative_sync",
                    ingestion_channel="manual_intake",
                    modality="text",
                    tags=[standard_name, "criterio_normativo", crit_code]
                )
                self.db.add(item)
                self.db.flush()
                self._generate_chunks_for_item(item)
                synced_count += 1

        # Sincronizar SourceAssets
        q_sources = self.db.query(SourceAsset).filter(SourceAsset.organization_id == organization_id)
        if project_id:
            q_sources = q_sources.filter(or_(SourceAsset.project_id == project_id, SourceAsset.project_id.is_(None)))
        
        sources = q_sources.all()
        for src in sources:
            existing = self.db.query(KnowledgeItem).filter(
                KnowledgeItem.organization_id == organization_id,
                KnowledgeItem.source_asset_id == src.id
            ).first()

            if not existing:
                content = (
                    f"Documento Guía / Fuente: {src.title or src.filename}\n"
                    f"Tipo: {src.source_type}\n"
                    f"Categoría: {src.category}\n"
                    f"Disciplina: {src.discipline}\n"
                    f"Resumen / Descripción: {src.description or 'Fuente incorporada desde Intake'}"
                )
                item = KnowledgeItem(
                    id=str(uuid.uuid4()),
                    organization_id=organization_id,
                    project_id=src.project_id,
                    domain="guide_document_knowledge" if src.category in ["template", "guide", "cad_standard"] else "normative_knowledge",
                    item_type="guide_document_reference" if src.category in ["template", "guide"] else "normative_source_document",
                    title=f"Fuente: {src.title or src.filename}",
                    summary=src.description,
                    content_text=content,
                    structured_payload={
                        "source_asset_id": src.id,
                        "filename": src.filename,
                        "category": src.category,
                        "source_type": src.source_type
                    },
                    discipline=src.discipline or "general",
                    source_asset_id=src.id,
                    status=status_target,
                    is_active_for_reuse=is_reusable,
                    confidence_score=0.95,
                    author=author,
                    origin_type="intake_source_sync",
                    ingestion_channel="manual_intake",
                    modality="guide" if src.category in ["template", "guide"] else "text",
                    tags=["fuente_intake", src.category or "general", src.discipline or "general"]
                )
                self.db.add(item)
                self.db.flush()
                self._generate_chunks_for_item(item)
                synced_count += 1

        self.db.commit()
        return synced_count

    def sync_from_rules_engine(self, organization_id: str, author: str = "system", auto_approve: bool = False) -> int:
        """Sincroniza definiciones de reglas QA/QC aprobadas hacia la Base de Conocimiento."""
        synced_count = 0
        status_target = "approved_for_reuse" if auto_approve else "extracted"
        is_reusable = auto_approve

        rules = self.db.query(RuleDefinition).filter(RuleDefinition.is_active.is_(True)).all()
        for r in rules:
            existing = self.db.query(KnowledgeItem).filter(
                KnowledgeItem.organization_id == organization_id,
                KnowledgeItem.rule_id == r.id
            ).first()

            content = (
                f"Regla QA/QC: {r.code} - {r.name}\n"
                f"Categoría: {r.category}\n"
                f"Disciplina: {r.discipline}\n"
                f"Severidad por defecto: {r.severity_default}\n"
                f"Tipo de Lógica: {r.rule_logic_type}\n"
                f"Descripción: {r.description}\n"
                f"Requisitos de entrada: {r.input_requirements}"
            )

            if not existing:
                item = KnowledgeItem(
                    id=str(uuid.uuid4()),
                    organization_id=organization_id,
                    project_id=None, # Reglas son globales de organización
                    domain="rule_knowledge",
                    item_type="qaqc_baseline_rule",
                    title=f"Regla: {r.code} ({r.name})",
                    summary=r.description[:200] if r.description else None,
                    content_text=content,
                    structured_payload={
                        "rule_code": r.code,
                        "category": r.category,
                        "logic_type": r.rule_logic_type,
                        "severity_default": r.severity_default,
                        "input_requirements": r.input_requirements or {}
                    },
                    discipline=r.discipline or "general",
                    rule_id=r.id,
                    status=status_target,
                    is_active_for_reuse=is_reusable,
                    confidence_score=1.0,
                    author=author,
                    origin_type="rules_engine_sync",
                    ingestion_channel="rule_derivation",
                    modality="rule",
                    tags=["regla_qaqc", r.category, r.discipline or "general", r.code]
                )
                self.db.add(item)
                self.db.flush()
                self._generate_chunks_for_item(item)
                synced_count += 1

        self.db.commit()
        return synced_count

    def sync_from_completeness_matrix(self, organization_id: str, project_id: Optional[str] = None, author: str = "system", auto_approve: bool = False) -> int:
        """Sincroniza especificaciones de entregables de la matriz de completitud."""
        synced_count = 0
        status_target = "approved_for_reuse" if auto_approve else "extracted"
        is_reusable = auto_approve

        reqs = self.db.query(ProjectDeliverableRequirement).filter(
            or_(
                ProjectDeliverableRequirement.organization_id == organization_id,
                ProjectDeliverableRequirement.organization_id.is_(None)
            )
        ).all()

        for req in reqs:
            req_title = getattr(req, "title", None) or getattr(req, "name", "Entregable Requerido")
            blocked_rules = getattr(req, "blocked_rule_codes", None) or getattr(req, "blocks_rules", []) or []

            existing = self.db.query(KnowledgeItem).filter(
                KnowledgeItem.organization_id == organization_id,
                KnowledgeItem.domain == "deliverable_knowledge",
                KnowledgeItem.structured_payload["requirement_id"].as_string() == req.id
            ).first()

            content = (
                f"Requisito de Entregable: {req_title}\n"
                f"Etapa: {req.stage}\n"
                f"Tipo de Entregable: {req.deliverable_type}\n"
                f"Disciplina: {req.discipline}\n"
                f"Obligatorio para Gatekeeper: {'Sí' if req.is_mandatory else 'No'}\n"
                f"Descripción: {req.description or 'Especificación de entregable documental'}\n"
                f"Reglas Bloqueadas ante ausencia: {', '.join(blocked_rules) if blocked_rules else 'Ninguna'}"
            )

            if not existing:
                item = KnowledgeItem(
                    id=str(uuid.uuid4()),
                    organization_id=organization_id,
                    project_id=project_id,
                    domain="deliverable_knowledge",
                    item_type="stage_deliverable_spec",
                    title=f"Entregable [{req.stage}]: {req_title}",
                    summary=f"Especificación de {req.deliverable_type} para etapa {req.stage}",
                    content_text=content,
                    structured_payload={
                        "requirement_id": req.id,
                        "deliverable_type": req.deliverable_type,
                        "stage": req.stage,
                        "is_mandatory": req.is_mandatory,
                        "blocked_rule_codes": blocked_rules
                    },
                    discipline=req.discipline or "general",
                    stage=req.stage,
                    status=status_target,
                    is_active_for_reuse=is_reusable,
                    confidence_score=1.0,
                    author=author,
                    origin_type="completeness_matrix_sync",
                    ingestion_channel="manual_intake",
                    modality="deliverable_spec",
                    tags=["completitud", req.stage, req.deliverable_type, "gatekeeper"]
                )
                self.db.add(item)
                self.db.flush()
                self._generate_chunks_for_item(item)
                synced_count += 1

        self.db.commit()
        return synced_count

    def sync_from_observations(
        self,
        organization_id: str,
        project_id: Optional[str] = None,
        author: str = "system",
        auto_approve: bool = False,
        only_closed: bool = True
    ) -> int:
        """Sincroniza observaciones y RFIs resueltos/cerrados como lecciones aprendidas de revisión."""
        synced_count = 0
        status_target = "approved_for_reuse" if auto_approve else "extracted"
        is_reusable = auto_approve

        q_obs = self.db.query(AuditObservation).filter(
            AuditObservation.organization_id == organization_id
        )
        if project_id:
            q_obs = q_obs.filter(AuditObservation.project_id == project_id)
        if only_closed:
            q_obs = q_obs.filter(AuditObservation.status.in_(["closed", "resolved", "validated"]))

        observations = q_obs.all()
        for obs in observations:
            existing = self.db.query(KnowledgeItem).filter(
                KnowledgeItem.organization_id == organization_id,
                KnowledgeItem.observation_id == obs.id
            ).first()

            content = (
                f"Lección de Revisión / Observación: {obs.code}\n"
                f"Tipo de Ítem: {obs.item_type.upper()}\n"
                f"Título: {obs.title}\n"
                f"Disciplina: {obs.discipline}\n"
                f"Etapa: {obs.stage or 'General'}\n"
                f"Severidad: {obs.severity}\n"
                f"Descripción del Hallazgo: {obs.description or 'N/A'}\n"
                f"Recomendación Técnica: {obs.recommendation or 'N/A'}\n"
                f"Resolución / Cierre: {obs.resolution_notes or 'Cerrado tras validación técnica'}\n"
                f"Regla Origen: {obs.rule_code or 'N/A'}"
            )

            if not existing:
                item = KnowledgeItem(
                    id=str(uuid.uuid4()),
                    organization_id=organization_id,
                    project_id=obs.project_id,
                    domain="observation_rfi_knowledge",
                    item_type="resolved_observation_lesson",
                    title=f"Lección Resuelta [{obs.code}]: {obs.title}",
                    summary=obs.resolution_notes or obs.description[:200] if obs.description else None,
                    content_text=content,
                    structured_payload={
                        "observation_code": obs.code,
                        "item_type": obs.item_type,
                        "rule_code": obs.rule_code,
                        "severity": obs.severity,
                        "resolution_notes": obs.resolution_notes,
                        "history_trace": obs.history_trace or []
                    },
                    discipline=obs.discipline or "general",
                    stage=obs.stage,
                    observation_id=obs.id,
                    status=status_target,
                    is_active_for_reuse=is_reusable,
                    confidence_score=0.95,
                    author=author,
                    origin_type="observation_resolution_sync",
                    ingestion_channel="review_finding",
                    modality="observation",
                    tags=["observacion_resuelta", obs.item_type, obs.discipline or "general", obs.code]
                )
                self.db.add(item)
                self.db.flush()
                self._generate_chunks_for_item(item)
                synced_count += 1

        self.db.commit()
        return synced_count

    def sync_from_stage_snapshots(
        self,
        organization_id: str,
        project_id: Optional[str] = None,
        author: str = "system",
        auto_approve: bool = False
    ) -> int:
        """Sincroniza hitos y snapshots de revisión consolidada como conocimiento de proyecto."""
        synced_count = 0
        status_target = "approved_for_reuse" if auto_approve else "extracted"
        is_reusable = auto_approve

        q_snap = self.db.query(ProjectStageReportSnapshot).filter(
            ProjectStageReportSnapshot.organization_id == organization_id
        )
        if project_id:
            q_snap = q_snap.filter(ProjectStageReportSnapshot.project_id == project_id)

        snapshots = q_snap.all()
        for snap in snapshots:
            snap_title = snap.title
            global_verd = getattr(snap, "global_stage_verdict", "no_aprobable_bloqueada")
            manifest_hash = getattr(snap, "manifest_hash", "N/A")
            comp_sum = snap.completeness_summary or {}
            verd_sum = snap.audit_verdicts_summary or {}
            obs_sum = snap.observations_summary or {}

            existing = self.db.query(KnowledgeItem).filter(
                KnowledgeItem.organization_id == organization_id,
                KnowledgeItem.stage_snapshot_id == snap.id
            ).first()

            content = (
                f"Hito de Auditoría: {snap_title} (Rev {snap.revision_number})\n"
                f"Etapa: {snap.stage}\n"
                f"Veredicto Global de Etapa: {global_verd.upper()}\n"
                f"Gatekeeper Documental: {'APROBADO' if comp_sum.get('gatekeeper_passed') else 'BLOQUEADO'} ({comp_sum.get('percentage', 0)}%)\n"
                f"Total Hallazgos Auditados: Cumple: {verd_sum.get('cumple_count', 0)}, No Cumple: {verd_sum.get('no_cumple_count', 0)}\n"
                f"Observaciones Abiertas: {obs_sum.get('open_count', 0)}, Cerradas: {obs_sum.get('closed_count', 0)}\n"
                f"Hash SHA-256 Inmutable: {manifest_hash}"
            )

            if not existing:
                item = KnowledgeItem(
                    id=str(uuid.uuid4()),
                    organization_id=organization_id,
                    project_id=snap.project_id,
                    domain="project_knowledge",
                    item_type="stage_review_milestone_synthesis",
                    title=f"Hito Rev {snap.revision_number} [{snap.stage}]: {global_verd.upper()}",
                    summary=f"Consolidado de auditoría de etapa {snap.stage} emitido formalmente con veredicto {global_verd}",
                    content_text=content,
                    structured_payload={
                        "snapshot_id": snap.id,
                        "revision_number": snap.revision_number,
                        "stage": snap.stage,
                        "global_stage_verdict": global_verd,
                        "completeness_summary": comp_sum,
                        "audit_verdicts_summary": verd_sum,
                        "delta_comparison": getattr(snap, "delta_evolution_summary", {}) or {}
                    },
                    discipline="general",
                    stage=snap.stage,
                    stage_snapshot_id=snap.id,
                    status=status_target,
                    is_active_for_reuse=is_reusable,
                    confidence_score=1.0,
                    author=author,
                    origin_type="stage_snapshot_sync",
                    ingestion_channel="review_finding",
                    modality="text",
                    tags=["hito_auditoria", snap.stage, global_verd, "snapshot"]
                )
                self.db.add(item)
                self.db.flush()
                self._generate_chunks_for_item(item)
                synced_count += 1

        self.db.commit()
        return synced_count

    def sync_all(
        self,
        organization_id: str,
        project_id: Optional[str] = None,
        author: str = "system",
        auto_approve: bool = False
    ) -> KnowledgeSyncResponse:
        """Ejecuta la sincronización integral desde los 5 módulos operacionales."""
        counts = {
            "sources": self.sync_from_intake_sources(organization_id, project_id, author, auto_approve),
            "rules": self.sync_from_rules_engine(organization_id, author, auto_approve),
            "completeness": self.sync_from_completeness_matrix(organization_id, project_id, author, auto_approve),
            "observations": self.sync_from_observations(organization_id, project_id, author, auto_approve),
            "snapshots": self.sync_from_stage_snapshots(organization_id, project_id, author, auto_approve)
        }
        total = sum(counts.values())
        return KnowledgeSyncResponse(
            success=True,
            message=f"Sincronización completada exitosamente. {total} unidades operacionales procesadas.",
            synced_counts=counts,
            total_items_created=total,
            total_items_updated=0
        )

    # =========================================================================
    # MOTOR DE BÚSQUEDA Y RECUPERACIÓN CONTEXTUAL HÍBRIDA (QDRANT + FALLBACK SQL)
    # =========================================================================
    def sync_hybrid_vector_store(
        self,
        organization_id: str,
        project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Sincroniza todos los ítems aprobados y activos hacia la colección de Qdrant."""
        q = self.db.query(KnowledgeItem).filter(
            KnowledgeItem.organization_id == organization_id,
            KnowledgeItem.is_active_for_reuse.is_(True),
            KnowledgeItem.status.in_(["validated", "approved_for_reuse"])
        )
        if project_id:
            q = q.filter(or_(KnowledgeItem.project_id == project_id, KnowledgeItem.project_id.is_(None)))
        items = q.all()
        synced_count = 0
        for it in items:
            if it.chunks:
                ok = self.vector_store.upsert_approved_chunks(organization_id, it.project_id, it.chunks, it)
                if ok:
                    synced_count += 1
        return {
            "success": True,
            "is_qdrant_available": self.vector_store.is_available(),
            "total_approved_items": len(items),
            "synced_items": synced_count
        }

    def search_knowledge(
        self,
        organization_id: str,
        search_query: KnowledgeSearchQuery
    ) -> KnowledgeSearchResponse:
        """
        Recuperador contextual de conocimiento para el asistente.
        Estrategia híbrida:
        1. Intenta búsqueda vectorial en Qdrant sobre conocimiento aprobado si está disponible.
        2. Fallback automático a scoring léxico ponderado SQL sin interrumpir al usuario.
        """
        # 1. Intento de Búsqueda Vectorial Híbrida en Qdrant (Solo conocimiento aprobado)
        if self.vector_store.is_available() and search_query.active_only:
            try:
                v_results = self.vector_store.hybrid_search(
                    organization_id=organization_id,
                    query_text=search_query.query,
                    project_id=search_query.project_id,
                    discipline=search_query.discipline,
                    secondary_disciplines=search_query.secondary_disciplines,
                    stage=search_query.stage,
                    top_k=search_query.top_k
                )
                if v_results:
                    result_items: List[KnowledgeSearchResultItem] = []
                    for hit in v_results:
                        item_id = hit["item_id"]
                        db_item = self.db.query(KnowledgeItem).filter(KnowledgeItem.id == item_id).first()
                        # Re-validación estricta de seguridad en SQL: no admitir statuses retirados/superseded
                        if not db_item or not db_item.is_active_for_reuse or db_item.status in ["superseded", "archived", "withdrawn", "rejected", "draft", "inactive"]:
                            continue

                        result_items.append(KnowledgeSearchResultItem(
                            item_id=db_item.id,
                            chunk_id=hit.get("chunk_id"),
                            title=db_item.title,
                            domain=db_item.domain,
                            item_type=db_item.item_type,
                            discipline=db_item.discipline,
                            stage=db_item.stage,
                            status=db_item.status,
                            is_active_for_reuse=db_item.is_active_for_reuse,
                            relevance_score=hit.get("score", 0.95),
                            snippet=hit.get("snippet") or (db_item.summary or db_item.content_text[:300]),
                            provenance=hit.get("provenance", {}),
                            tags=db_item.tags or []
                        ))
                    if result_items:
                        return KnowledgeSearchResponse(
                            query=search_query.query,
                            total_matches=len(result_items),
                            results=result_items
                        )
            except Exception as e:
                logger.warning(f"Excepción en búsqueda Qdrant: {e}. Continuando con fallback SQL.")

        # 2. Fallback Seguro: Scoring Léxico Ponderado en Base de Datos Relacional (SQL)
        q_text = search_query.query.strip().lower()
        terms = [t for t in re.split(r"\s+", q_text) if len(t) > 2]

        q = self.db.query(KnowledgeItem).filter(KnowledgeItem.organization_id == organization_id)

        # Aislamiento por proyecto: proyecto consultado + conocimiento global
        if search_query.project_id:
            q = q.filter(or_(KnowledgeItem.project_id == search_query.project_id, KnowledgeItem.project_id.is_(None)))
        else:
            q = q.filter(KnowledgeItem.project_id.is_(None))

        # Filtro estricto de gobernanza: solo reutilizable por defecto y excluir superseded/archived/withdrawn/rejected/draft
        if search_query.active_only:
            q = q.filter(
                KnowledgeItem.is_active_for_reuse.is_(True),
                KnowledgeItem.status.in_(["validated", "approved_for_reuse"]),
                KnowledgeItem.status.notin_(["superseded", "archived", "withdrawn", "rejected", "draft", "inactive"])
            )

        if search_query.domain:
            q = q.filter(KnowledgeItem.domain == search_query.domain)

        # Filtrado multidisciplinario (primary_discipline + secondary_disciplines + 'general')
        target_disciplines = set()
        if search_query.discipline and search_query.discipline != "general":
            target_disciplines.add(search_query.discipline)
        if search_query.secondary_disciplines:
            for sd in search_query.secondary_disciplines:
                if sd and sd != "general":
                    target_disciplines.add(sd)

        if target_disciplines:
            q = q.filter(KnowledgeItem.discipline.in_(list(target_disciplines) + ["general"]))

        if search_query.stage:
            q = q.filter(or_(KnowledgeItem.stage == search_query.stage, KnowledgeItem.stage.is_(None)))

        items = q.all()
        scored_results: List[Tuple[float, KnowledgeItem, str, Optional[str]]] = []

        for item in items:
            full_text = f"{item.title} {item.summary or ''} {item.content_text}".lower()
            
            # Cálculo de score
            score = 0.0
            for t in terms:
                if t in item.title.lower():
                    score += 3.5 # Mayor peso en título
                if t in (item.summary or "").lower():
                    score += 2.0
                if t in item.content_text.lower():
                    score += 1.0

            # Bonus por match de disciplina o etapa
            if search_query.discipline and item.discipline == search_query.discipline:
                score += 1.5
            if search_query.stage and item.stage == search_query.stage:
                score += 1.5

            if score > 0 or not terms: # Si no hay términos de búsqueda o hizo match
                # Encontrar el fragmento más relevante (preferir table_chunk o section_chunk)
                best_snippet = item.summary or item.content_text[:300]
                best_chunk_id = None
                if item.chunks:
                    # Priorizar chunks de tablas o secciones si coinciden
                    for c in item.chunks:
                        if terms and any(t in c.chunk_text.lower() for t in terms):
                            best_snippet = c.chunk_text[:350]
                            best_chunk_id = c.id
                            break
                    if not best_chunk_id:
                        best_chunk = item.chunks[0]
                        best_snippet = best_chunk.chunk_text[:350]
                        best_chunk_id = best_chunk.id

                final_score = round(min(1.0, (score / max(1.0, len(terms) * 4.0))), 3)
                scored_results.append((final_score, item, best_snippet, best_chunk_id))

        # Ordenar por score descendente
        scored_results.sort(key=lambda x: x[0], reverse=True)
        top_results = scored_results[:search_query.top_k]

        result_items: List[KnowledgeSearchResultItem] = []
        for sc, item, snip, c_id in top_results:
            prov = {
                "origin_type": item.origin_type,
                "author": item.author,
                "source_asset_id": item.source_asset_id,
                "rule_id": item.rule_id,
                "observation_id": item.observation_id,
                "stage_snapshot_id": item.stage_snapshot_id,
                "version_number": item.version_number
            }
            result_items.append(KnowledgeSearchResultItem(
                item_id=item.id,
                chunk_id=c_id,
                title=item.title,
                domain=item.domain,
                item_type=item.item_type,
                discipline=item.discipline,
                stage=item.stage,
                status=item.status,
                is_active_for_reuse=item.is_active_for_reuse,
                relevance_score=sc,
                snippet=snip,
                provenance=prov,
                tags=item.tags or []
            ))

        return KnowledgeSearchResponse(
            query=search_query.query,
            total_matches=len(result_items),
            results=result_items
        )

    # =========================================================================
    # ESTADÍSTICAS Y MÉTRICAS
    # =========================================================================
    def get_stats(self, organization_id: str, project_id: Optional[str] = None) -> KnowledgeBaseStatsRead:
        q = self.db.query(KnowledgeItem).filter(KnowledgeItem.organization_id == organization_id)
        if project_id:
            q = q.filter(or_(KnowledgeItem.project_id == project_id, KnowledgeItem.project_id.is_(None)))

        items = q.all()
        total = len(items)
        approved = sum(1 for i in items if i.status == "approved_for_reuse")
        draft_ext = sum(1 for i in items if i.status in ["draft", "extracted", "reviewed"])
        validated = sum(1 for i in items if i.status == "validated")
        rej_sup = sum(1 for i in items if i.status in ["rejected", "superseded", "archived"])
        global_cnt = sum(1 for i in items if i.project_id is None)
        proj_cnt = sum(1 for i in items if i.project_id is not None)

        by_domain: Dict[str, int] = {}
        by_discipline: Dict[str, int] = {}
        by_status: Dict[str, int] = {}

        for i in items:
            by_domain[i.domain] = by_domain.get(i.domain, 0) + 1
            by_discipline[i.discipline] = by_discipline.get(i.discipline, 0) + 1
            by_status[i.status] = by_status.get(i.status, 0) + 1

        return KnowledgeBaseStatsRead(
            total_items=total,
            approved_for_reuse_count=approved,
            draft_or_extracted_count=draft_ext,
            validated_count=validated,
            rejected_or_superseded_count=rej_sup,
            global_items_count=global_cnt,
            project_scoped_items_count=proj_cnt,
            items_by_domain=by_domain,
            items_by_discipline=by_discipline,
            items_by_status=by_status
        )
