import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

@dataclass
class ExtractedCellDTO:
    row_index: int
    column_index: int
    text: str
    normalized_text: str
    confidence: float
    bbox: List[float]
    bbox_normalized: List[float]
    is_header: bool
    source_text_refs: List[str]

@dataclass
class ExtractedTableDTO:
    title: str
    bbox: List[float]
    bbox_normalized: List[float]
    row_count: int
    column_count: int
    confidence: float
    extraction_status: str
    headers: List[str]
    cells: List[ExtractedCellDTO]
    raw_structure: Dict[str, Any]

class TableExtractor:
    """Extractor espacial híbrido y auditable de tablas a partir de bloques OCR."""

    def __init__(self, width_px: int = 8000, height_px: int = 6000):
        self.width_px = width_px
        self.height_px = height_px

    def extract_from_region(
        self,
        region_bbox_norm: List[float],
        texts: List[Any]
    ) -> Optional[ExtractedTableDTO]:
        rx0, ry0, rx1, ry1 = region_bbox_norm

        # 1. Filtrar textos que caigan dentro de la macro-región
        region_texts = []
        for t in texts:
            tx0, ty0, tx1, ty1 = t.bbox_normalized
            # Centroide del texto
            cx = (tx0 + tx1) / 2.0
            cy = (ty0 + ty1) / 2.0
            if rx0 <= cx <= rx1 and ry0 <= cy <= ry1:
                region_texts.append(t)

        if not region_texts:
            return None

        # 2. Separar título si la línea superior contiene palabras clave de tabla
        region_texts.sort(key=lambda t: (t.bbox_normalized[1], t.bbox_normalized[0]))
        title = "Cuadro Técnico"
        body_texts = list(region_texts)

        first_line = body_texts[0]
        if re.search(r"(CUADRO|TABLA|LISTA|RESUMEN|ESPECIFICACI)", first_line.text.upper()):
            title = first_line.text.strip()
            body_texts = body_texts[1:]

        if not body_texts:
            body_texts = [first_line]

        # 3. Agrupación en Filas por coordenada Y
        rows: List[List[Any]] = []
        row_tol = 0.015 # 1.5% de tolerancia vertical normalizada

        for t in body_texts:
            cy = (t.bbox_normalized[1] + t.bbox_normalized[3]) / 2.0
            placed = False
            for r in rows:
                r_cy = sum((item.bbox_normalized[1] + item.bbox_normalized[3]) / 2.0 for item in r) / len(r)
                if abs(cy - r_cy) <= row_tol:
                    r.append(t)
                    placed = True
                    break
            if not placed:
                rows.append([t])

        # Ordenar filas de arriba hacia abajo y textos de cada fila de izquierda a derecha
        rows.sort(key=lambda r: min(t.bbox_normalized[1] for t in r))
        for r in rows:
            r.sort(key=lambda t: t.bbox_normalized[0])

        if not rows:
            return None

        # 4. Agrupación en Columnas por coordenada X
        col_centers: List[float] = []
        col_tol = 0.035 # 3.5% tolerancia horizontal

        for r in rows:
            for t in r:
                cx = (t.bbox_normalized[0] + t.bbox_normalized[2]) / 2.0
                placed = False
                for i, col_cx in enumerate(col_centers):
                    if abs(cx - col_cx) <= col_tol:
                        # Refinar centro de columna con promedio móvil
                        col_centers[i] = (col_centers[i] + cx) / 2.0
                        placed = True
                        break
                if not placed:
                    col_centers.append(cx)

        col_centers.sort()
        num_cols = max(len(col_centers), 1)
        num_rows = len(rows)

        # 5. Construcción de matriz de celdas
        cells_dto: List[ExtractedCellDTO] = []
        headers_list: List[str] = []
        confidences: List[float] = []

        for r_idx, row_items in enumerate(rows):
            is_header_row = (r_idx == 0)
            row_cells_by_col: Dict[int, List[Any]] = {c: [] for c in range(num_cols)}

            for t in row_items:
                cx = (t.bbox_normalized[0] + t.bbox_normalized[2]) / 2.0
                # Encontrar la columna más cercana
                closest_col = min(range(num_cols), key=lambda c: abs(cx - col_centers[c]))
                row_cells_by_col[closest_col].append(t)

            for c_idx in range(num_cols):
                matched_items = row_cells_by_col[c_idx]
                if matched_items:
                    cell_text = " ".join(item.text.strip() for item in matched_items)
                    clean_txt = " ".join(item.clean_text.strip() if item.clean_text else item.text.strip() for item in matched_items)
                    cell_conf = sum(item.confidence for item in matched_items) / len(matched_items)
                    c_x0 = min(item.bbox_normalized[0] for item in matched_items)
                    c_y0 = min(item.bbox_normalized[1] for item in matched_items)
                    c_x1 = max(item.bbox_normalized[2] for item in matched_items)
                    c_y1 = max(item.bbox_normalized[3] for item in matched_items)
                    src_refs = [item.id for item in matched_items]
                else:
                    # Celda vacía inferida en la grilla
                    cell_text = ""
                    clean_txt = ""
                    cell_conf = 0.80
                    src_refs = []
                    col_x = col_centers[c_idx]
                    c_x0 = max(rx0, col_x - 0.02)
                    c_x1 = min(rx1, col_x + 0.02)
                    c_y0 = rows[r_idx][0].bbox_normalized[1]
                    c_y1 = rows[r_idx][0].bbox_normalized[3]

                confidences.append(cell_conf)

                if is_header_row and cell_text:
                    headers_list.append(cell_text)

                cell_bbox_px = [
                    round(c_x0 * self.width_px, 1),
                    round(c_y0 * self.height_px, 1),
                    round(c_x1 * self.width_px, 1),
                    round(c_y1 * self.height_px, 1),
                ]
                cell_bbox_norm = [round(c_x0, 4), round(c_y0, 4), round(c_x1, 4), round(c_y1, 4)]

                cells_dto.append(
                    ExtractedCellDTO(
                        row_index=r_idx,
                        column_index=c_idx,
                        text=cell_text,
                        normalized_text=clean_txt,
                        confidence=round(cell_conf, 3),
                        bbox=cell_bbox_px,
                        bbox_normalized=cell_bbox_norm,
                        is_header=is_header_row,
                        source_text_refs=src_refs
                    )
                )

        table_conf = sum(confidences) / len(confidences) if confidences else 0.50
        status = "extracted" if table_conf >= 0.70 else "low_confidence"

        bbox_px = [
            round(rx0 * self.width_px, 1),
            round(ry0 * self.height_px, 1),
            round(rx1 * self.width_px, 1),
            round(ry1 * self.height_px, 1),
        ]

        raw_struct = {
            "title": title,
            "headers": headers_list,
            "row_count": num_rows,
            "column_count": num_cols,
            "non_empty_cells": len([c for c in cells_dto if c.text]),
            "total_cells": len(cells_dto)
        }

        return ExtractedTableDTO(
            title=title,
            bbox=bbox_px,
            bbox_normalized=[round(rx0, 4), round(ry0, 4), round(rx1, 4), round(ry1, 4)],
            row_count=num_rows,
            column_count=num_cols,
            confidence=round(table_conf, 3),
            extraction_status=status,
            headers=headers_list,
            cells=cells_dto,
            raw_structure=raw_struct
        )
