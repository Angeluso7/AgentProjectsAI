import os
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from app.db.models.intake import SourceAsset
from app.db.models.intake_extractions import SourceExtraction, RuleDocument
from app.db.models.research import ResearchQuery, ResearchResult, ResearchSource, ResearchItem
from app.db.repositories.base import BaseRepository

class IntakeRepository(BaseRepository[SourceAsset]):
    def __init__(self, db: Session):
        super().__init__(SourceAsset, db)

    def get_by_sha256(self, sha256: str) -> Optional[SourceAsset]:
        return self.db.query(SourceAsset).filter(SourceAsset.sha256 == sha256).first()

    def list_sources(
        self,
        source_type: Optional[str] = None,
        discipline: Optional[str] = None,
        status: Optional[str] = None,
        approval_status: Optional[str] = None,
        linked_memory_target: Optional[str] = None
    ) -> List[SourceAsset]:
        query = self.db.query(SourceAsset)
        if source_type:
            query = query.filter(SourceAsset.source_type == source_type)
        if discipline:
            query = query.filter(SourceAsset.discipline == discipline)
        if status:
            query = query.filter(SourceAsset.status == status)
        if approval_status:
            query = query.filter(SourceAsset.approval_status == approval_status)
        if linked_memory_target:
            query = query.filter(SourceAsset.linked_memory_target == linked_memory_target)
        return query.order_by(SourceAsset.created_at.desc()).all()

    def list_distinct_disciplines(self) -> List[str]:
        rows = self.db.query(SourceAsset.discipline).distinct().all()
        base = ["Arquitectura", "Estructuras", "Mecánica", "Eléctrica", "Instrumentación", "Piping"]
        db_discs = [r[0] for r in rows if r[0]]
        merged = list(base)
        for d in db_discs:
            if not any(m.lower() == d.lower() for m in merged):
                merged.append(d)
        return merged

    def update_approval(
        self,
        source_id: str,
        approval_status: str,
        notes: Optional[str] = None,
        reviewer: str = "reviewer"
    ) -> Optional[SourceAsset]:
        source = self.get_by_id(source_id)
        if not source:
            return None
        source.approval_status = approval_status
        source.approval_notes = notes
        source.reviewed_by = reviewer
        source.reviewed_at = datetime.utcnow()
        if approval_status == "rejected":
            source.status = "rejected"
        self.db.commit()
        self.db.refresh(source)
        return source

    def update_status(self, source_id: str, status: str) -> Optional[SourceAsset]:
        source = self.get_by_id(source_id)
        if not source:
            return None
        source.status = status
        self.db.commit()
        self.db.refresh(source)
        return source

    def get_source_dependencies(self, source_id: str) -> Dict[str, Any]:
        """Calcula el número de dependencias activas (extracciones, reglas) vinculadas al activo fuente."""
        source = self.get_by_id(source_id)
        if not source:
            return {
                "source_id": source_id,
                "title": "",
                "has_file": False,
                "file_path": None,
                "original_filename": None,
                "file_size_bytes": None,
                "extractions_count": 0,
                "rule_documents_count": 0,
                "can_hard_delete": True,
                "warnings": ["La fuente no existe."]
            }

        ext_count = self.db.query(SourceExtraction).filter(SourceExtraction.source_asset_id == source_id).count()
        rules_count = self.db.query(RuleDocument).filter(RuleDocument.source_asset_id == source_id).count()

        warnings = []
        if ext_count > 0:
            warnings.append(f"Tiene {ext_count} sesión(es) de extracción estructurada vinculada(s).")
        if rules_count > 0:
            warnings.append(f"Tiene {rules_count} documento(s) normativo(s) incorporado(s) al Motor de Reglas QA/QC.")

        return {
            "source_id": source.id,
            "title": source.title,
            "has_file": bool(source.file_path and os.path.exists(source.file_path)),
            "file_path": source.file_path,
            "original_filename": source.original_filename or (os.path.basename(source.file_path) if source.file_path else None),
            "file_size_bytes": source.file_size_bytes,
            "extractions_count": ext_count,
            "rule_documents_count": rules_count,
            "can_hard_delete": (ext_count == 0 and rules_count == 0),
            "warnings": warnings
        }

    # =========================================================
    # REPOSITORIO PARA INVESTIGACIONES WEB PERSISTENTES
    # =========================================================

    def save_web_research(
        self,
        organization_id: str,
        search_prompt: str,
        discipline: str = "Arquitectura",
        document_type: str = "norma",
        authority: Optional[str] = None,
        focus_areas: Optional[List[str]] = None,
        source_extraction_id: Optional[str] = None,
        executive_summary: Optional[str] = None,
        citations: Optional[List[Dict[str, Any]]] = None,
        extracted_items: Optional[List[Dict[str, Any]]] = None,
        metadata_info: Optional[Dict[str, Any]] = None
    ) -> ResearchQuery:
        """Crea y persiste la consulta de investigación web, su resultado, fuentes y elementos en BD estructurada."""
        query = ResearchQuery(
            organization_id=organization_id,
            search_prompt=search_prompt,
            discipline=discipline,
            document_type=document_type,
            authority=authority or "MINVU / Web Research",
            focus_areas=focus_areas or [],
            status="completed",
            metadata_payload=metadata_info or {}
        )
        self.db.add(query)
        self.db.flush()

        res_items = extracted_items or []
        result = ResearchResult(
            query_id=query.id,
            source_extraction_id=source_extraction_id,
            title=f"Investigación: {search_prompt[:80]}",
            executive_summary=executive_summary,
            total_items_found=len(res_items),
            raw_payload={"citations_count": len(citations or []), "items_count": len(res_items)},
            metadata_info=metadata_info or {}
        )
        self.db.add(result)
        self.db.flush()

        for c in (citations or []):
            src = ResearchSource(
                result_id=result.id,
                title=c.get("title") or c.get("domain") or "Fuente Web",
                url=c.get("url") or "https://minvu.gob.cl",
                domain=c.get("domain") or "minvu.gob.cl",
                snippet=c.get("snippet"),
                reliability_score=0.95
            )
            self.db.add(src)

        for it in res_items:
            item = ResearchItem(
                result_id=result.id,
                item_type=it.get("item_type", "rule"),
                item_nature=it.get("item_nature", "proposed_rule"),
                title=it.get("title", "Elemento Investigado"),
                code_or_number=it.get("code_or_number"),
                description=it.get("description"),
                content_text=it.get("content_text"),
                source_reference=it.get("source_reference"),
                governance_note=it.get("governance_note"),
                validation_status="pending_review"
            )
            self.db.add(item)

        self.db.commit()
        self.db.refresh(query)
        return query

    def list_research_queries(
        self,
        discipline: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Lista el histórico de investigaciones web persistidas con métricas resumidas."""
        q = self.db.query(ResearchQuery)
        if discipline:
            q = q.filter(ResearchQuery.discipline == discipline)
        if status:
            q = q.filter(ResearchQuery.status == status)
        
        queries = q.order_by(ResearchQuery.created_at.desc()).all()
        results = []
        for item in queries:
            total_sources = sum(len(r.sources) for r in item.results)
            total_items = sum(len(r.items) for r in item.results)
            results.append({
                "id": item.id,
                "organization_id": item.organization_id,
                "project_id": item.project_id,
                "search_prompt": item.search_prompt,
                "discipline": item.discipline,
                "document_type": item.document_type,
                "authority": item.authority,
                "focus_areas": item.focus_areas,
                "status": item.status,
                "created_at": item.created_at,
                "updated_at": item.updated_at,
                "results_count": len(item.results),
                "total_sources_count": total_sources,
                "total_items_count": total_items
            })
        return results

    def get_research_query_detail(self, query_id: str) -> Optional[ResearchQuery]:
        return self.db.query(ResearchQuery).filter(ResearchQuery.id == query_id).first()
