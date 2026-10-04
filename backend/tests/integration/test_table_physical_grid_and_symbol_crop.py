import os
import math
import uuid
import pytest
import fitz
import numpy as np
from pathlib import Path

from app.core.config import settings
from app.services.tables.extractor import TableExtractor, ExtractedTableDTO, ExtractedCellDTO
from app.services.symbols.geometric_validator import GeometricEvidenceValidator, compute_symbol_crop_bbox
from app.services.extraction.candidate_generator_service import CandidateGeneratorService
from app.db.models.intake_extractions import SourceExtraction, ExtractedItem


# =============================================================================
# GENERADORES DE PDF PARA TEST DE GRILLA FÍSICA Y CROPS
# =============================================================================

def create_table_with_physical_grid_and_symbols_pdf() -> tuple[bytes, dict]:
    """
    Tabla de 4 filas x 3 columnas con grilla física vectorial nítida (1.0 pt).
    - Fila 0: Encabezados ("SÍMBOLO", "DESCRIPCIÓN", "CÓDIGO")
    - Fila 1: Válvula de compuerta (geometría de 2 triángulos cruzados)
    - Fila 2: Válvula de bola (círculo con línea)
    - Fila 3: Válvula check (cuadrado con flecha)
    """
    doc = fitz.open()
    page = doc.new_page(width=800, height=600)

    col_x = [60, 220, 560, 740]  # 3 columnas
    row_y = [80, 130, 210, 290, 370]  # 4 filas: 1 header + 3 datos

    # Dibujar líneas físicas de grilla
    for y in row_y:
        page.draw_line(fitz.Point(col_x[0], y), fitz.Point(col_x[-1], y), color=(0, 0, 0), width=1.0)
    for x in col_x:
        page.draw_line(fitz.Point(x, row_y[0]), fitz.Point(x, row_y[-1]), color=(0, 0, 0), width=1.0)

    # Headers
    page.insert_text(fitz.Point(col_x[0] + 15, row_y[0] + 30), "SÍMBOLO", fontsize=10, fontname="helv", color=(0, 0, 0))
    page.insert_text(fitz.Point(col_x[1] + 15, row_y[0] + 30), "DESCRIPCIÓN TÉCNICA", fontsize=10, fontname="helv", color=(0, 0, 0))
    page.insert_text(fitz.Point(col_x[2] + 15, row_y[0] + 30), "TAG / NORMA", fontsize=10, fontname="helv", color=(0, 0, 0))

    # Fila 1: Válvula Compuerta
    cy1 = (row_y[1] + row_y[2]) / 2.0
    cx1 = (col_x[0] + col_x[1]) / 2.0
    # Geometría interior acotada: ancho 30 pt, alto 20 pt
    page.draw_line(fitz.Point(cx1 - 15, cy1 - 10), fitz.Point(cx1 + 15, cy1 + 10), color=(0, 0, 0), width=2.0)
    page.draw_line(fitz.Point(cx1 - 15, cy1 + 10), fitz.Point(cx1 + 15, cy1 - 10), color=(0, 0, 0), width=2.0)
    page.draw_line(fitz.Point(cx1 - 15, cy1 - 10), fitz.Point(cx1 - 15, cy1 + 10), color=(0, 0, 0), width=2.0)
    page.draw_line(fitz.Point(cx1 + 15, cy1 - 10), fitz.Point(cx1 + 15, cy1 + 10), color=(0, 0, 0), width=2.0)
    page.insert_text(fitz.Point(col_x[1] + 15, cy1 + 5), "Válvula Compuerta Acero Forjado", fontsize=9, fontname="helv", color=(0, 0, 0))
    page.insert_text(fitz.Point(col_x[2] + 15, cy1 + 5), "VLV-GT-001 (ASME B16.34)", fontsize=9, fontname="helv", color=(0, 0, 0))

    # Fila 2: Válvula de Bola
    cy2 = (row_y[2] + row_y[3]) / 2.0
    cx2 = (col_x[0] + col_x[1]) / 2.0
    page.draw_circle(fitz.Point(cx2, cy2), 12.0, color=(0, 0, 0), width=2.0)
    page.draw_line(fitz.Point(cx2 - 18, cy2), fitz.Point(cx2 + 18, cy2), color=(0, 0, 0), width=1.5)
    page.insert_text(fitz.Point(col_x[1] + 15, cy2 + 5), "Válvula de Bola Paso Total", fontsize=9, fontname="helv", color=(0, 0, 0))
    page.insert_text(fitz.Point(col_x[2] + 15, cy2 + 5), "VLV-BL-002 (API 6D)", fontsize=9, fontname="helv", color=(0, 0, 0))

    # Fila 3: Válvula Check
    cy3 = (row_y[3] + row_y[4]) / 2.0
    cx3 = (col_x[0] + col_x[1]) / 2.0
    page.draw_rect(fitz.Rect(cx3 - 12, cy3 - 12, cx3 + 12, cy3 + 12), color=(0, 0, 0), width=1.8)
    page.draw_line(fitz.Point(cx3 - 8, cy3), fitz.Point(cx3 + 8, cy3), color=(0, 0, 0), width=1.5)
    page.insert_text(fitz.Point(col_x[1] + 15, cy3 + 5), "Válvula Check Clapeta Oscilante", fontsize=9, fontname="helv", color=(0, 0, 0))
    page.insert_text(fitz.Point(col_x[2] + 15, cy3 + 5), "VLV-CK-003 (BS 1868)", fontsize=9, fontname="helv", color=(0, 0, 0))

    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes, {
        "table_bbox_norm": [col_x[0] / 800.0, row_y[0] / 600.0, col_x[-1] / 800.0, row_y[-1] / 600.0],
        "col_x": col_x,
        "row_y": row_y
    }


def create_table_with_thick_grid_lines_pdf() -> tuple[bytes, dict]:
    """
    Tabla técnica con líneas divisorias gruesas (5 pt y 8 pt).
    Ninguna línea gruesa de la grilla debe ser tomada como símbolo.
    """
    doc = fitz.open()
    page = doc.new_page(width=800, height=600)

    col_x = [70, 250, 710]
    row_y = [90, 150, 230, 310]

    # Grilla exterior e interior gruesa (6 pt)
    for y in row_y:
        page.draw_line(fitz.Point(col_x[0], y), fitz.Point(col_x[-1], y), color=(0, 0, 0), width=6.0)
    for x in col_x:
        page.draw_line(fitz.Point(x, row_y[0]), fitz.Point(x, row_y[-1]), color=(0, 0, 0), width=6.0)

    page.insert_text(fitz.Point(col_x[0] + 20, row_y[0] + 35), "SÍMBOLO", fontsize=10, fontname="helv", color=(0, 0, 0))
    page.insert_text(fitz.Point(col_x[1] + 20, row_y[0] + 35), "DESCRIPCIÓN", fontsize=10, fontname="helv", color=(0, 0, 0))

    # Fila 1: Símbolo real concéntrico
    cy1 = (row_y[1] + row_y[2]) / 2.0
    cx1 = (col_x[0] + col_x[1]) / 2.0
    page.draw_circle(fitz.Point(cx1, cy1), 14.0, color=(0, 0, 0), width=2.0)
    page.draw_circle(fitz.Point(cx1, cy1), 6.0, color=(0, 0, 0), width=1.5)
    page.insert_text(fitz.Point(col_x[1] + 20, cy1 + 5), "Pulsador de Emergencia ESD", fontsize=9, fontname="helv", color=(0, 0, 0))

    # Fila 2: Celda vacía (solo líneas de grilla gruesas)
    page.insert_text(fitz.Point(col_x[1] + 20, (row_y[2] + row_y[3]) / 2.0 + 5), "Celda sin símbolo asociado", fontsize=9, fontname="helv", color=(0, 0, 0))

    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes, {
        "table_bbox_norm": [col_x[0] / 800.0, row_y[0] / 600.0, col_x[-1] / 800.0, row_y[-1] / 600.0]
    }


def create_table_with_waveform_figure_pdf() -> tuple[bytes, dict]:
    """
    Tabla con una celda que contiene un gráfico técnico / forma de onda oscilante.
    Debe clasificarse como 'figure' / 'table_graphic', NO promoverse como symbol_candidate.
    """
    doc = fitz.open()
    page = doc.new_page(width=800, height=600)

    col_x = [60, 320, 720]
    row_y = [80, 130, 220]

    for y in row_y:
        page.draw_line(fitz.Point(col_x[0], y), fitz.Point(col_x[-1], y), color=(0, 0, 0), width=1.0)
    for x in col_x:
        page.draw_line(fitz.Point(x, row_y[0]), fitz.Point(x, row_y[-1]), color=(0, 0, 0), width=1.0)

    page.insert_text(fitz.Point(col_x[0] + 15, row_y[0] + 30), "RESPUESTA DINÁMICA", fontsize=10, fontname="helv", color=(0, 0, 0))
    page.insert_text(fitz.Point(col_x[1] + 15, row_y[0] + 30), "CARACTERIZACIÓN", fontsize=10, fontname="helv", color=(0, 0, 0))

    # En la celda (Fila 1, Col 0), dibujar forma de onda oscilante continua
    cy = (row_y[1] + row_y[2]) / 2.0
    start_x = col_x[0] + 20
    end_x = col_x[1] - 20
    prev_pt = fitz.Point(start_x, cy)
    for step, x_cur in enumerate(range(int(start_x), int(end_x), 6)):
        y_cur = cy + 18.0 * math.sin(step * 0.75)
        cur_pt = fitz.Point(x_cur, y_cur)
        page.draw_line(prev_pt, cur_pt, color=(0, 0, 0), width=1.5)
        prev_pt = cur_pt

    page.insert_text(fitz.Point(col_x[1] + 15, cy + 5), "Curva de respuesta de transitorio de presión", fontsize=9, fontname="helv", color=(0, 0, 0))

    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes, {
        "table_bbox_norm": [col_x[0] / 800.0, row_y[0] / 600.0, col_x[-1] / 800.0, row_y[-1] / 600.0]
    }


def create_table_combined_spans_pdf() -> tuple[bytes, dict]:
    """
    Tabla donde una celda de encabezado combina 2 columnas (col_span=2, sin divisor vertical entre col 1 y 2).
    """
    doc = fitz.open()
    page = doc.new_page(width=800, height=600)

    col_x = [60, 200, 450, 720]
    row_y = [80, 130, 210, 290]

    # Líneas horizontales en todas las filas
    for y in row_y:
        page.draw_line(fitz.Point(col_x[0], y), fitz.Point(col_x[-1], y), color=(0, 0, 0), width=1.0)

    # Líneas verticales exteriores
    page.draw_line(fitz.Point(col_x[0], row_y[0]), fitz.Point(col_x[0], row_y[-1]), color=(0, 0, 0), width=1.0)
    page.draw_line(fitz.Point(col_x[-1], row_y[0]), fitz.Point(col_x[-1], row_y[-1]), color=(0, 0, 0), width=1.0)

    # Línea vertical 1 (col_x[1]): completa
    page.draw_line(fitz.Point(col_x[1], row_y[0]), fitz.Point(col_x[1], row_y[-1]), color=(0, 0, 0), width=1.0)

    # Línea vertical 2 (col_x[2]): SOLO existe en filas 1 y 2 (ausente en fila 0 -> col_span=2 en encabezado)
    page.draw_line(fitz.Point(col_x[2], row_y[1]), fitz.Point(col_x[2], row_y[-1]), color=(0, 0, 0), width=1.0)

    # Fila 0: Header combinado
    page.insert_text(fitz.Point(col_x[0] + 15, row_y[0] + 30), "ICONO", fontsize=9, fontname="helv", color=(0, 0, 0))
    page.insert_text(fitz.Point(col_x[1] + 60, row_y[0] + 30), "ESPECIFICACIÓN COMBINADA (COL SPAN 2)", fontsize=9, fontname="helv", color=(0, 0, 0))

    # Fila 1: Símbolo en col 0
    cy1 = (row_y[1] + row_y[2]) / 2.0
    cx1 = (col_x[0] + col_x[1]) / 2.0
    page.draw_circle(fitz.Point(cx1, cy1), 12.0, color=(0, 0, 0), width=2.0)
    page.insert_text(fitz.Point(col_x[1] + 15, cy1 + 5), "Sensor de Nivel", fontsize=9, fontname="helv", color=(0, 0, 0))
    page.insert_text(fitz.Point(col_x[2] + 15, cy1 + 5), "LT-100", fontsize=9, fontname="helv", color=(0, 0, 0))

    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes, {
        "table_bbox_norm": [col_x[0] / 800.0, row_y[0] / 600.0, col_x[-1] / 800.0, row_y[-1] / 600.0]
    }


def _extract_page_words_as_texts(page):
    words = page.get_text("words")
    pw = page.rect.width
    ph = page.rect.height
    texts = []
    for w in words:
        tx0, ty0, tx1, ty1, text = w[0], w[1], w[2], w[3], w[4]
        if text.strip():
            texts.append({
                "text": text.strip(),
                "clean_text": text.strip(),
                "bbox_normalized": [round(tx0 / pw, 4), round(ty0 / ph, 4), round(tx1 / pw, 4), round(ty1 / ph, 4)],
                "confidence": 0.95,
                "id": str(uuid.uuid4())
            })
    return texts


# =============================================================================
# TEST SUITE: GRILLA FÍSICA Y RECORTE PRECISO (3 MM)
# =============================================================================

class TestTablePhysicalGridAndSymbolCrop:

    def test_condition_1_physical_grid_detection_and_boundaries(self, tmp_path):
        """
        Condición 1:
        Debe detectar la grilla física vectorial y registrar:
        - grid_source = "vector"
        - physical_grid_detected = True
        - grid_confidence >= 0.90
        - x_boundaries e y_boundaries con los límites exactos de filas y columnas.
        """
        pdf_bytes, meta = create_table_with_physical_grid_and_symbols_pdf()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc[0]

        texts = _extract_page_words_as_texts(page)
        extractor = TableExtractor(width_px=800, height_px=600)
        table = extractor.extract_from_region(
            region_bbox_norm=meta["table_bbox_norm"],
            texts=texts,
            page=page,
            doc_uid="test_phys_grid",
            crops_dir=str(tmp_path / "crops")
        )
        doc.close()

        assert table is not None
        assert table.physical_grid_detected is True
        assert table.grid_source == "vector"
        assert table.grid_confidence >= 0.90

        # Verificar x_boundaries e y_boundaries
        assert len(table.x_boundaries) == 4  # 3 columnas -> 4 divisores
        assert len(table.y_boundaries) == 5  # 4 filas -> 5 divisores
        assert table.row_count == 4
        assert table.column_count == 3

        # Verificar que los límites correspondan a las coordenadas físicas
        assert abs(table.x_boundaries[0] - 60 / 800.0) < 0.015
        assert abs(table.x_boundaries[-1] - 740 / 800.0) < 0.015
        assert abs(table.y_boundaries[0] - 80 / 600.0) < 0.015
        assert abs(table.y_boundaries[-1] - 370 / 600.0) < 0.015

        # Todos los símbolos generados deben heredar los metadatos de grilla
        assert len(table.extracted_symbols) == 3
        for sym in table.extracted_symbols:
            assert sym.grid_source == "vector"
            assert sym.physical_grid_detected is True
            assert sym.grid_confidence >= 0.90
            assert sym.x_boundaries == table.x_boundaries
            assert sym.y_boundaries == table.y_boundaries
            assert sym.table_bbox == table.bbox_normalized

    def test_condition_2_logical_alignment_fallback_when_no_physical_grid(self, tmp_path):
        """
        Condición 2:
        Fallback por alineamiento de texto solo si no existe grilla física.
        Debe marcar grid_source = 'logical_alignment' y physical_grid_detected = False.
        Si la confianza es baja (<0.60), requiere revisión humana.
        """
        doc = fitz.open()
        page = doc.new_page(width=800, height=600)
        # Solo texto sin ninguna línea vectorial ni raster
        page.insert_text(fitz.Point(100, 100), "SÍMBOLO", fontsize=10)
        page.insert_text(fitz.Point(300, 100), "DESCRIPCIÓN", fontsize=10)
        page.insert_text(fitz.Point(100, 180), "VALV-01", fontsize=9)
        page.insert_text(fitz.Point(300, 180), "Válvula de alivio", fontsize=9)
        pdf_bytes = doc.write()
        doc.close()

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc[0]
        texts = _extract_page_words_as_texts(page)
        extractor = TableExtractor(width_px=800, height_px=600)
        table = extractor.extract_from_region(
            region_bbox_norm=[0.1, 0.1, 0.7, 0.4],
            texts=texts,
            page=page,
            drawings=[], # Sin dibujos vectoriales
            doc_uid="test_logical"
        )
        doc.close()

        assert table is not None
        assert table.physical_grid_detected is False
        assert table.grid_source == "logical_alignment"
        assert table.grid_confidence <= 0.65

    def test_condition_3_and_4_symbol_crop_3mm_strictly_bounded_by_cell_bbox(self, tmp_path):
        """
        Condición 3 & 4:
        - Líneas de grilla y bordes no forman parte de inner_drawing_bbox.
        - symbol_crop_bbox = inner_drawing_bbox + 3 mm (8.50 pt) acotado estrictamente a cell_bbox.
        """
        pdf_bytes, meta = create_table_with_physical_grid_and_symbols_pdf()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc[0]

        texts = _extract_page_words_as_texts(page)
        extractor = TableExtractor(width_px=800, height_px=600)
        crops_dir = tmp_path / "crops_3mm"
        table = extractor.extract_from_region(
            region_bbox_norm=meta["table_bbox_norm"],
            texts=texts,
            page=page,
            doc_uid="test_crop_3mm",
            crops_dir=str(crops_dir)
        )
        doc.close()

        assert table is not None
        assert len(table.extracted_symbols) == 3

        # 3 mm en pt = 3 * 72 / 25.4 = 8.5039 pt
        # En coordenadas normalizadas: dx_3mm = 8.5039 / 800 = 0.01063, dy_3mm = 8.5039 / 600 = 0.01417
        for sym in table.extracted_symbols:
            assert sym.inner_drawing_bbox is not None
            assert sym.symbol_crop_bbox is not None
            assert sym.cell_bbox is not None
            assert sym.crop_margin_mm == 3.0

            c_x0, c_y0, c_x1, c_y1 = sym.cell_bbox
            i_x0, i_y0, i_x1, i_y1 = sym.inner_drawing_bbox
            s_x0, s_y0, s_x1, s_y1 = sym.symbol_crop_bbox

            # inner_drawing_bbox debe ser estrictamente menor que cell_bbox (no incluye bordes de celda)
            assert i_x0 > c_x0 + 0.005, "inner_drawing_bbox no debe incluir el borde izquierdo de celda"
            assert i_x1 < c_x1 - 0.005, "inner_drawing_bbox no debe incluir el borde derecho de celda"
            assert i_y0 > c_y0 + 0.005, "inner_drawing_bbox no debe incluir el borde superior de celda"
            assert i_y1 < c_y1 - 0.005, "inner_drawing_bbox no debe incluir el borde inferior de celda"

            # symbol_crop_bbox debe expandir inner_drawing_bbox en aproximadamente 3 mm
            assert s_x0 <= i_x0
            assert s_y0 <= i_y0
            assert s_x1 >= i_x1
            assert s_y1 >= i_y1

            # symbol_crop_bbox debe quedar estrictamente limitado al interior de cell_bbox
            assert s_x0 >= c_x0 - 0.0001, "symbol_crop_bbox no debe salir de cell_bbox por la izquierda"
            assert s_y0 >= c_y0 - 0.0001, "symbol_crop_bbox no debe salir de cell_bbox por arriba"
            assert s_x1 <= c_x1 + 0.0001, "symbol_crop_bbox no debe salir de cell_bbox por la derecha"
            assert s_y1 <= c_y1 + 0.0001, "symbol_crop_bbox no debe salir de cell_bbox por abajo"

            # El bbox del símbolo candidato debe ser exactamente symbol_crop_bbox (no la celda completa)
            assert sym.bbox_normalized == sym.symbol_crop_bbox
            assert sym.bbox_normalized != sym.cell_bbox

            # El archivo físico de imagen de recorte debe existir en disco
            crop_file = crops_dir / Path(sym.crop_image_path).name
            assert crop_file.exists(), f"El recorte {crop_file} no existe en disco"
            assert crop_file.stat().st_size > 50

    def test_condition_5_text_only_table_generates_zero_symbols_visible_in_tables(self, tmp_path):
        """
        Condición 5:
        Las tablas sin geometría simbólica válida deben quedar visibles en Tablas y generar cero símbolos.
        """
        doc = fitz.open()
        page = doc.new_page(width=800, height=600)
        col_x = [60, 220, 500, 720]
        row_y = [80, 120, 160, 200]
        for y in row_y:
            page.draw_line(fitz.Point(col_x[0], y), fitz.Point(col_x[-1], y), color=(0, 0, 0), width=1.0)
        for x in col_x:
            page.draw_line(fitz.Point(x, row_y[0]), fitz.Point(x, row_y[-1]), color=(0, 0, 0), width=1.0)

        page.insert_text(fitz.Point(col_x[0] + 10, row_y[0] + 25), "ITEM", fontsize=9)
        page.insert_text(fitz.Point(col_x[1] + 10, row_y[0] + 25), "DESCRIPCIÓN", fontsize=9)
        page.insert_text(fitz.Point(col_x[2] + 10, row_y[0] + 25), "CANTIDAD", fontsize=9)

        page.insert_text(fitz.Point(col_x[0] + 10, row_y[1] + 25), "1", fontsize=9)
        page.insert_text(fitz.Point(col_x[1] + 10, row_y[1] + 25), "Tubería Acero Carbón 4 pulg", fontsize=9)
        page.insert_text(fitz.Point(col_x[2] + 10, row_y[1] + 25), "120 m", fontsize=9)

        page.insert_text(fitz.Point(col_x[0] + 10, row_y[2] + 25), "2", fontsize=9)
        page.insert_text(fitz.Point(col_x[1] + 10, row_y[2] + 25), "Brida ANSI 150 RF", fontsize=9)
        page.insert_text(fitz.Point(col_x[2] + 10, row_y[2] + 25), "24 un", fontsize=9)

        pdf_bytes = doc.write()
        doc.close()

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc[0]
        texts = _extract_page_words_as_texts(page)
        extractor = TableExtractor(width_px=800, height_px=600)
        table = extractor.extract_from_region(
            region_bbox_norm=[col_x[0]/800.0, row_y[0]/600.0, col_x[-1]/800.0, row_y[-1]/600.0],
            texts=texts,
            page=page,
            doc_uid="test_text_table"
        )
        doc.close()

        assert table is not None
        assert table.has_symbols is False
        assert len(table.extracted_symbols) == 0
        assert table.row_count == 3
        assert table.column_count == 3
        assert table.raw_structure["symbol_cells"] == 0
        assert table.raw_structure["non_empty_cells"] > 0

    def test_condition_6_and_7_waveform_classified_as_figure_not_symbol(self, tmp_path):
        """
        Condición 6 & 7:
        Forma de onda / gráfico técnico oscilante dentro de una celda se clasifica como
        graphic_classification = 'figure', no genera símbolo y se envía a diagram_candidate / Figure.
        """
        pdf_bytes, meta = create_table_with_waveform_figure_pdf()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc[0]

        texts = _extract_page_words_as_texts(page)
        extractor = TableExtractor(width_px=800, height_px=600)
        crops_dir = tmp_path / "crops_fig"
        table = extractor.extract_from_region(
            region_bbox_norm=meta["table_bbox_norm"],
            texts=texts,
            page=page,
            doc_uid="test_waveform",
            crops_dir=str(crops_dir)
        )
        doc.close()

        assert table is not None
        # La tabla NO debe promover la forma de onda como símbolo canónico
        assert table.has_symbols is False
        assert len(table.extracted_symbols) == 0

        # La celda de la forma de onda debe quedar clasificada como figure
        wave_cell = next(c for c in table.cells if c.row_index == 1 and c.column_index == 0)
        assert wave_cell.graphic_classification == "figure"
        assert wave_cell.has_symbol is False
        assert wave_cell.cell_type == "figure"

    def test_condition_thick_grid_lines_generate_zero_spurious_symbols(self, tmp_path):
        """
        Condición de robustez:
        Líneas divisorias de grilla gruesas (hasta 6 pt) son filtradas y no producen símbolos falsos.
        """
        pdf_bytes, meta = create_table_with_thick_grid_lines_pdf()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc[0]

        texts = _extract_page_words_as_texts(page)
        extractor = TableExtractor(width_px=800, height_px=600)
        table = extractor.extract_from_region(
            region_bbox_norm=meta["table_bbox_norm"],
            texts=texts,
            page=page,
            doc_uid="test_thick_grid",
            crops_dir=str(tmp_path / "crops_thick")
        )
        doc.close()

        assert table is not None
        assert table.physical_grid_detected is True
        # Solo debe haber 1 símbolo real (el pulsador ESD en Fila 1)
        # La celda vacía con bordes gruesos de 6 pt NO debe generar símbolo
        assert len(table.extracted_symbols) == 1
        assert "ESD" in table.extracted_symbols[0].symbol_name or "Pulsador" in table.extracted_symbols[0].symbol_name

        empty_cell = next(c for c in table.cells if c.row_index == 2 and c.column_index == 0)
        assert empty_cell.has_symbol is False
        assert empty_cell.geometric_evidence is False

    def test_combined_cell_span_detection(self, tmp_path):
        """
        Verifica detección de col_span=2 cuando falta un divisor vertical interior en el encabezado.
        """
        pdf_bytes, meta = create_table_combined_spans_pdf()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc[0]

        texts = _extract_page_words_as_texts(page)
        extractor = TableExtractor(width_px=800, height_px=600)
        table = extractor.extract_from_region(
            region_bbox_norm=meta["table_bbox_norm"],
            texts=texts,
            page=page,
            doc_uid="test_spans",
            crops_dir=str(tmp_path / "crops_span")
        )
        doc.close()

        assert table is not None
        # En la Fila 0, Col 1 falta el divisor hacia Col 2 -> col_span = 2
        header_span_cell = next(c for c in table.cells if c.row_index == 0 and c.column_index == 1)
        assert header_span_cell.col_span == 2
