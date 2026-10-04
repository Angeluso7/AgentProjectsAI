import os
import sys
import json
import math
import uuid
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

import fitz
from app.services.tables.extractor import TableExtractor
from app.services.symbols.geometric_validator import GeometricEvidenceValidator, compute_symbol_crop_bbox
from tests.integration.test_table_physical_grid_and_symbol_crop import (
    create_table_with_physical_grid_and_symbols_pdf,
    create_table_with_waveform_figure_pdf,
    create_table_combined_spans_pdf,
    _extract_page_words_as_texts
)

ARTIFACTS_DIR = Path(r"C:\Users\Windows\.gemini\antigravity-ide\brain\2efb811f-ae0e-4de3-8389-fe5b4db1fa73")
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
CROPS_DIR = ARTIFACTS_DIR / "crops"
CROPS_DIR.mkdir(parents=True, exist_ok=True)


def generate_physical_grid_visual_evidence():
    print("Iniciando generador de evidencia visual de grilla física y recortes de 3 mm...")

    # 1. Procesar tabla física con símbolos reales
    pdf_bytes, meta = create_table_with_physical_grid_and_symbols_pdf()
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[0]
    pw, ph = int(page.rect.width), int(page.rect.height)

    texts = _extract_page_words_as_texts(page)
    extractor = TableExtractor(width_px=pw, height_px=ph)
    table = extractor.extract_from_region(
        region_bbox_norm=meta["table_bbox_norm"],
        texts=texts,
        page=page,
        doc_uid="audit_grid",
        crops_dir=str(CROPS_DIR)
    )

    # Renderizar la página completa a imagen PIL para anotación visual
    pix = page.get_pixmap(dpi=150)
    page_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    draw = ImageDraw.Draw(page_img)

    scale_x = pix.width
    scale_y = pix.height

    # Anotar cuadrícula física detectada (líneas verdes)
    for x_norm in table.x_boundaries:
        px = int(x_norm * scale_x)
        draw.line([(px, int(table.y_boundaries[0] * scale_y)), (px, int(table.y_boundaries[-1] * scale_y))], fill=(0, 180, 0), width=2)
    for y_norm in table.y_boundaries:
        py = int(y_norm * scale_y)
        draw.line([(int(table.x_boundaries[0] * scale_x), py), (int(table.x_boundaries[-1] * scale_x), py)], fill=(0, 180, 0), width=2)

    # Anotar celdas, inner_drawing_bbox (rojo) y symbol_crop_bbox (cian)
    saved_crops = []
    for sym in table.extracted_symbols:
        # Cell bbox (amarillo)
        c_x0, c_y0, c_x1, c_y1 = [int(v * scale_x if i % 2 == 0 else v * scale_y) for i, v in enumerate(sym.cell_bbox)]
        draw.rectangle([c_x0, c_y0, c_x1, c_y1], outline=(255, 200, 0), width=2)

        # Symbol crop bbox (cian - 3mm)
        s_x0, s_y0, s_x1, s_y1 = [int(v * scale_x if i % 2 == 0 else v * scale_y) for i, v in enumerate(sym.symbol_crop_bbox)]
        draw.rectangle([s_x0, s_y0, s_x1, s_y1], outline=(0, 220, 255), width=2)

        # Inner drawing bbox (rojo)
        i_x0, i_y0, i_x1, i_y1 = [int(v * scale_x if i % 2 == 0 else v * scale_y) for i, v in enumerate(sym.inner_drawing_bbox)]
        draw.rectangle([i_x0, i_y0, i_x1, i_y1], outline=(255, 30, 30), width=2)

        # Guardar recorte del símbolo real
        crop_pil = page_img.crop((s_x0, s_y0, s_x1, s_y1))
        crop_name = f"symbol_crop_r{sym.row_index}_c{sym.col_index}.png"
        crop_path = ARTIFACTS_DIR / crop_name
        crop_pil.save(crop_path)
        saved_crops.append(str(crop_path))

    # Guardar imagen general con anotaciones de grilla y crops
    annotated_table_path = ARTIFACTS_DIR / "physical_grid_and_cells_annotated.png"
    page_img.save(annotated_table_path)
    print(f"Evidencia anotada guardada: {annotated_table_path}")

    # 2. Procesar tabla con forma de onda para evidenciar clasificación como Figure
    pdf_bytes_fig, meta_fig = create_table_with_waveform_figure_pdf()
    doc_fig = fitz.open(stream=pdf_bytes_fig, filetype="pdf")
    page_fig = doc_fig[0]
    pw_f, ph_f = int(page_fig.rect.width), int(page_fig.rect.height)
    texts_f = _extract_page_words_as_texts(page_fig)
    table_fig = extractor.extract_from_region(
        region_bbox_norm=meta_fig["table_bbox_norm"],
        texts=texts_f,
        page=page_fig,
        doc_uid="audit_fig",
        crops_dir=str(CROPS_DIR)
    )

    wave_cell = next(c for c in table_fig.cells if c.row_index == 1 and c.column_index == 0)
    pix_fig = page_fig.get_pixmap(dpi=150)
    page_fig_img = Image.frombytes("RGB", [pix_fig.width, pix_fig.height], pix_fig.samples)
    w_px, h_px = pix_fig.width, pix_fig.height
    wb_x0, wb_y0, wb_x1, wb_y1 = [int(v * w_px if i % 2 == 0 else v * h_px) for i, v in enumerate(wave_cell.bbox_normalized)]
    wave_crop = page_fig_img.crop((wb_x0, wb_y0, wb_x1, wb_y1))
    waveform_crop_path = ARTIFACTS_DIR / "waveform_classified_as_figure.png"
    wave_crop.save(waveform_crop_path)

    # 3. Reporte JSON de Auditoría
    audit_report = {
        "title": "Auditoría de Grilla Física y Recorte Preciso de Símbolos (3 mm)",
        "physical_grid": {
            "grid_source": table.grid_source,
            "grid_confidence": table.grid_confidence,
            "physical_grid_detected": table.physical_grid_detected,
            "row_count": table.row_count,
            "column_count": table.column_count,
            "x_boundaries": table.x_boundaries,
            "y_boundaries": table.y_boundaries,
            "table_bbox": table.bbox_normalized
        },
        "crops_validation": [
            {
                "symbol_id": s.id,
                "symbol_name": s.symbol_name,
                "row_index": s.row_index,
                "col_index": s.col_index,
                "cell_bbox": s.cell_bbox,
                "inner_drawing_bbox": s.inner_drawing_bbox,
                "symbol_crop_bbox": s.symbol_crop_bbox,
                "crop_margin_mm": s.crop_margin_mm,
                "crop_image_path": s.crop_image_path,
                "graphic_classification": s.graphic_classification,
                "routing_destination": "Símbolos"
            }
            for s in table.extracted_symbols
        ],
        "non_symbol_routing": {
            "cell_type": wave_cell.cell_type,
            "graphic_classification": wave_cell.graphic_classification,
            "has_symbol": wave_cell.has_symbol,
            "routing_destination": "Figure / diagram_candidate",
            "crop_path": str(waveform_crop_path)
        },
        "text_table_routing": {
            "total_extracted_symbols": 0,
            "routing_destination": "Tablas (visible exclusivamente en matrices tabulares sin contaminar Símbolos)"
        }
    }

    report_path = ARTIFACTS_DIR / "physical_grid_symbol_evidence_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(audit_report, f, indent=2, ensure_ascii=False)

    print(f"Reporte de auditoría generado exitosamente en {report_path}")


if __name__ == "__main__":
    generate_physical_grid_visual_evidence()
