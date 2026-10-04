import io
import os
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.core.logging import logger
from app.db.models.document_memory import DocumentStructuralNode

class DxfService:
    """
    Servicio de extracción semántica nativa para archivos CAD en formato DXF.
    Extrae capas, bloques con atributos (válvulas, instrumentos), textos y trazados de cañerías.
    """

    def __init__(self):
        self._ezdxf_available = False
        try:
            import ezdxf
            self._ezdxf_available = True
            logger.info("ezdxf disponible en el entorno.")
        except ImportError:
            logger.warning("ezdxf no instalado; extracción DXF operará en modo stub/fallback.")

    def is_available(self) -> bool:
        return self._ezdxf_available

    def parse_dxf_summary(self, file_bytes: bytes, filename: str) -> Dict[str, Any]:
        """
        Analiza el binario DXF y retorna una estructura completa de capas, bloques y textos.
        """
        if not file_bytes:
            return {"error": "Archivo vacío", "filename": filename}

        if not self._ezdxf_available:
            return {
                "filename": filename,
                "error": "ezdxf no disponible en el servidor",
                "layers": [],
                "blocks_inserted": [],
                "texts": []
            }

        try:
            import ezdxf
            # Intentar decodificar como texto UTF-8 o latin1
            text_stream = io.StringIO(file_bytes.decode("utf-8", errors="ignore"))
            doc = ezdxf.read(text_stream)
            msp = doc.modelspace()

            # 1. Capas (Layers)
            layers_info = []
            for layer in doc.layers:
                layers_info.append({
                    "name": layer.dxf.name,
                    "color": getattr(layer.dxf, "color", 7),
                    "is_locked": layer.is_locked(),
                    "is_off": layer.is_off()
                })

            # 2. Bloques Insertados (INSERT) y Atributos (ATTRIB)
            blocks_inserted = []
            for insert in msp.query("INSERT"):
                block_name = insert.dxf.name
                layer_name = insert.dxf.layer
                ins_pt = [round(insert.dxf.insert.x, 3), round(insert.dxf.insert.y, 3)]
                rotation = getattr(insert.dxf, "rotation", 0.0)
                
                # Extraer atributos asociados al bloque
                attribs = {}
                for attrib in insert.attribs:
                    tag_name = getattr(attrib.dxf, "tag", "")
                    tag_val = getattr(attrib.dxf, "text", "")
                    if tag_name:
                        attribs[tag_name] = tag_val

                blocks_inserted.append({
                    "block_name": block_name,
                    "layer": layer_name,
                    "insertion_point": ins_pt,
                    "rotation_deg": rotation,
                    "attributes": attribs
                })

            # 3. Textos (TEXT y MTEXT)
            texts_extracted = []
            for txt_ent in msp.query("TEXT MTEXT"):
                txt_val = getattr(txt_ent.dxf, "text", "")
                if not txt_val and hasattr(txt_ent, "text"):
                    txt_val = txt_ent.text # Para MTEXT
                
                if txt_val.strip():
                    ins_pt = [round(txt_ent.dxf.insert.x, 3), round(txt_ent.dxf.insert.y, 3)]
                    texts_extracted.append({
                        "text": txt_val.strip(),
                        "layer": txt_ent.dxf.layer,
                        "insertion_point": ins_pt,
                        "height": getattr(txt_ent.dxf, "height", 2.5)
                    })

            # 4. Conteo de Entidades de Trazado
            lines_count = len(msp.query("LINE"))
            polylines_count = len(msp.query("LWPOLYLINE POLYLINE"))
            circles_count = len(msp.query("CIRCLE ARC"))

            return {
                "filename": filename,
                "dxf_version": doc.dxfversion,
                "layers": layers_info,
                "blocks_inserted": blocks_inserted,
                "texts": texts_extracted,
                "summary": {
                    "total_layers": len(layers_info),
                    "total_blocks": len(blocks_inserted),
                    "total_texts": len(texts_extracted),
                    "total_lines": lines_count,
                    "total_polylines": polylines_count,
                    "total_circles": circles_count
                }
            }
        except Exception as e:
            logger.error(f"Error procesando DXF '{filename}': {str(e)}", exc_info=True)
            return {
                "filename": filename,
                "error": f"Fallo en parseo DXF: {str(e)}",
                "layers": [],
                "blocks_inserted": [],
                "texts": []
            }

    def extract_structural_nodes(
        self,
        file_bytes: bytes,
        filename: str,
        document_id: str,
        sheet_id: Optional[str] = None
    ) -> List[DocumentStructuralNode]:
        """
        Convierte la información extraída de un archivo DXF a nodos estructurales
        (resumen de bloques de piping, tabla de capas y notas de texto).
        """
        summary_data = self.parse_dxf_summary(file_bytes, filename)
        if "error" in summary_data and not summary_data.get("layers"):
            return []

        base_name = os.path.splitext(filename)[0]
        nodes: List[DocumentStructuralNode] = []

        # 1. Nodo: Tabla Resumen de Capas CAD
        layers = summary_data.get("layers", [])
        if layers:
            layer_headers = ["Layer Name", "Color Index", "Locked", "Status"]
            layer_rows = [
                [l["name"], str(l.get("color", 7)), "Yes" if l.get("is_locked") else "No", "Off" if l.get("is_off") else "Active"]
                for l in layers[:30] # Top 30 capas
            ]
            layer_md = self._build_markdown_table(layer_headers, layer_rows)
            
            node_layers = DocumentStructuralNode(
                id=str(uuid.uuid4()),
                document_id=document_id,
                sheet_id=sheet_id,
                node_type="table",
                hierarchy_path=f"/{base_name}/CAD_Layers",
                level=1,
                title=f"Capas CAD: {filename}",
                content_text=layer_md,
                structured_payload={
                    "headers": layer_headers,
                    "rows": layer_rows,
                    "row_count": len(layer_rows),
                    "col_count": len(layer_headers),
                    "markdown_repr": layer_md
                },
                page_number=1
            )
            nodes.append(node_layers)

        # 2. Nodo: Resumen de Bloques de Piping / Instrumentación (INSERT)
        blocks = summary_data.get("blocks_inserted", [])
        if blocks:
            block_headers = ["Block Name", "Layer", "Tag / ID", "Coordinates (X,Y)"]
            block_rows = []
            for b in blocks[:50]: # Top 50 bloques
                tag = b.get("attributes", {}).get("TAG", "") or b.get("attributes", {}).get("TAG_NO", "") or "-"
                coords = f"({b['insertion_point'][0]}, {b['insertion_point'][1]})"
                block_rows.append([b["block_name"], b["layer"], tag, coords])

            block_md = self._build_markdown_table(block_headers, block_rows)
            node_blocks = DocumentStructuralNode(
                id=str(uuid.uuid4()),
                document_id=document_id,
                sheet_id=sheet_id,
                node_type="dxf_block_summary",
                hierarchy_path=f"/{base_name}/Piping_Blocks",
                level=1,
                title=f"Bloques Técnicos de Piping ({len(blocks)} detectados)",
                content_text=block_md,
                structured_payload={
                    "headers": block_headers,
                    "rows": block_rows,
                    "blocks_count": len(blocks),
                    "markdown_repr": block_md
                },
                page_number=1
            )
            nodes.append(node_blocks)

        # 3. Nodo: Notas y Textos Relevantes del Plano
        texts = summary_data.get("texts", [])
        if texts:
            all_text_str = "\n".join([f"- [{t['layer']}] {t['text']}" for t in texts[:60]])
            node_texts = DocumentStructuralNode(
                id=str(uuid.uuid4()),
                document_id=document_id,
                sheet_id=sheet_id,
                node_type="technical_note",
                hierarchy_path=f"/{base_name}/Anotaciones_Texto",
                level=2,
                title="Anotaciones y Textos Técnicos",
                content_text=all_text_str,
                structured_payload={"text_count": len(texts)},
                page_number=1
            )
            nodes.append(node_texts)

        return nodes

    @staticmethod
    def _build_markdown_table(headers: List[str], rows: List[List[str]]) -> str:
        if not headers and not rows:
            return ""
        clean_headers = [h.replace("|", "/") for h in headers]
        header_line = "| " + " | ".join(clean_headers) + " |"
        sep_line = "| " + " | ".join(["---"] * len(clean_headers)) + " |"
        row_lines = []
        for r in rows:
            padded = r + [""] * (len(clean_headers) - len(r))
            clean_r = [str(c).replace("|", "/").replace("\n", " ") for c in padded[:len(clean_headers)]]
            row_lines.append("| " + " | ".join(clean_r) + " |")
        return "\n".join([header_line, sep_line] + row_lines)
