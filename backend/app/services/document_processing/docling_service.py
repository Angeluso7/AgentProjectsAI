import io
import os
import csv
import uuid
import re
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.core.settings import settings
from app.core.logging import logger
from app.db.models.document_memory import DocumentStructuralNode
from app.services.document_processing.structural_sanitizer import (
    clean_spacing_and_newlines,
    is_binary_or_matrix_garbage,
    sanitize_symbol_title,
    sanitize_hierarchy_path,
    sanitize_symbol_content_text
)

class DoclingService:
    """
    Servicio de extracción estructural de documentos técnicos (especificaciones,
    normas, line lists, tablas complejas, diagramas y simbología) para piping,
    arquitectura, instrumentación y multidisciplina.
    """

    def __init__(self):
        self._docling_available = False
        try:
            from docling.document_converter import DocumentConverter
            self._docling_available = True
            logger.info("Docling DocumentConverter disponible en el entorno.")
        except ImportError:
            logger.info("Docling no instalado; utilizando motor estructural nativo de alta precisión (PyMuPDF / openpyxl / CSV).")
        
        self.crops_dir = os.path.join(settings.STORAGE_LOCAL_ROOT, "crops", "extractions")
        os.makedirs(self.crops_dir, exist_ok=True)

    def is_docling_available(self) -> bool:
        return self._docling_available

    def extract_structural_nodes(
        self,
        file_bytes: bytes,
        filename: str,
        document_id: str,
        sheet_id: Optional[str] = None
    ) -> List[DocumentStructuralNode]:
        """
        Extrae nodos estructurales (artículos, capítulos, tablas, figuras, símbolos, imágenes, notas y párrafos)
        desde el binario del archivo preservando layout, bboxes, jerarquía y recortes visuales.
        """
        if not file_bytes:
            return []

        ext = os.path.splitext(filename)[1].lower()
        nodes_data: List[Dict[str, Any]] = []

        try:
            if ext == ".csv":
                nodes_data = self._extract_csv(file_bytes, filename)
            elif ext in [".xlsx", ".xls"]:
                nodes_data = self._extract_xlsx(file_bytes, filename)
            elif ext in [".docx", ".doc"]:
                nodes_data = self._extract_docx(file_bytes, filename)
            elif ext == ".pdf":
                nodes_data = self._extract_pdf(file_bytes, filename, document_id=document_id)
            elif ext == ".txt":
                nodes_data = self._extract_txt(file_bytes, filename)
            else:
                logger.warning(f"Formato '{ext}' no soportado para extracción estructural en DoclingService.")
                return []
        except Exception as e:
            logger.error(f"Error procesando extracción estructural para '{filename}': {str(e)}", exc_info=True)
            return []

        # Convertir diccionarios a instancias de DocumentStructuralNode con sanitización estricta
        created_nodes: List[DocumentStructuralNode] = []
        for item in nodes_data:
            n_type = item.get("node_type", "paragraph")
            raw_title = item.get("title") or ""
            raw_path = item.get("hierarchy_path") or ""
            raw_content = item.get("content_text") or ""
            s_payload = item.get("structured_payload", {})

            if n_type == "symbol":
                clean_title = sanitize_symbol_title(raw_title, fallback="Símbolo Técnico", max_length=120)
                clean_path = raw_path if (raw_path and len(raw_path) <= 200) else sanitize_hierarchy_path(filename, "General", "Simbolos", clean_title)
                clean_content = sanitize_symbol_content_text(raw_content, clean_title, max_length=350)
            else:
                clean_title = clean_spacing_and_newlines(raw_title)
                if len(clean_title) > 200:
                    clean_title = clean_title[:197].rsplit(" ", 1)[0] + "..."
                clean_path = clean_spacing_and_newlines(raw_path)
                if len(clean_path) > 220:
                    clean_path = clean_path[:215].rstrip("_/")
                clean_content = clean_spacing_and_newlines(raw_content)

            node = DocumentStructuralNode(
                id=str(uuid.uuid4()),
                document_id=document_id,
                sheet_id=sheet_id,
                node_type=n_type,
                hierarchy_path=clean_path,
                level=item.get("level", 0),
                title=clean_title,
                content_text=clean_content,
                structured_payload=s_payload,
                page_number=item.get("page_number", 1),
                bbox_normalized=item.get("bbox_normalized")
            )
            created_nodes.append(node)

        return created_nodes

    def _extract_csv(self, file_bytes: bytes, filename: str) -> List[Dict[str, Any]]:
        """Extrae tablas y encabezados desde archivos CSV (ej. Line Lists)."""
        text = file_bytes.decode("utf-8", errors="ignore")
        reader = csv.reader(io.StringIO(text))
        rows = [row for row in reader if any(cell.strip() for cell in row)]
        if not rows:
            return []

        headers = [h.strip() for h in rows[0]]
        data_rows = rows[1:] if len(rows) > 1 else []

        md_table = self._build_markdown_table(headers, data_rows)
        base_name = os.path.splitext(filename)[0]

        return [
            {
                "node_type": "table",
                "hierarchy_path": f"/{base_name}/Tabla_Principal",
                "level": 1,
                "title": f"Tabla: {filename}",
                "content_text": md_table,
                "structured_payload": {
                    "table_name": base_name,
                    "headers": headers,
                    "rows": data_rows,
                    "row_count": len(data_rows),
                    "col_count": len(headers),
                    "markdown_repr": md_table
                },
                "page_number": 1
            }
        ]

    def _extract_xlsx(self, file_bytes: bytes, filename: str) -> List[Dict[str, Any]]:
        """Extrae hojas y tablas desde archivos Excel."""
        results = []
        base_name = os.path.splitext(filename)[0]
        try:
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
            for sheet_idx, sheet_name in enumerate(wb.sheetnames):
                ws = wb[sheet_name]
                all_rows = []
                for row in ws.iter_rows(values_only=True):
                    row_vals = [str(val).strip() if val is not None else "" for val in row]
                    if any(row_vals):
                        all_rows.append(row_vals)
                if not all_rows:
                    continue

                headers = all_rows[0]
                data_rows = all_rows[1:]
                md_table = self._build_markdown_table(headers, data_rows)

                results.append({
                    "node_type": "table",
                    "hierarchy_path": f"/{base_name}/{sheet_name}",
                    "level": 1,
                    "title": f"Hoja: {sheet_name}",
                    "content_text": md_table,
                    "structured_payload": {
                        "sheet_name": sheet_name,
                        "headers": headers,
                        "rows": data_rows,
                        "row_count": len(data_rows),
                        "col_count": len(headers),
                        "markdown_repr": md_table
                    },
                    "page_number": sheet_idx + 1
                })
        except Exception as e:
            logger.warning(f"Fallo extracción openpyxl para '{filename}': {e}. Usando fallback.")
        return results

    def _extract_docx(self, file_bytes: bytes, filename: str) -> List[Dict[str, Any]]:
        """Extrae secciones y tablas desde archivos DOCX."""
        results = []
        base_name = os.path.splitext(filename)[0]
        try:
            import docx
            doc = docx.Document(io.BytesIO(file_bytes))
            current_h1 = base_name

            for p in doc.paragraphs:
                text = p.text.strip()
                if not text:
                    continue
                style_name = p.style.name.lower() if p.style else ""
                if "heading 1" in style_name or style_name.startswith("h1"):
                    current_h1 = text
                    results.append({
                        "node_type": "heading",
                        "hierarchy_path": f"/{base_name}/{text}",
                        "level": 1,
                        "title": text,
                        "content_text": text,
                        "structured_payload": {"style": "Heading 1"},
                        "page_number": 1
                    })
                elif "heading 2" in style_name or style_name.startswith("h2"):
                    results.append({
                        "node_type": "heading",
                        "hierarchy_path": f"/{base_name}/{current_h1}/{text}",
                        "level": 2,
                        "title": text,
                        "content_text": text,
                        "structured_payload": {"style": "Heading 2"},
                        "page_number": 1
                    })
                else:
                    results.append({
                        "node_type": "paragraph",
                        "hierarchy_path": f"/{base_name}/{current_h1}",
                        "level": 0,
                        "title": None,
                        "content_text": text,
                        "structured_payload": {},
                        "page_number": 1
                    })

            for t_idx, table in enumerate(doc.tables):
                t_rows = []
                for row in table.rows:
                    t_rows.append([cell.text.strip() for cell in row.cells])
                if t_rows:
                    headers = t_rows[0]
                    data_rows = t_rows[1:]
                    md_table = self._build_markdown_table(headers, data_rows)
                    results.append({
                        "node_type": "table",
                        "hierarchy_path": f"/{base_name}/{current_h1}/Tabla_{t_idx + 1}",
                        "level": 2,
                        "title": f"Tabla {t_idx + 1}",
                        "content_text": md_table,
                        "structured_payload": {
                            "headers": headers,
                            "rows": data_rows,
                            "row_count": len(data_rows),
                            "col_count": len(headers),
                            "markdown_repr": md_table
                        },
                        "page_number": 1
                    })
        except Exception as e:
            logger.warning(f"Fallo extracción docx para '{filename}': {e}. Usando fallback de texto plano.")
            raw_text = file_bytes.decode("utf-8", errors="ignore")
            results.append({
                "node_type": "paragraph",
                "hierarchy_path": f"/{base_name}",
                "level": 0,
                "title": base_name,
                "content_text": raw_text[:4000],
                "structured_payload": {},
                "page_number": 1
            })
        return results

    def _extract_pdf(self, file_bytes: bytes, filename: str, document_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Extrae exhaustivamente todos los elementos técnicos de un PDF:
        - Capítulos, Secciones, Artículos y Cláusulas
        - Tablas estructuradas (con find_tables() y generación de crop PNG)
        - Figuras, Diagramas y Esquemas técnicos (con crop PNG y caption)
        - Símbolos y Leyendas de instrumentación/válvulas (con crop PNG y metadatos)
        - Fotos e imágenes de equipos/materiales/dispositivos (con crop PNG)
        - Notas técnicas y Ejemplos ilustrativos
        """
        import fitz
        results = []
        base_name = os.path.splitext(filename)[0]
        doc_uid = (document_id or str(uuid.uuid4()))[:12]

        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            current_chapter = "General"
            current_section = "General"

            for page_idx in range(len(doc)):
                page = doc[page_idx]
                page_no = page_idx + 1
                rect = page.rect
                pw, ph = rect.width, rect.height

                # =========================================================
                # 1. EXTRACCIÓN DE TABLAS ESTRUCTURADAS (find_tables)
                # =========================================================
                try:
                    tabs = page.find_tables()
                    if tabs and tabs.tables:
                        for t_idx, t in enumerate(tabs.tables):
                            t_raw = t.extract()
                            if not t_raw or len(t_raw) < 1:
                                continue
                            
                            headers = [str(c).strip() if c is not None else "" for c in t_raw[0]]
                            data_rows = []
                            for r in t_raw[1:]:
                                data_rows.append([str(c).strip() if c is not None else "" for c in r])
                            
                            if not any(headers) and not data_rows:
                                continue

                            md_table = self._build_markdown_table(headers, data_rows)
                            bbox_norm = [
                                round(t.bbox[0] / pw, 4),
                                round(t.bbox[1] / ph, 4),
                                round(t.bbox[2] / pw, 4),
                                round(t.bbox[3] / ph, 4)
                            ]

                            # Generar Crop PNG de la tabla
                            crop_path = None
                            try:
                                pad = 6
                                clip_rect = fitz.Rect(
                                    max(0, t.bbox[0] - pad),
                                    max(0, t.bbox[1] - pad),
                                    min(pw, t.bbox[2] + pad),
                                    min(ph, t.bbox[3] + pad)
                                )
                                pix = page.get_pixmap(clip=clip_rect, dpi=150)
                                crop_filename = f"tbl_{doc_uid}_p{page_no}_{t_idx + 1}.png"
                                crop_full_path = os.path.join(self.crops_dir, crop_filename)
                                pix.save(crop_full_path)
                                crop_path = f"/data/crops/extractions/{crop_filename}"
                            except Exception as ce:
                                logger.debug(f"Aviso generando crop de tabla en pág {page_no}: {ce}")

                            # Título descriptivo de tabla
                            first_cell = headers[0] if headers and headers[0] else f"P{page_no}_T{t_idx+1}"
                            tbl_title = f"Tabla: {first_cell[:40]} (Pág. {page_no})"

                            # Integración con TableExtractor: inspección visual de celdas para extraer símbolos y recortes
                            table_symbols_payload = []
                            try:
                                from app.services.tables.extractor import TableExtractor
                                table_extractor = TableExtractor(width_px=int(pw), height_px=int(ph))
                                page_raw_blocks = page.get_text("blocks")
                                region_texts = []
                                for b in page_raw_blocks:
                                    if b[6] == 0 and b[4].strip():
                                        region_texts.append({
                                            "text": b[4].strip(),
                                            "bbox_normalized": [
                                                round(b[0] / pw, 4),
                                                round(b[1] / ph, 4),
                                                round(b[2] / pw, 4),
                                                round(b[3] / ph, 4)
                                            ]
                                        })

                                extracted_tbl_dto = table_extractor.extract_from_region(
                                    region_bbox_norm=bbox_norm,
                                    texts=region_texts,
                                    page=page,
                                    doc_uid=f"{doc_uid}_p{page_no}_t{t_idx+1}"
                                )

                                if extracted_tbl_dto and extracted_tbl_dto.has_symbols and extracted_tbl_dto.extracted_symbols:
                                    for sym in extracted_tbl_dto.extracted_symbols:
                                        sym_dict = {
                                            "symbol_name": sym.symbol_name,
                                            "canonical_symbol_family": sym.canonical_symbol_family,
                                            "standard_reference": sym.standard_reference,
                                            "discipline": sym.discipline,
                                            "category": sym.category,
                                            "source_render_mode": sym.source_render_mode,
                                            "layout_context": "inside_table",
                                            "context_association_mode": sym.context_association_mode,
                                            "bbox_normalized": sym.bbox_normalized,
                                            "estimated_physical_size_mm": sym.estimated_physical_size_mm,
                                            "crop_image_path": sym.crop_image_path,
                                            "technical_function": sym.technical_function,
                                            "aliases": sym.aliases,
                                            "confidence_score": sym.confidence_score,
                                            "source_table_id": f"tbl_{doc_uid}_p{page_no}_{t_idx+1}",
                                            "row_index": sym.row_index,
                                            "col_index": sym.col_index,
                                            "cell_bbox": sym.cell_bbox,
                                            "row_bbox": sym.row_bbox,
                                            "tag_or_code": sym.tag_or_code,
                                            "symbol_description": sym.symbol_description,
                                            "needs_visual_crop": sym.needs_visual_crop,
                                            "crop_error_reason": sym.crop_error_reason,
                                            "inner_drawing_bbox": sym.inner_drawing_bbox,
                                            "reading_orientation": sym.reading_orientation,
                                            "orientation": sym.reading_orientation,
                                            "orientation_confidence": sym.orientation_confidence,
                                            "orientation_reason": sym.orientation_reason,
                                            "requires_human_review": sym.requires_human_review,
                                            "geometric_evidence": getattr(sym, "geometric_evidence", True),
                                            "geometric_confidence": getattr(sym, "geometric_confidence", 1.0),
                                            "evidence_sources": getattr(sym, "evidence_sources", []),
                                            "shape_features": getattr(sym, "shape_features", {}),
                                            "text_mask_overlap_ratio": getattr(sym, "text_mask_overlap_ratio", 0.0),
                                            "rejection_reason": getattr(sym, "rejection_reason", None)
                                        }
                                        table_symbols_payload.append(sym_dict)

                                        # Materializar cada símbolo extraído de la tabla como nodo 'symbol' de Capa 1
                                        clean_sym_title = sanitize_symbol_title(
                                            sym.symbol_name or sym.tag_or_code,
                                            fallback=f"Símbolo R{sym.row_index if sym.row_index is not None else 0}C{sym.col_index if sym.col_index is not None else 0}",
                                            max_length=120
                                        )
                                        clean_sym_path = sanitize_hierarchy_path(
                                            base_name,
                                            current_chapter,
                                            "Simbolos",
                                            clean_sym_title
                                        )
                                        clean_sym_content = sanitize_symbol_content_text(
                                            description=sym.symbol_description,
                                            title=clean_sym_title,
                                            technical_function=sym.technical_function,
                                            max_length=350
                                        )
                                        results.append({
                                            "node_type": "symbol",
                                            "hierarchy_path": clean_sym_path,
                                            "level": 3,
                                            "title": clean_sym_title,
                                            "content_text": clean_sym_content,
                                            "structured_payload": sym_dict,
                                            "page_number": page_no,
                                            "bbox_normalized": sym.bbox_normalized
                                        })
                            except Exception as tee:
                                logger.debug(f"Aviso ejecutando TableExtractor en tabla de pág {page_no}: {tee}")

                            results.append({
                                "node_type": "table",
                                "hierarchy_path": f"/{base_name}/{current_chapter}/Tablas/{tbl_title}",
                                "level": 2,
                                "title": tbl_title,
                                "content_text": md_table,
                                "structured_payload": {
                                    "headers": headers,
                                    "rows": data_rows,
                                    "row_count": len(data_rows),
                                    "col_count": len(headers),
                                    "markdown_repr": md_table,
                                    "crop_image_path": crop_path,
                                    "extracted_symbols": table_symbols_payload,
                                    "has_symbols": extracted_tbl_dto.has_symbols if extracted_tbl_dto else False,
                                    "reading_orientation": extracted_tbl_dto.reading_orientation if extracted_tbl_dto else "row_major",
                                    "orientation": extracted_tbl_dto.reading_orientation if extracted_tbl_dto else "row_major",
                                    "orientation_confidence": extracted_tbl_dto.orientation_confidence if extracted_tbl_dto else 1.0,
                                    "orientation_reason": extracted_tbl_dto.orientation_reason if extracted_tbl_dto else "",
                                },
                                "page_number": page_no,
                                "bbox_normalized": bbox_norm
                            })

                    # Fallback si find_tables no encontró tablas tradicionales pero hay dibujos vectoriales
                    if not (tabs and tabs.tables) and len(page.get_drawings()) >= 10:
                        try:
                            from app.services.tables.extractor import TableExtractor
                            table_extractor = TableExtractor(width_px=int(pw), height_px=int(ph))
                            page_raw_blocks = page.get_text("blocks")
                            page_texts = [
                                {
                                    "text": b[4].strip(),
                                    "bbox_normalized": [
                                        round(b[0] / pw, 4),
                                        round(b[1] / ph, 4),
                                        round(b[2] / pw, 4),
                                        round(b[3] / ph, 4)
                                    ]
                                }
                                for b in page_raw_blocks if b[6] == 0 and b[4].strip()
                            ]
                            fb_table = table_extractor.extract_from_region(
                                region_bbox_norm=[0.0, 0.0, 1.0, 1.0],
                                texts=page_texts,
                                page=page,
                                doc_uid=f"{doc_uid}_p{page_no}_fb"
                            )
                            if fb_table and fb_table.row_count >= 2 and (fb_table.has_symbols and fb_table.extracted_symbols):
                                fb_symbols_payload = []
                                for sym in fb_table.extracted_symbols:
                                    sym_dict = {
                                        "symbol_name": sym.symbol_name,
                                        "canonical_symbol_family": sym.canonical_symbol_family,
                                        "standard_reference": sym.standard_reference,
                                        "discipline": sym.discipline,
                                        "category": sym.category,
                                        "source_render_mode": sym.source_render_mode,
                                        "layout_context": "inside_table",
                                        "context_association_mode": sym.context_association_mode,
                                        "bbox_normalized": sym.bbox_normalized,
                                        "estimated_physical_size_mm": sym.estimated_physical_size_mm,
                                        "crop_image_path": sym.crop_image_path,
                                        "technical_function": sym.technical_function,
                                        "aliases": sym.aliases,
                                        "confidence_score": sym.confidence_score,
                                        "source_table_id": f"tbl_{doc_uid}_p{page_no}_fb",
                                        "row_index": sym.row_index,
                                        "col_index": sym.col_index,
                                        "cell_bbox": sym.cell_bbox,
                                        "row_bbox": sym.row_bbox,
                                        "tag_or_code": sym.tag_or_code,
                                        "symbol_description": sym.symbol_description,
                                        "needs_visual_crop": sym.needs_visual_crop,
                                        "crop_error_reason": sym.crop_error_reason,
                                        "inner_drawing_bbox": sym.inner_drawing_bbox,
                                        "reading_orientation": sym.reading_orientation,
                                        "orientation": sym.reading_orientation,
                                        "orientation_confidence": sym.orientation_confidence,
                                        "orientation_reason": sym.orientation_reason,
                                        "requires_human_review": sym.requires_human_review,
                                    }
                                    fb_symbols_payload.append(sym_dict)
                                    clean_fb_title = sanitize_symbol_title(
                                        sym.symbol_name or sym.tag_or_code,
                                        fallback=f"Símbolo R{sym.row_index if sym.row_index is not None else 0}C{sym.col_index if sym.col_index is not None else 0}",
                                        max_length=120
                                    )
                                    clean_fb_path = sanitize_hierarchy_path(
                                        base_name,
                                        current_chapter,
                                        "Simbolos",
                                        clean_fb_title
                                    )
                                    clean_fb_content = sanitize_symbol_content_text(
                                        description=sym.symbol_description,
                                        title=clean_fb_title,
                                        technical_function=sym.technical_function,
                                        max_length=350
                                    )
                                    results.append({
                                        "node_type": "symbol",
                                        "hierarchy_path": clean_fb_path,
                                        "level": 3,
                                        "title": clean_fb_title,
                                        "content_text": clean_fb_content,
                                        "structured_payload": sym_dict,
                                        "page_number": page_no,
                                        "bbox_normalized": sym.bbox_normalized
                                    })

                                fb_md = self._build_markdown_table(fb_table.headers, [[c.text for c in fb_table.cells if c.row_index == r] for r in range(1, fb_table.row_count)])
                                results.append({
                                    "node_type": "table",
                                    "hierarchy_path": f"/{base_name}/{current_chapter}/Tablas/Tabla_Leyenda_P{page_no}",
                                    "level": 2,
                                    "title": f"Tabla: {fb_table.title} (Pág. {page_no})",
                                    "content_text": fb_md,
                                    "structured_payload": {
                                        "headers": fb_table.headers,
                                        "rows": [[c.text for c in fb_table.cells if c.row_index == r] for r in range(1, fb_table.row_count)],
                                        "row_count": fb_table.row_count,
                                        "col_count": fb_table.column_count,
                                        "markdown_repr": fb_md,
                                        "crop_image_path": None,
                                        "extracted_symbols": fb_symbols_payload,
                                        "has_symbols": fb_table.has_symbols,
                                        "reading_orientation": fb_table.reading_orientation,
                                        "orientation": fb_table.reading_orientation,
                                        "orientation_confidence": fb_table.orientation_confidence,
                                        "orientation_reason": fb_table.orientation_reason,
                                    },
                                    "page_number": page_no,
                                    "bbox_normalized": fb_table.bbox_normalized
                                })
                            elif fb_table and fb_table.row_count >= 2 and len(fb_table.cells) >= 4:
                                # Tabla de solo texto (Condición 2: Descartada de simbología)
                                fb_md = self._build_markdown_table(fb_table.headers, [[c.text for c in fb_table.cells if c.row_index == r] for r in range(1, fb_table.row_count)])
                                results.append({
                                    "node_type": "table",
                                    "hierarchy_path": f"/{base_name}/{current_chapter}/Tablas/Tabla_Doc_P{page_no}",
                                    "level": 2,
                                    "title": f"Tabla: {fb_table.title} (Pág. {page_no})",
                                    "content_text": fb_md,
                                    "structured_payload": {
                                        "headers": fb_table.headers,
                                        "rows": [[c.text for c in fb_table.cells if c.row_index == r] for r in range(1, fb_table.row_count)],
                                        "row_count": fb_table.row_count,
                                        "col_count": fb_table.column_count,
                                        "markdown_repr": fb_md,
                                        "crop_image_path": None,
                                        "extracted_symbols": [],
                                        "has_symbols": False,
                                        "reading_orientation": fb_table.reading_orientation,
                                        "orientation": fb_table.reading_orientation,
                                        "orientation_confidence": fb_table.orientation_confidence,
                                        "orientation_reason": fb_table.orientation_reason,
                                    },
                                    "page_number": page_no,
                                    "bbox_normalized": fb_table.bbox_normalized
                                })
                        except Exception as fbe:
                            logger.debug(f"Aviso en fallback de tabla vectorial pág {page_no}: {fbe}")
                except Exception as te:
                    logger.debug(f"Aviso en find_tables página {page_no}: {te}")

                # =========================================================
                # 2. EXTRACCIÓN DE IMÁGENES, SÍMBOLOS Y DIAGRAMAS (get_images)
                # =========================================================
                try:
                    images = page.get_images(full=True)
                    for img_idx, img in enumerate(images):
                        xref = img[0]
                        rects = page.get_image_rects(xref)
                        if not rects:
                            continue

                        for r_idx, r in enumerate(rects):
                            # Filtrar íconos o artefactos minúsculos (< 25px)
                            if r.width < 25 or r.height < 25:
                                continue

                            bbox_norm = [
                                round(r.x0 / pw, 4),
                                round(r.y0 / ph, 4),
                                round(r.x1 / pw, 4),
                                round(r.y1 / ph, 4)
                            ]

                            # Generar Recorte de Alta Resolución
                            crop_path = None
                            try:
                                pad = 4
                                clip_rect = fitz.Rect(
                                    max(0, r.x0 - pad),
                                    max(0, r.y0 - pad),
                                    min(pw, r.x1 + pad),
                                    min(ph, r.y1 + pad)
                                )
                                pix = page.get_pixmap(clip=clip_rect, dpi=150)
                                crop_filename = f"vis_{doc_uid}_p{page_no}_{img_idx}_{r_idx}.png"
                                crop_full_path = os.path.join(self.crops_dir, crop_filename)
                                pix.save(crop_full_path)
                                crop_path = f"/data/crops/extractions/{crop_filename}"
                            except Exception as ce:
                                logger.debug(f"Aviso generando recorte visual en pág {page_no}: {ce}")

                            # Extraer contexto textual circundante (30pt arriba y abajo)
                            context_rect = fitz.Rect(max(0, r.x0 - 20), max(0, r.y0 - 50), min(pw, r.x1 + 20), min(ph, r.y1 + 50))
                            caption_text = page.get_text("text", clip=context_rect).strip()
                            clean_caption = " ".join(caption_text.split()) if caption_text else ""

                            # Clasificación estricta: Las imágenes flotantes de página son figuras/diagramas o fotos de equipos
                            # Los símbolos técnicos deben provenir de celdas o leyendas con geometría validada
                            is_diagram = (
                                (r.width > 250 or r.height > 250) or
                                any(tag in clean_caption.upper() for tag in ["DIAGRAM", "P&ID", "ESQUEMA", "PLANO", "ISOMETRIC", "CIRCUITO", "FLUJO", "FIGURA"])
                            )

                            if is_diagram:
                                node_type = "figure"
                                title = f"Diagrama / Esquema: {clean_caption[:45] if clean_caption else f'Figura Pág {page_no} #{img_idx+1}'}"
                            else:
                                node_type = "image"
                                title = f"Imagen / Equipo Técnico: {clean_caption[:45] if clean_caption else f'Equipo Pág {page_no} #{img_idx+1}'}"

                            results.append({
                                "node_type": node_type,
                                "hierarchy_path": f"/{base_name}/{current_chapter}/Visuales/{title[:40]}",
                                "level": 2,
                                "title": title,
                                "content_text": clean_caption or f"Elemento visual técnico en página {page_no}.",
                                "structured_payload": {
                                    "crop_image_path": crop_path,
                                    "caption_or_context": clean_caption,
                                    "aspect_ratio": round(aspect_ratio, 2),
                                    "width_pt": round(r.width, 1),
                                    "height_pt": round(r.height, 1),
                                    "detected_type": node_type
                                },
                                "page_number": page_no,
                                "bbox_normalized": bbox_norm
                            })
                except Exception as ie:
                    logger.debug(f"Aviso en get_images página {page_no}: {ie}")

                # =========================================================
                # 3. EXTRACCIÓN DE TEXTO, CAPÍTULOS, CLÁUSULAS, NOTAS Y EJEMPLOS
                # =========================================================
                blocks = page.get_text("blocks") # (x0, y0, x1, y1, text, block_no, block_type)
                for b in blocks:
                    if b[6] != 0: # Solo bloques de texto
                        continue
                    text = b[4].strip()
                    if not text:
                        continue

                    x0, y0, x1, y1 = b[0], b[1], b[2], b[3]
                    bbox_norm = [
                        round(x0 / pw, 4),
                        round(y0 / ph, 4),
                        round(x1 / pw, 4),
                        round(y1 / ph, 4)
                    ]

                    # Heurísticas de Clasificación Textual
                    is_chapter = bool(re.match(r"^(CAP[ÍI]TULO|T[ÍI]TULO|SECTION|[0-9]+\.)\s+[A-ZÁÉÍÓÚ\s]{3,}", text))
                    is_article_clause = bool(re.match(r"^(ART[ÍI]CULO|ART\.|[0-9]+\.[0-9]+(\.[0-9]+)?)\s+", text, re.IGNORECASE))
                    is_note = bool(re.match(r"^(NOTA|NOTAS|ADVERTENCIA|PRECAUCI[ÓO]N)[\s:]+", text, re.IGNORECASE))
                    is_example = bool(re.search(r"(ejemplo|caso ilustrativo|por ejemplo|a modo de ejemplo)", text[:60], re.IGNORECASE))
                    has_requirement = bool(re.search(r"(deber[aá]|m[ií]nimo|m[aá]ximo|no inferior|superior a|obligatorio|exigencia|tolerancia)", text, re.IGNORECASE))

                    if is_chapter:
                        current_chapter = text.split("\n")[0][:80]
                        results.append({
                            "node_type": "heading",
                            "hierarchy_path": f"/{base_name}/{current_chapter}",
                            "level": 1,
                            "title": current_chapter,
                            "content_text": text,
                            "structured_payload": {"is_header": True, "header_level": 1},
                            "page_number": page_no,
                            "bbox_normalized": bbox_norm
                        })
                    elif is_article_clause:
                        clause_title = text.split("\n")[0][:80]
                        current_section = clause_title
                        results.append({
                            "node_type": "heading",
                            "hierarchy_path": f"/{base_name}/{current_chapter}/{clause_title}",
                            "level": 2,
                            "title": clause_title,
                            "content_text": text,
                            "structured_payload": {"is_clause": True, "has_requirement": has_requirement},
                            "page_number": page_no,
                            "bbox_normalized": bbox_norm
                        })
                    elif is_note:
                        results.append({
                            "node_type": "technical_note",
                            "hierarchy_path": f"/{base_name}/{current_chapter}/Notas",
                            "level": 2,
                            "title": f"Nota Técnica (Pág. {page_no})",
                            "content_text": text,
                            "structured_payload": {"is_note": True},
                            "page_number": page_no,
                            "bbox_normalized": bbox_norm
                        })
                    elif is_example:
                        results.append({
                            "node_type": "example",
                            "hierarchy_path": f"/{base_name}/{current_chapter}/Ejemplos",
                            "level": 2,
                            "title": f"Ejemplo Normativo (Pág. {page_no})",
                            "content_text": text,
                            "structured_payload": {"is_example": True},
                            "page_number": page_no,
                            "bbox_normalized": bbox_norm
                        })
                    else:
                        # Párrafo estándar / requisito técnico
                        results.append({
                            "node_type": "paragraph",
                            "hierarchy_path": f"/{base_name}/{current_chapter}",
                            "level": 0,
                            "title": None,
                            "content_text": text,
                            "structured_payload": {"has_requirement": has_requirement},
                            "page_number": page_no,
                            "bbox_normalized": bbox_norm
                        })

            total_pages = len(doc)
            doc.close()
            logger.info(f"PyMuPDF completó extracción de '{filename}': {len(results)} nodos estructurales en {total_pages} páginas.")
        except Exception as e:
            logger.error(f"Fallo extracción estructural PyMuPDF para '{filename}': {e}", exc_info=True)
        return results

    def _extract_txt(self, file_bytes: bytes, filename: str) -> List[Dict[str, Any]]:
        """Extrae párrafos y secciones desde archivos de texto plano."""
        text = file_bytes.decode("utf-8", errors="ignore")
        base_name = os.path.splitext(filename)[0]
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        
        results = []
        for idx, p in enumerate(paragraphs):
            results.append({
                "node_type": "paragraph",
                "hierarchy_path": f"/{base_name}/Párrafo_{idx + 1}",
                "level": 0,
                "title": f"Sección {idx + 1}",
                "content_text": p,
                "structured_payload": {},
                "page_number": 1
            })
        return results

    @staticmethod
    def _build_markdown_table(headers: List[str], rows: List[List[str]]) -> str:
        """Construye una representación Markdown estándar para tablas técnicas."""
        if not headers and not rows:
            return ""

        clean_headers = [h.replace("|", "/").strip() for h in headers]
        if not any(clean_headers) and rows:
            clean_headers = [f"Col {i+1}" for i in range(len(rows[0]))]

        header_line = "| " + " | ".join(clean_headers) + " |"
        sep_line = "| " + " | ".join(["---"] * len(clean_headers)) + " |"

        row_lines = []
        for r in rows:
            padded_row = r + [""] * (len(clean_headers) - len(r))
            clean_row = [str(c).replace("|", "/").replace("\n", " ").strip() for c in padded_row[:len(clean_headers)]]
            row_lines.append("| " + " | ".join(clean_row) + " |")

        return "\n".join([header_line, sep_line] + row_lines)
