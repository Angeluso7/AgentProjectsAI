from typing import Optional, List
from sqlalchemy.orm import Session
from app.db.models.document_memory import (
    Document, DocumentSheet, SheetRegion, TitleBlockExtraction,
    ExtractedText, DetectedSymbol
)
from app.db.repositories.base import BaseRepository

class DocumentRepository(BaseRepository[Document]):
    def __init__(self, db: Session):
        super().__init__(Document, db)

    def get_by_hash(self, hash_sha256: str) -> Optional[Document]:
        return self.db.query(Document).filter(Document.file_hash_sha256 == hash_sha256).first()

    def get_by_project_and_hash(self, project_id: str, hash_sha256: str) -> Optional[Document]:
        """Obtiene un documento por su hash SHA-256 dentro del ámbito exclusivo del proyecto."""
        return (
            self.db.query(Document)
            .filter(Document.project_id == project_id, Document.file_hash_sha256 == hash_sha256)
            .first()
        )

    def list_by_project(self, project_id: str) -> List[Document]:
        return self.db.query(Document).filter(Document.project_id == project_id).all()

    def list_by_project_all_statuses(self, project_id: str, organization_id: Optional[str] = None) -> List[Document]:
        """Lista todos los documentos de un proyecto en cualquier estado (uploaded, processing, ready, failed)."""
        query = self.db.query(Document).filter(Document.project_id == project_id)
        if organization_id:
            query = query.filter(Document.organization_id == organization_id)
        return query.order_by(Document.created_at.desc()).all()

    def get_sheet_by_id(self, sheet_id: str) -> Optional[DocumentSheet]:
        return self.db.query(DocumentSheet).filter(DocumentSheet.id == sheet_id).first()

    def list_sheets_by_document(self, document_id: str) -> List[DocumentSheet]:
        return (
            self.db.query(DocumentSheet)
            .filter(DocumentSheet.document_id == document_id)
            .order_by(DocumentSheet.sheet_number.asc())
            .all()
        )

    def add_sheet(self, sheet: DocumentSheet) -> DocumentSheet:
        self.db.add(sheet)
        self.db.commit()
        self.db.refresh(sheet)
        return sheet

    def delete_sheets_by_document(self, document_id: str) -> int:
        count = self.db.query(DocumentSheet).filter(DocumentSheet.document_id == document_id).delete()
        self.db.commit()
        return count

    # --- Métodos para ExtractedText (OCR) ---
    def list_texts_by_sheet(self, sheet_id: str) -> List[ExtractedText]:
        """Obtiene todos los bloques de texto extraídos de una lámina/hoja."""
        return (
            self.db.query(ExtractedText)
            .filter(ExtractedText.sheet_id == sheet_id)
            .order_by(ExtractedText.created_at.asc())
            .all()
        )

    def list_texts_by_document(self, document_id: str) -> List[ExtractedText]:
        """Obtiene todos los bloques de texto de todas las hojas de un documento."""
        return (
            self.db.query(ExtractedText)
            .join(DocumentSheet, ExtractedText.sheet_id == DocumentSheet.id)
            .filter(DocumentSheet.document_id == document_id)
            .order_by(DocumentSheet.sheet_number.asc(), ExtractedText.created_at.asc())
            .all()
        )

    def add_extracted_texts(self, texts: List[ExtractedText]) -> List[ExtractedText]:
        """Inserta en bloque múltiples registros de texto OCR en la base de datos."""
        self.db.add_all(texts)
        self.db.commit()
        return texts

    def delete_texts_by_sheet(self, sheet_id: str) -> int:
        """Elimina todos los textos OCR asociados a una lámina (para reprocesamiento limpio)."""
        count = self.db.query(ExtractedText).filter(ExtractedText.sheet_id == sheet_id).delete()
        self.db.commit()
        return count

    # --- Métodos para SheetRegion (Layout) ---
    def list_regions_by_sheet(self, sheet_id: str) -> List[SheetRegion]:
        """Lista las macro-regiones detectadas para una lámina."""
        return (
            self.db.query(SheetRegion)
            .filter(SheetRegion.sheet_id == sheet_id)
            .order_by(SheetRegion.created_at.asc())
            .all()
        )

    def add_sheet_regions(self, regions: List[SheetRegion]) -> List[SheetRegion]:
        """Inserta en bloque las macro-regiones segmentadas de una lámina."""
        self.db.add_all(regions)
        self.db.commit()
        return regions

    def delete_regions_by_sheet(self, sheet_id: str) -> int:
        """Elimina las macro-regiones previas de una lámina (para reprocesamiento idempotente)."""
        count = self.db.query(SheetRegion).filter(SheetRegion.sheet_id == sheet_id).delete()
        self.db.commit()
        return count

    # --- Métodos para TitleBlockExtraction ---
    def get_title_block_extraction(self, sheet_id: str) -> Optional[TitleBlockExtraction]:
        """Obtiene la extracción estructurada de viñeta asociada a una lámina."""
        return self.db.query(TitleBlockExtraction).filter(TitleBlockExtraction.sheet_id == sheet_id).first()

    def upsert_title_block_extraction(self, extraction: TitleBlockExtraction) -> TitleBlockExtraction:
        existing = self.get_title_block_extraction(extraction.sheet_id)
        if existing:
            existing.discipline = extraction.discipline
            existing.drawn_by = extraction.drawn_by
            existing.checked_by = extraction.checked_by
            existing.approved_by = extraction.approved_by
            existing.matched_anchors = extraction.matched_anchors
            existing.unmatched_required_fields = extraction.unmatched_required_fields
            existing.raw_fields = extraction.raw_fields
            self.db.commit()
            self.db.refresh(existing)
            return existing
        else:
            self.db.add(extraction)
            self.db.commit()
            self.db.refresh(extraction)
            return extraction

    def delete_title_block_extraction(self, sheet_id: str) -> int:
        """Elimina la extracción de viñeta de una lámina."""
        count = self.db.query(TitleBlockExtraction).filter(TitleBlockExtraction.sheet_id == sheet_id).delete()
        self.db.commit()
        return count

    # --- Análisis de Impacto y Eliminación de Documentos (Fase Gobierno) ---
    def get_impact_analysis(self, document_id: str) -> Optional[dict]:
        """Calcula el resumen de dependencias antes de eliminar un documento."""
        import os
        from app.db.models.document_memory import ExtractedTable
        from app.db.models.decision_memory import RuleFinding
        from app.db.models.operations import DecisionTrace, ReviewTask

        doc = self.get_by_id(document_id)
        if not doc:
            return None

        sheets = self.db.query(DocumentSheet).filter(DocumentSheet.document_id == document_id).all()
        sheet_ids = [s.id for s in sheets]

        ocr_count = self.db.query(ExtractedText).filter(ExtractedText.sheet_id.in_(sheet_ids)).count() if sheet_ids else 0
        region_count = self.db.query(SheetRegion).filter(SheetRegion.sheet_id.in_(sheet_ids)).count() if sheet_ids else 0
        title_block_count = self.db.query(TitleBlockExtraction).filter(TitleBlockExtraction.sheet_id.in_(sheet_ids)).count() if sheet_ids else 0
        table_count = self.db.query(ExtractedTable).filter(ExtractedTable.document_id == document_id).count()
        symbol_count = self.db.query(DetectedSymbol).filter(DetectedSymbol.document_id == document_id).count()

        findings = self.db.query(RuleFinding).filter(RuleFinding.document_id == document_id).all()
        finding_ids = [f.id for f in findings]

        severity_breakdown = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        for f in findings:
            sev = f.severity.lower() if f.severity else "medium"
            if sev in severity_breakdown:
                severity_breakdown[sev] += 1

        trace_count = self.db.query(DecisionTrace).filter(DecisionTrace.document_id == document_id).count()
        if sheet_ids:
            review_task_count = self.db.query(ReviewTask).filter(
                (ReviewTask.document_id == document_id) | (ReviewTask.sheet_id.in_(sheet_ids))
            ).count()
        else:
            review_task_count = self.db.query(ReviewTask).filter(ReviewTask.document_id == document_id).count()


        raster_files = []
        for s in sheets:
            if s.raster_image_path and os.path.exists(s.raster_image_path):
                raster_files.append(s.raster_image_path)
            if s.thumbnail_path and os.path.exists(s.thumbnail_path):
                raster_files.append(s.thumbnail_path)

        raw_file_exists = os.path.exists(doc.file_path) if doc.file_path else False

        return {
            "document_id": doc.id,
            "filename": doc.filename,
            "project_id": doc.project_id,
            "organization_id": doc.organization_id,
            "status": doc.status,
            "file_size_bytes": doc.file_size_bytes,
            "sheets_count": len(sheets),
            "ocr_count": ocr_count,
            "region_count": region_count,
            "title_block_count": title_block_count,
            "table_count": table_count,
            "symbol_count": symbol_count,
            "findings_count": len(findings),
            "severity_breakdown": severity_breakdown,
            "trace_count": trace_count,
            "review_task_count": review_task_count,
            "raster_files_count": len(raster_files),
            "raw_file_exists": raw_file_exists
        }

    def soft_delete_document(self, document_id: str, user_id: str = "system") -> Optional[Document]:
        """Marca un documento como archivado y descarta hallazgos activos."""
        from app.db.models.decision_memory import RuleFinding
        from app.db.models.core import AuditLog

        doc = self.get_by_id(document_id)
        if not doc:
            return None

        doc.status = "archived"

        # Archivar hallazgos
        findings = self.db.query(RuleFinding).filter(RuleFinding.document_id == document_id).all()
        for f in findings:
            f.status = "dismissed"

        audit = AuditLog(
            organization_id=doc.organization_id,
            entity_type="document",
            entity_id=doc.id,
            action="soft_delete_archive",
            user_id=user_id,
            details={
                "filename": doc.filename,
                "project_id": doc.project_id,
                "sheets_archived": doc.page_count,
                "findings_archived": len(findings)
            }
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(doc)
        return doc

    def hard_delete_document(self, document_id: str, user_id: str = "system") -> Optional[dict]:
        """Elimina permanentemente el documento, entidades en base de datos y archivos en disco."""
        import os
        from app.core.logging import logger
        from app.db.models.decision_memory import RuleFinding
        from app.db.models.operations import DecisionTrace, ReviewTask, ProcessingJob
        from app.db.models.intake import SourceAsset
        from app.db.models.core import AuditLog

        doc = self.get_by_id(document_id)
        if not doc:
            return None

        impact = self.get_impact_analysis(document_id)

        # Recolectar archivos a purgar en disco
        files_to_delete = []
        if doc.file_path and os.path.exists(doc.file_path):
            files_to_delete.append(doc.file_path)

        sheets = self.db.query(DocumentSheet).filter(DocumentSheet.document_id == document_id).all()
        for s in sheets:
            if s.raster_image_path and os.path.exists(s.raster_image_path):
                files_to_delete.append(s.raster_image_path)
            if s.thumbnail_path and os.path.exists(s.thumbnail_path):
                files_to_delete.append(s.thumbnail_path)

        sheet_ids = [s.id for s in sheets]
        findings = self.db.query(RuleFinding).filter(RuleFinding.document_id == document_id).all()
        finding_ids = [f.id for f in findings]
        targets_to_check = [document_id] + sheet_ids + finding_ids

        # Eliminar operaciones y tareas
        if sheet_ids:
            self.db.query(ReviewTask).filter(
                (ReviewTask.document_id == document_id) | (ReviewTask.sheet_id.in_(sheet_ids))
            ).delete(synchronize_session=False)
        else:
            self.db.query(ReviewTask).filter(ReviewTask.document_id == document_id).delete(synchronize_session=False)


        self.db.query(DecisionTrace).filter(DecisionTrace.document_id == document_id).delete(synchronize_session=False)
        self.db.query(ProcessingJob).filter(ProcessingJob.target_id.in_([document_id] + sheet_ids)).delete(synchronize_session=False)
        self.db.query(RuleFinding).filter(RuleFinding.document_id == document_id).delete(synchronize_session=False)
        self.db.query(SourceAsset).filter(SourceAsset.file_path == doc.file_path).delete(synchronize_session=False)

        # Eliminar documento raíz (cascada en PostgreSQL elimina sheets, texts, regions, tables, symbols)
        org_id = doc.organization_id
        doc_filename = doc.filename
        proj_id = doc.project_id
        self.db.delete(doc)

        # Bitácora
        audit = AuditLog(
            organization_id=org_id,
            entity_type="document",
            entity_id=document_id,
            action="hard_delete_permanent",
            user_id=user_id,
            details={
                "filename": doc_filename,
                "project_id": proj_id,
                "impact_summary": impact,
                "files_to_remove": len(files_to_delete)
            }
        )
        self.db.add(audit)
        self.db.commit()

        # Eliminar archivos físicos
        deleted_count = 0
        for fpath in files_to_delete:
            try:
                if os.path.exists(fpath):
                    os.remove(fpath)
                    deleted_count += 1
            except Exception as e:
                logger.warning(f"Error borrando archivo {fpath}: {e}")

        return {
            "success": True,
            "document_id": document_id,
            "delete_type": "hard_delete",
            "impact_summary": impact,
            "files_deleted_count": deleted_count
        }

