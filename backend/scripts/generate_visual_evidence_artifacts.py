import os
import sys
import json
import fitz
from PIL import Image

# Agregar backend al path
sys.path.insert(0, os.path.abspath("backend"))

from app.services.tables.extractor import TableExtractor

ARTIFACT_DIR = r"C:\Users\Windows\.gemini\antigravity-ide\brain\2efb811f-ae0e-4de3-8389-fe5b4db1fa73"
CROPS_DIR = os.path.join(ARTIFACT_DIR, "symbol_crops")
os.makedirs(CROPS_DIR, exist_ok=True)

def generate_isa51_table_demo():
    """Genera una página PDF con tabla ISA 5.1 alfanumérica y comprueba que arroja 0 símbolos."""
    doc = fitz.open()
    page = doc.new_page(width=800, height=600)

    col_x = [60, 160, 420, 720]
    row_y = [80, 120, 160, 200, 240, 280, 320]

    # Cuadrícula
    for y in row_y:
        page.draw_line(fitz.Point(col_x[0], y), fitz.Point(col_x[-1], y), color=(0, 0, 0), width=1.0)
    for x in col_x:
        page.draw_line(fitz.Point(x, row_y[0]), fitz.Point(x, row_y[-1]), color=(0, 0, 0), width=1.0)

    # Headers
    page.insert_text(fitz.Point(col_x[0] + 15, row_y[0] + 25), "LETRA", fontsize=11, fontname="helv", color=(0, 0, 0))
    page.insert_text(fitz.Point(col_x[1] + 15, row_y[0] + 25), "VARIABLE DE MEDICIÓN", fontsize=11, fontname="helv", color=(0, 0, 0))
    page.insert_text(fitz.Point(col_x[2] + 15, row_y[0] + 25), "FUNCIÓN MODIFICADORA", fontsize=11, fontname="helv", color=(0, 0, 0))

    rows_data = [
        ("A", "Análisis (Analysis)", "Alarma (Alarm)"),
        ("B", "Quemador / Llama (Burner)", "Elección del Usuario"),
        ("C", "Conductividad (Conductivity)", "Control"),
        ("D", "Densidad (Density)", "Diferencial"),
        ("P", "Presión (Pressure)", "Punto de Prueba (Test Point)"),
    ]

    for idx, (code, var, func) in enumerate(rows_data, start=1):
        cy = (row_y[idx] + row_y[idx + 1]) / 2 + 4
        page.insert_text(fitz.Point(col_x[0] + 40, cy), code, fontsize=12, fontname="helv", color=(0, 0, 0))
        page.insert_text(fitz.Point(col_x[1] + 15, cy), var, fontsize=10, fontname="helv", color=(0, 0, 0))
        page.insert_text(fitz.Point(col_x[2] + 15, cy), func, fontsize=10, fontname="helv", color=(0, 0, 0))

    # Guardar imagen de la tabla ISA 5.1
    pix = page.get_pixmap(dpi=150)
    isa_img_path = os.path.join(ARTIFACT_DIR, "isa51_table_visual.png")
    pix.save(isa_img_path)

    # Extraer textos y dibujos con PyMuPDF
    words = page.get_text("words")
    texts = []
    for w in words:
        texts.append({
            "text": w[4],
            "clean_text": w[4],
            "bbox_normalized": [w[0]/800.0, w[1]/600.0, w[2]/800.0, w[3]/600.0],
            "id": f"txt_{w[4]}",
            "confidence": 0.98
        })
    drawings = page.get_drawings()

    extractor = TableExtractor(width_px=800, height_px=600)
    res = extractor.extract_from_region(
        region_bbox_norm=[col_x[0]/800.0, row_y[0]/600.0, col_x[-1]/800.0, row_y[-1]/600.0],
        texts=texts,
        page=page,
        drawings=drawings,
        crops_dir=CROPS_DIR,
        doc_uid="isa51_doc"
    )

    doc.close()

    return {
        "image_path": isa_img_path,
        "symbols_extracted_count": len(res.extracted_symbols),
        "has_symbols": res.has_symbols,
        "reading_orientation": res.reading_orientation,
        "orientation_reason": res.orientation_reason,
        "total_cells": len(res.cells),
        "cell_types": [c.cell_type for c in res.cells]
    }

def generate_technical_legend_demo():
    """Genera una leyenda técnica con símbolos geométricos reales (válvulas, check, extintor) y crops."""
    doc = fitz.open()
    page = doc.new_page(width=800, height=600)

    col_x = [60, 200, 520, 740]
    row_y = [80, 120, 190, 260, 330]

    # Cuadrícula
    for y in row_y:
        page.draw_line(fitz.Point(col_x[0], y), fitz.Point(col_x[-1], y), color=(0, 0, 0), width=1.0)
    for x in col_x:
        page.draw_line(fitz.Point(x, row_y[0]), fitz.Point(x, row_y[-1]), color=(0, 0, 0), width=1.0)

    # Headers
    page.insert_text(fitz.Point(col_x[0] + 15, row_y[0] + 25), "SÍMBOLO", fontsize=11, fontname="helv", color=(0, 0, 0))
    page.insert_text(fitz.Point(col_x[1] + 15, row_y[0] + 25), "DESCRIPCIÓN DEL EQUIPO", fontsize=11, fontname="helv", color=(0, 0, 0))
    page.insert_text(fitz.Point(col_x[2] + 15, row_y[0] + 25), "NORMA / TAG", fontsize=11, fontname="helv", color=(0, 0, 0))

    # Filas con geometrías reales en Col 0:
    items = [
        {
            "name": "VÁLVULA DE COMPUERTA MANUAL",
            "tag": "ASME B16.34 / GATE",
            "draw": lambda p, cx, cy: (
                p.draw_line(fitz.Point(cx - 20, cy - 14), fitz.Point(cx + 20, cy + 14), color=(0, 0, 0), width=2.0),
                p.draw_line(fitz.Point(cx - 20, cy + 14), fitz.Point(cx + 20, cy - 14), color=(0, 0, 0), width=2.0),
                p.draw_line(fitz.Point(cx - 20, cy - 14), fitz.Point(cx - 20, cy + 14), color=(0, 0, 0), width=2.0),
                p.draw_line(fitz.Point(cx + 20, cy - 14), fitz.Point(cx + 20, cy + 14), color=(0, 0, 0), width=2.0),
                p.draw_line(fitz.Point(cx, cy), fitz.Point(cx, cy - 20), color=(0, 0, 0), width=1.5),
                p.draw_circle(fitz.Point(cx, cy - 20), 5, color=(0, 0, 0), width=1.5)
            )
        },
        {
            "name": "VÁLVULA CHECK DE RETENCIÓN",
            "tag": "API 594 / CHK-01",
            "draw": lambda p, cx, cy: (
                p.draw_line(fitz.Point(cx - 22, cy - 12), fitz.Point(cx + 22, cy + 12), color=(0, 0, 0), width=2.0),
                p.draw_line(fitz.Point(cx - 22, cy + 12), fitz.Point(cx + 22, cy - 12), color=(0, 0, 0), width=2.0),
                p.draw_line(fitz.Point(cx - 22, cy - 12), fitz.Point(cx - 22, cy + 12), color=(0, 0, 0), width=2.0),
                p.draw_line(fitz.Point(cx + 22, cy - 12), fitz.Point(cx + 22, cy + 12), color=(0, 0, 0), width=2.0),
                p.draw_line(fitz.Point(cx - 8, cy), fitz.Point(cx + 8, cy), color=(0, 0, 0), width=2.0),
                p.draw_line(fitz.Point(cx + 2, cy - 6), fitz.Point(cx + 8, cy), color=(0, 0, 0), width=2.0),
                p.draw_line(fitz.Point(cx + 2, cy + 6), fitz.Point(cx + 8, cy), color=(0, 0, 0), width=2.0)
            )
        },
        {
            "name": "PULSADOR DE ALARMA MANUAL",
            "tag": "NFPA 72 / PAL-101",
            "draw": lambda p, cx, cy: (
                p.draw_rect(fitz.Rect(cx - 18, cy - 18, cx + 18, cy + 18), color=(0, 0, 0), width=2.0),
                p.draw_circle(fitz.Point(cx, cy), 9, color=(0, 0, 0), fill=(0, 0, 0), width=1.5),
                p.draw_line(fitz.Point(cx - 18, cy - 18), fitz.Point(cx + 18, cy + 18), color=(0, 0, 0), width=1.0)
            )
        }
    ]

    for idx, item in enumerate(items, start=1):
        cx_sym = (col_x[0] + col_x[1]) / 2
        cy_sym = (row_y[idx] + row_y[idx + 1]) / 2
        item["draw"](page, cx_sym, cy_sym)

        cy_text = (row_y[idx] + row_y[idx + 1]) / 2 + 5
        page.insert_text(fitz.Point(col_x[1] + 15, cy_text), item["name"], fontsize=10, fontname="helv", color=(0, 0, 0))
        page.insert_text(fitz.Point(col_x[2] + 15, cy_text), item["tag"], fontsize=10, fontname="helv", color=(0, 0, 0))

    legend_img_path = os.path.join(ARTIFACT_DIR, "technical_legend_visual.png")
    pix = page.get_pixmap(dpi=150)
    pix.save(legend_img_path)

    # Textos y dibujos
    words = page.get_text("words")
    texts = []
    for w in words:
        texts.append({
            "text": w[4],
            "clean_text": w[4],
            "bbox_normalized": [w[0]/800.0, w[1]/600.0, w[2]/800.0, w[3]/600.0],
            "id": f"txt_{w[4]}",
            "confidence": 0.98
        })
    drawings = page.get_drawings()

    extractor = TableExtractor(width_px=800, height_px=600)
    res = extractor.extract_from_region(
        region_bbox_norm=[col_x[0]/800.0, row_y[0]/600.0, col_x[-1]/800.0, row_y[-1]/600.0],
        texts=texts,
        page=page,
        drawings=drawings,
        crops_dir=CROPS_DIR,
        doc_uid="legend_real_doc"
    )

    doc.close()

    symbols_data = []
    for s in res.extracted_symbols:
        symbols_data.append({
            "name": s.symbol_name,
            "crop_path": s.crop_image_path,
            "crop_filename": os.path.basename(s.crop_image_path) if s.crop_image_path else None,
            "geometric_evidence": s.geometric_evidence,
            "geometric_confidence": s.geometric_confidence,
            "evidence_sources": s.evidence_sources,
            "row_index": s.row_index,
            "col_index": s.col_index,
            "text_mask_overlap_ratio": s.text_mask_overlap_ratio
        })

    return {
        "image_path": legend_img_path,
        "symbols_extracted_count": len(res.extracted_symbols),
        "has_symbols": res.has_symbols,
        "reading_orientation": res.reading_orientation,
        "orientation_reason": res.orientation_reason,
        "symbols": symbols_data
    }

if __name__ == "__main__":
    isa_res = generate_isa51_table_demo()
    leg_res = generate_technical_legend_demo()

    report = {
        "isa51_result": isa_res,
        "legend_result": leg_res
    }

    report_path = os.path.join(ARTIFACT_DIR, "symbol_geometry_evidence_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("=== EVIDENCE GENERATION COMPLETED ===")
    print(f"ISA 5.1 Symbols Extracted: {isa_res['symbols_extracted_count']} (Expected: 0)")
    print(f"Technical Legend Symbols Extracted: {leg_res['symbols_extracted_count']} (Expected: 3)")
    for s in leg_res["symbols"]:
        print(f" - {s['name']}: crop={s['crop_filename']}, geo_conf={s['geometric_confidence']}, sources={s['evidence_sources']}")
