import os
import glob
import pytest
import pymupdf

from app.services.tables.extractor import TableExtractor


def _find_isa_pdf() -> str:
    """Busca el PDF real de regresión ISA_5.1-2009.pdf en el volumen de intake_sources o fixtures."""
    candidates = glob.glob("data/intake_sources/**/170b22889574_ISA_5.1-2009.pdf", recursive=True)
    if not candidates:
        candidates = glob.glob("data/**/ISA_5.1-2009.pdf", recursive=True)
    if not candidates:
        candidates = glob.glob("tests/**/ISA_5.1-2009.pdf", recursive=True)
    if not candidates:
        pytest.skip("PDF ISA_5.1-2009.pdf no encontrado en el entorno.")
    return candidates[0]


@pytest.mark.integration
def test_isa_page66_waveform_classified_as_figure_and_emits_zero_symbols():
    """
    Regresión crítica Página 66 (Índice 65) de ISA_5.1-2009:
    - La grilla física debe ser detectada desde vectores (grid_source='vector', physical_grid_detected=True).
    - Los gráficos de forma de onda (timing diagrams) deben clasificarse como 'figure' o 'table_graphic'.
    - emit_symbol_candidate / has_symbol debe ser estrictamente False para la forma de onda.
    - CERO símbolos deben originarse desde la región o celdas de forma de onda.
    - Las celdas con matriz lógica de verdad (A, B, C, X, O, 0, 1) son texto y generan CERO símbolos.
    - No depende de IDs, conteos rígidos de paths ni coordenadas frágiles.
    """
    pdf_path = _find_isa_pdf()
    doc = pymupdf.open(pdf_path)
    assert len(doc) >= 66, f"El documento debe tener al menos 66 páginas, tiene {len(doc)}"

    page66 = doc[65]
    pw, ph = int(page66.rect.width), int(page66.rect.height)
    extractor = TableExtractor(pw, ph)

    # Coordenadas generales de la macro-región de la tabla en página 66
    rx0, ry0, rx1, ry1 = 72.0 / pw, 72.0 / ph, 540.0 / pw, 720.0 / ph
    raw_blocks = page66.get_text("blocks")
    texts = [
        {"text": b[4].strip(), "bbox_normalized": [b[0] / pw, b[1] / ph, b[2] / pw, b[3] / ph]}
        for b in raw_blocks
        if b[4].strip()
    ]

    tbl = extractor.extract_from_region([rx0, ry0, rx1, ry1], texts, page=page66)
    assert tbl is not None, "Debe extraer la tabla de la página 66"

    # 1. Verificación de Grilla Vectorial Estructural
    assert tbl.grid_source == "vector", f"grid_source debe ser 'vector', obtenido '{tbl.grid_source}'"
    assert tbl.physical_grid_detected is True, "physical_grid_detected debe ser True"

    # 2. Localizar celdas que contienen el gráfico de forma de onda (waveform / timing diagram)
    waveform_cells = [
        c for c in tbl.cells
        if any(marker in (c.text or "") for marker in ["1\n0", "t 1", "X O t", "X O 1"])
        or c.graphic_classification in ["figure", "table_graphic"]
        or c.content_class in ["figure", "table_graphic"]
    ]
    assert len(waveform_cells) >= 1, "Debe detectar al menos una celda que aloje la forma de onda técnica"

    for w_cell in waveform_cells:
        # Clasificación estricta: figura o gráfico tabular
        assert w_cell.graphic_classification in ["figure", "table_graphic"], (
            f"Forma de onda en fila {w_cell.row_index}, col {w_cell.column_index} no fue clasificada como figure/table_graphic: {w_cell.graphic_classification}"
        )
        assert w_cell.content_class in ["figure", "table_graphic"], (
            f"content_class de forma de onda debe ser figure/table_graphic, es: {w_cell.content_class}"
        )
        # La forma de onda nunca emite candidato a símbolo
        assert w_cell.has_symbol is False, (
            f"has_symbol debe ser False para forma de onda en fila {w_cell.row_index}, col {w_cell.column_index}"
        )

    # 3. Cero símbolos originados en las celdas de forma de onda
    extracted_syms = tbl.extracted_symbols or []
    waveform_cell_coords = {(c.row_index, c.column_index) for c in waveform_cells}
    for sym in extracted_syms:
        sym_coord = (sym.row_index, sym.col_index)
        assert sym_coord not in waveform_cell_coords, (
            f"Se emitió un símbolo incorrectamente desde la celda de forma de onda {sym_coord}: {sym.symbol_name}"
        )
        assert sym.graphic_classification not in ["figure", "table_graphic"], (
            f"Símbolo {sym.symbol_name} tiene clasificación prohibida {sym.graphic_classification}"
        )
        assert getattr(sym, "content_class", None) not in ["figure", "table_graphic", "text_only"], (
            f"Símbolo {sym.symbol_name} tiene content_class prohibido {getattr(sym, 'content_class', None)}"
        )

    # 4. Verificación de Matriz Lógica de Verdad (A/B/C/X/O y 0/1): NO generan símbolos
    truth_matrix_cells = [
        c for c in tbl.cells
        if ("A \nB \nC" in (c.text or "") or "A\nB\nC" in (c.text or ""))
        and any(val in (c.text or "") for val in ["1 \n0 \n0", "0 \n0 \n0", "X \nO \n1"])
    ]
    assert len(truth_matrix_cells) >= 1, "Deben identificarse celdas de matriz lógica de verdad en pág 66"

    for tm_cell in truth_matrix_cells:
        assert tm_cell.has_symbol is False, (
            f"Celda de matriz de verdad fila {tm_cell.row_index}, col {tm_cell.column_index} no debe tener has_symbol=True"
        )
        assert tm_cell.content_class == "text_only", (
            f"Celda de matriz de verdad debe ser text_only, es {tm_cell.content_class}"
        )
        assert tm_cell.graphic_classification == "not_symbol", (
            f"Celda de matriz de verdad no debe clasificarse como símbolo, es {tm_cell.graphic_classification}"
        )

    doc.close()


@pytest.mark.integration
def test_real_discrete_symbols_pass_geometric_gate_positive_test():
    """
    Prueba positiva con leyenda técnica real distinta (Página 48, Tabla 5.4.1 de ISA_5.1-2009):
    - Extrae válvulas y dampers reales donde los trazos discretos cerrados superan la puerta geométrica.
    - Verifica:
      * has_symbols=True
      * graphic_classification == 'symbol'
      * content_class in {'symbol_only', 'mixed'}
      * geometric_confidence >= 0.60
      * inner_drawing_bbox y symbol_crop_bbox presentes
      * Recortes visuales generados
    """
    pdf_path = _find_isa_pdf()
    doc = pymupdf.open(pdf_path)
    assert len(doc) >= 48, "El PDF debe tener al menos 48 páginas"

    page48 = doc[47]
    pw, ph = int(page48.rect.width), int(page48.rect.height)
    extractor = TableExtractor(pw, ph)

    rx0, ry0, rx1, ry1 = 72.0 / pw, 72.0 / ph, 540.0 / pw, 720.0 / ph
    raw_blocks = page48.get_text("blocks")
    texts = [
        {"text": b[4].strip(), "bbox_normalized": [b[0] / pw, b[1] / ph, b[2] / pw, b[3] / ph]}
        for b in raw_blocks
        if b[4].strip()
    ]

    tbl = extractor.extract_from_region([rx0, ry0, rx1, ry1], texts, page=page48)
    assert tbl is not None, "Debe extraer la tabla de simbología de la página 48"
    assert tbl.has_symbols is True, "Tabla 5.4.1 contiene simbología real y debe tener has_symbols=True"
    assert len(tbl.extracted_symbols) >= 3, (
        f"Tabla 5.4.1 debe extraer al menos 3 símbolos de válvulas/dampers, extrajo {len(tbl.extracted_symbols)}"
    )

    for sym in tbl.extracted_symbols:
        assert sym.graphic_classification == "symbol", (
            f"Símbolo {sym.symbol_name} debe tener graphic_classification='symbol', tiene '{sym.graphic_classification}'"
        )
        assert sym.content_class in ["symbol_only", "mixed"], (
            f"Símbolo {sym.symbol_name} debe ser 'symbol_only' o 'mixed', es '{sym.content_class}'"
        )
        assert sym.geometric_confidence >= 0.60, (
            f"Símbolo {sym.symbol_name} debe tener geometric_confidence >= 0.60, tiene {sym.geometric_confidence}"
        )
        assert sym.inner_drawing_bbox is not None and len(sym.inner_drawing_bbox) == 4, (
            f"Símbolo {sym.symbol_name} debe tener inner_drawing_bbox válido"
        )
        assert sym.cell_bbox is not None and len(sym.cell_bbox) == 4, (
            f"Símbolo {sym.symbol_name} debe tener cell_bbox válido"
        )
        assert sym.symbol_crop_bbox is not None and len(sym.symbol_crop_bbox) == 4, (
            f"Símbolo {sym.symbol_name} debe tener symbol_crop_bbox válido"
        )

    doc.close()
