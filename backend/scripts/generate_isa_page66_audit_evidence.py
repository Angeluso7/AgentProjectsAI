import os
import json
import pymupdf
from app.services.tables.extractor import TableExtractor

def generate_evidence():
    pdf_candidates = [
        "data/intake_sources/388d7837-9c5d-45fb-b3eb-69909a915e43/170b22889574_ISA_5.1-2009.pdf",
        "/app/data/intake_sources/388d7837-9c5d-45fb-b3eb-69909a915e43/170b22889574_ISA_5.1-2009.pdf",
    ]
    pdf_path = next((p for p in pdf_candidates if os.path.exists(p)), None)
    if not pdf_path:
        raise FileNotFoundError("ISA PDF no encontrado en rutas esperadas.")

    doc = pymupdf.open(pdf_path)
    page66 = doc[65] # 0-indexed page 66
    pw, ph = int(page66.rect.width), int(page66.rect.height)
    extractor = TableExtractor(pw, ph)

    rx0, ry0, rx1, ry1 = 72.0 / pw, 72.0 / ph, 540.0 / pw, 720.0 / ph
    raw_blocks = page66.get_text("blocks")
    texts = [
        {"text": b[4].strip(), "bbox_normalized": [b[0] / pw, b[1] / ph, b[2] / pw, b[3] / ph]}
        for b in raw_blocks
        if b[4].strip()
    ]

    tbl = extractor.extract_from_region([rx0, ry0, rx1, ry1], texts, page=page66)
    if not tbl:
        raise RuntimeError("No se pudo extraer la tabla de la página 66.")

    # 1. Crear JSON de Auditoría
    audit_data = {
        "page_number": 66,
        "grid_source": tbl.grid_source,
        "grid_confidence": tbl.grid_confidence,
        "physical_grid_detected": tbl.physical_grid_detected,
        "num_rows": tbl.num_rows,
        "num_cols": tbl.num_cols,
        "total_cells": len(tbl.cells),
        "waveform_cells": [],
        "truth_matrix_cells": [],
        "all_cells_summary": [],
        "extracted_symbols": [
            {
                "symbol_name": s.symbol_name,
                "graphic_classification": s.graphic_classification,
                "content_class": getattr(s, "content_class", None),
                "row_index": s.row_index,
                "col_index": s.col_index,
                "geometric_confidence": s.geometric_confidence,
            }
            for s in (tbl.extracted_symbols or [])
        ]
    }

    # Pixmap para overlay visual
    # Render at 2x zoom for crisp rendering
    mat = pymupdf.Matrix(2.0, 2.0)
    pix = page66.get_pixmap(matrix=mat)
    overlay_doc = pymupdf.open()
    overlay_page = overlay_doc.new_page(width=pw, height=ph)
    # Dibujar la imagen base
    img_bytes = page66.get_pixmap().tobytes("png")
    overlay_page.insert_image(overlay_page.rect, stream=img_bytes)

    for cell in tbl.cells:
        cell_dict = {
            "row_index": cell.row_index,
            "column_index": cell.column_index,
            "bbox": cell.bbox,
            "graphic_classification": cell.graphic_classification,
            "content_class": cell.content_class,
            "has_symbol": cell.has_symbol,
            "geometric_confidence": cell.geometric_confidence,
            "boundary_evidence": cell.boundary_evidence,
            "text_snippet": (cell.text or "")[:40].replace("\n", " ")
        }
        audit_data["all_cells_summary"].append(cell_dict)

        # Determinar si es celda de forma de onda (waveform)
        is_waveform = (
            cell.graphic_classification in ["figure", "table_graphic"]
            or cell.content_class in ["figure", "table_graphic"]
            or any(m in (cell.text or "") for m in ["1\n0 A", "t 1", "X O t"])
        )
        if is_waveform:
            audit_data["waveform_cells"].append(cell_dict)

        # Determinar si es celda de matriz de verdad (A/B/C/X/O y 0/1)
        is_truth_matrix = (
            cell.content_class == "text_only"
            and ("A \nB \nC" in (cell.text or "") or "A\nB\nC" in (cell.text or ""))
            and any(v in (cell.text or "") for v in ["1 \n0 \n0", "0 \n0 \n0"])
        )
        if is_truth_matrix:
            audit_data["truth_matrix_cells"].append(cell_dict)

        # Dibujar rectángulos en overlay_page:
        # Denormalizar bbox a puntos
        cb = cell.bbox # [x0, y0, x1, y1] normalized
        rect = pymupdf.Rect(cb[0] * pw, cb[1] * ph, cb[2] * pw, cb[3] * ph)

        if is_waveform:
            # Púrpura / Magenta grueso para formas de onda (clasificadas como figure/table_graphic)
            overlay_page.draw_rect(rect, color=(0.7, 0.1, 0.8), width=2.5)
            # Label
            overlay_page.insert_text(
                pymupdf.Point(rect.x0 + 4, rect.y0 + 12),
                f"FIGURE/WAVEFORM (has_symbol=False, conf={cell.geometric_confidence:.2f})",
                fontsize=8,
                color=(0.7, 0.1, 0.8)
            )
            if cell.inner_drawing_bbox:
                idb = cell.inner_drawing_bbox
                idb_rect = pymupdf.Rect(idb[0] * pw, idb[1] * ph, idb[2] * pw, idb[3] * ph)
                overlay_page.draw_rect(idb_rect, color=(0.1, 0.8, 0.8), width=1.5, dashes="[2 2] 0")
        elif is_truth_matrix:
            # Azul para celdas de matriz textual
            overlay_page.draw_rect(rect, color=(0.1, 0.4, 0.9), width=1.8)
            overlay_page.insert_text(
                pymupdf.Point(rect.x0 + 4, rect.y0 + 12),
                "TEXT_ONLY MATRIX (0 symbols)",
                fontsize=8,
                color=(0.1, 0.4, 0.9)
            )
        elif cell.has_symbol:
            # Verde para celdas con símbolo genuino
            overlay_page.draw_rect(rect, color=(0.1, 0.7, 0.2), width=2.0)
            overlay_page.insert_text(
                pymupdf.Point(rect.x0 + 4, rect.y0 + 12),
                f"SYMBOL ({cell.content_class}, conf={cell.geometric_confidence:.2f})",
                fontsize=8,
                color=(0.1, 0.7, 0.2)
            )
        else:
            # Gris sutil para bordes de celdas estándar
            overlay_page.draw_rect(rect, color=(0.6, 0.6, 0.6), width=0.8)

    # Guardar salidas
    out_json_path = "backend/isa_page66_audit.json"
    out_png_path = "backend/isa_page66_annotated_overlay.png"

    with open(out_json_path, "w", encoding="utf-8") as f:
        json.dump(audit_data, f, indent=2, ensure_ascii=False)

    annotated_pix = overlay_page.get_pixmap(matrix=pymupdf.Matrix(2.0, 2.0))
    annotated_pix.save(out_png_path)

    print(f"Auditoría generada exitosamente:")
    print(f"- JSON: {out_json_path} ({len(audit_data['all_cells_summary'])} celdas)")
    print(f"- Waveform cells clasificadas como figure: {len(audit_data['waveform_cells'])}")
    print(f"- Truth matrix cells (text_only): {len(audit_data['truth_matrix_cells'])}")
    print(f"- Overlay PNG: {out_png_path}")

    doc.close()
    overlay_doc.close()

if __name__ == "__main__":
    generate_evidence()
