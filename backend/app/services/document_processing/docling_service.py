import io
import os
import csv
import uuid
import re
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.core.logging import logger
from app.db.models.document_memory import DocumentStructuralNode

class DoclingService:
    """
    Servicio de extracción estructural de documentos técnicos (especificaciones,
    normas, line lists y tablas complejas) para piping y arquitectura.
    """

    def __init__(self):
        self._docling_available = False
        try:
            from docling.document_converter import DocumentConverter
            self._docling_available = True
            logger.info("Docling DocumentConverter disponible en el entorno.")
        except ImportError:
            logger.info("Docling no instalado; utilizando motor estructural nativo de alta precisión (PyMuPDF / openpyxl / CSV).")

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
        Extrae nodos estructurales (encabezados, tablas, notas y párrafos) desde el binario del archivo.
        Nunca propaga excepciones no controladas; en caso de error, retorna lista vacía y registra el log.
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
                nodes_data = self._extract_pdf(file_bytes, filename)
            elif ext == ".txt":
                nodes_data = self._extract_txt(file_bytes, filename)
            else:
                logger.warning(f"Formato '{ext}' no soportado para extracción estructural en DoclingService.")
                return []
        except Exception as e:
            logger.error(f"Error procesando extracción estructural para '{filename}': {str(e)}", exc_info=True)
            return []

        # Convertir diccionarios a instancias de DocumentStructuralNode
        created_nodes: List[DocumentStructuralNode] = []
        for item in nodes_data:
            node = DocumentStructuralNode(
                id=str(uuid.uuid4()),
                document_id=document_id,
                sheet_id=sheet_id,
                node_type=item.get("node_type", "paragraph"),
                hierarchy_path=item.get("hierarchy_path"),
                level=item.get("level", 0),
                title=item.get("title"),
                content_text=item.get("content_text", ""),
                structured_payload=item.get("structured_payload", {}),
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

    def _extract_pdf(self, file_bytes: bytes, filename: str) -> List[Dict[str, Any]]:
        """Extrae secciones jerárquicas y tablas desde documentos PDF usando PyMuPDF."""
        import fitz
        results = []
        base_name = os.path.splitext(filename)[0]

        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            current_section = "General"

            for page_idx in range(len(doc)):
                page = doc[page_idx]
                page_no = page_idx + 1
                rect = page.rect
                pw, ph = rect.width, rect.height

                # Extraer bloques de texto con metadatos
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

                    # Detectar si es encabezado (heurística de longitud y mayúsculas o numeración)
                    is_h1 = bool(re.match(r"^(CAP[ÍI]TULO|[0-9]+\.)\s+[A-ZÁÉÍÓÚ\s]{3,}", text))
                    is_h2 = bool(re.match(r"^[0-9]+\.[0-9]+\s+[A-ZÁÉÍÓÚa-záéíóú]", text))
                    is_table_like = "\t" in text or ("|" in text and len(text.split("\n")) > 2)

                    if is_h1:
                        current_section = text.split("\n")[0]
                        results.append({
                            "node_type": "heading",
                            "hierarchy_path": f"/{base_name}/{current_section}",
                            "level": 1,
                            "title": current_section,
                            "content_text": text,
                            "structured_payload": {"is_header": True},
                            "page_number": page_no,
                            "bbox_normalized": bbox_norm
                        })
                    elif is_h2:
                        h2_title = text.split("\n")[0]
                        results.append({
                            "node_type": "heading",
                            "hierarchy_path": f"/{base_name}/{current_section}/{h2_title}",
                            "level": 2,
                            "title": h2_title,
                            "content_text": text,
                            "structured_payload": {"is_header": True},
                            "page_number": page_no,
                            "bbox_normalized": bbox_norm
                        })
                    elif is_table_like:
                        lines = [l.strip() for l in text.split("\n") if l.strip()]
                        rows = [re.split(r"[\t|]+", l) for l in lines]
                        headers = rows[0] if rows else []
                        data_rows = rows[1:] if len(rows) > 1 else []
                        md_table = self._build_markdown_table(headers, data_rows)

                        results.append({
                            "node_type": "table",
                            "hierarchy_path": f"/{base_name}/{current_section}/Tabla_P{page_no}",
                            "level": 2,
                            "title": f"Tabla en Página {page_no}",
                            "content_text": md_table,
                            "structured_payload": {
                                "headers": headers,
                                "rows": data_rows,
                                "row_count": len(data_rows),
                                "col_count": len(headers),
                                "markdown_repr": md_table
                            },
                            "page_number": page_no,
                            "bbox_normalized": bbox_norm
                        })
                    else:
                        results.append({
                            "node_type": "paragraph",
                            "hierarchy_path": f"/{base_name}/{current_section}",
                            "level": 0,
                            "title": None,
                            "content_text": text,
                            "structured_payload": {},
                            "page_number": page_no,
                            "bbox_normalized": bbox_norm
                        })
            doc.close()
        except Exception as e:
            logger.warning(f"Fallo extracción estructural PyMuPDF para '{filename}': {e}")
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

        clean_headers = [h.replace("|", "/") for h in headers]
        if not clean_headers and rows:
            clean_headers = [f"Col {i+1}" for i in range(len(rows[0]))]

        header_line = "| " + " | ".join(clean_headers) + " |"
        sep_line = "| " + " | ".join(["---"] * len(clean_headers)) + " |"

        row_lines = []
        for r in rows:
            padded_row = r + [""] * (len(clean_headers) - len(r))
            clean_row = [str(c).replace("|", "/").replace("\n", " ") for c in padded_row[:len(clean_headers)]]
            row_lines.append("| " + " | ".join(clean_row) + " |")

        return "\n".join([header_line, sep_line] + row_lines)
