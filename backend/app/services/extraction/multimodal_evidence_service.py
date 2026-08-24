import os
import uuid
import hashlib
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.db.models.document_memory import Document, DocumentSheet, DocumentStructuralNode, ExtractedTable, ExtractedTableCell
from app.services.document_processing.docling_service import DoclingService
from app.services.cad.dxf_service import DxfService

class MultimodalEvidenceService:
    """
    Capa 1: Evidence Extraction.
    Extrae, separa, preserva y estructura evidencia técnica multimodal bruta
    a partir de documentos (PDFs, DXF, XLSX, DOCX, CSV e imágenes),
    preservando jerarquía, layout/bbox, procedencia, matrices tabulares y referencias visuales.
    """

    def __init__(self, db: Session):
        self.db = db
        self.docling_service = DoclingService()
        self.dxf_service = DxfService()

    def extract_document_evidence(
        self,
        document_id: str,
        file_bytes: Optional[bytes] = None,
        filename: Optional[str] = None,
        file_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Orquesta la extracción multimodal de Capa 1 sobre un documento registrado.
        Retorna el payload estructurado con nodos jerárquicos, tablas, entidades CAD,
        referencias visuales y procedencia completa.
        """
        doc = self.db.query(Document).filter(Document.id == document_id).first()
        actual_filename = filename or (doc.filename if doc else "document.pdf")
        actual_path = file_path or (doc.file_path if doc else None)

        if not file_bytes and actual_path and os.path.exists(actual_path):
            with open(actual_path, "rb") as f:
                file_bytes = f.read()

        evidence_payload: Dict[str, Any] = {
            "document_id": document_id,
            "filename": actual_filename,
            "provenance": {
                "sha256": hashlib.sha256(file_bytes).hexdigest() if file_bytes else (doc.file_hash_sha256 if doc else "unknown"),
                "file_size_bytes": len(file_bytes) if file_bytes else (doc.file_size_bytes if doc else 0),
                "extracted_at": doc.created_at.isoformat() if doc else None,
                "engine_version": "MultimodalEvidenceExtractor-v1.0"
            },
            "structural_nodes": [],
            "tables": [],
            "cad_entities": None,
            "visual_crops": [],
            "disclaimers": []
        }

        if not file_bytes:
            logger.warning(f"No se proporcionaron bytes para el documento '{document_id}'.")
            return evidence_payload

        ext = os.path.splitext(actual_filename)[1].lower()

        # 1. Extracción Estructural con DoclingService (PDF, Office, CSV)
        if ext in [".pdf", ".docx", ".doc", ".xlsx", ".xls", ".csv", ".txt"]:
            nodes = self.docling_service.extract_structural_nodes(
                file_bytes=file_bytes,
                filename=actual_filename,
                document_id=document_id
            )
            for node in nodes:
                # Persistir en BD si no existe aún
                existing = self.db.query(DocumentStructuralNode).filter(
                    DocumentStructuralNode.document_id == document_id,
                    DocumentStructuralNode.hierarchy_path == node.hierarchy_path,
                    DocumentStructuralNode.title == node.title
                ).first()
                if not existing:
                    self.db.add(node)
                    self.db.flush()
                    node_id = node.id
                else:
                    node_id = existing.id

                node_dict = {
                    "id": node_id,
                    "node_type": node.node_type,
                    "hierarchy_path": node.hierarchy_path,
                    "level": node.level,
                    "title": node.title,
                    "content_text": node.content_text,
                    "structured_payload": node.structured_payload,
                    "page_number": node.page_number,
                    "bbox_normalized": node.bbox_normalized
                }
                evidence_payload["structural_nodes"].append(node_dict)

                # Si es tabla, catalogarla en tables
                if node.node_type == "table":
                    evidence_payload["tables"].append({
                        "node_id": node_id,
                        "title": node.title,
                        "headers": node.structured_payload.get("headers", []),
                        "rows": node.structured_payload.get("rows", []),
                        "row_count": node.structured_payload.get("row_count", 0),
                        "page_number": node.page_number
                    })

        # 2. Extracción Semántica CAD con DxfService si aplica
        if ext == ".dxf":
            cad_summary = self.dxf_service.extract_cad_entities_from_bytes(file_bytes, actual_filename)
            evidence_payload["cad_entities"] = cad_summary
            evidence_payload["disclaimers"].append(
                "Extracción semántica DXF regional realizada sin inferencia de conectividad topológica ni grafo P&ID en esta fase."
            )
            # Crear nodos estructurales para bloques CAD
            for blk in cad_summary.get("blocks", []):
                blk_title = f"Bloque CAD: {blk.get('block_name')} (Capa {blk.get('layer')})"
                blk_attrs = blk.get("attributes", {})
                blk_text = f"Bloque {blk.get('block_name')} ubicado en coordenadas {blk.get('location')}. Atributos: {blk_attrs}"
                dxf_node = DocumentStructuralNode(
                    id=str(uuid.uuid4()),
                    document_id=document_id,
                    node_type="dxf_block_summary",
                    hierarchy_path=f"/CAD/Blocks/{blk.get('block_name')}",
                    level=2,
                    title=blk_title,
                    content_text=blk_text,
                    structured_payload=blk,
                    page_number=1
                )
                self.db.add(dxf_node)
                self.db.flush()
                evidence_payload["structural_nodes"].append({
                    "id": dxf_node.id,
                    "node_type": "dxf_block_summary",
                    "hierarchy_path": dxf_node.hierarchy_path,
                    "title": blk_title,
                    "content_text": blk_text,
                    "structured_payload": blk
                })

        self.db.commit()
        return evidence_payload
