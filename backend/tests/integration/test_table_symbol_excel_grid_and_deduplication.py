import os
import sys
import uuid
import tempfile
import pytest
import fitz  # PyMuPDF
from pathlib import Path
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models.core import Organization, Project
from app.db.models.intake_extractions import (
    SourceExtraction, ExtractedItem, StructuredSymbol
)
from app.services.tables.extractor import TableExtractor, ExtractedCellDTO
from app.services.extraction.candidate_generator_service import CandidateGeneratorService
from app.services.extraction.candidate_enrichment_service import CandidateEnrichmentService


def create_row_major_legend_pdf() -> tuple[bytes, dict]:
    """
    Crea un PDF con una tabla tipo Excel con orientación ROW_MAJOR:
    - Columna 0: Símbolos gráficos B/N (Puerta, Extintor, Pulsador)
    - Columna 1: Nombre / Denominación
    - Columna 2: Norma técnica
    """
    doc = fitz.open()
    page = doc.new_page(width=800, height=600)

    # Coordenadas de la tabla
    col_x = [50, 180, 520, 750]  # 3 columnas
    row_y = [70, 110, 180, 250, 320]  # 4 filas (fila 0 = encabezado, filas 1..3 = datos)

    # Dibujar cuadrícula
    for y in row_y:
        page.draw_line(fitz.Point(col_x[0], y), fitz.Point(col_x[-1], y), color=(0, 0, 0), width=1.0)
    for x in col_x:
        page.draw_line(fitz.Point(x, row_y[0]), fitz.Point(x, row_y[-1]), color=(0, 0, 0), width=1.0)

    # Encabezados
    page.insert_text(fitz.Point(col_x[0] + 20, row_y[0] + 25), "SÍMBOLO", fontsize=10, fontname="helv", color=(0, 0, 0))
    page.insert_text(fitz.Point(col_x[1] + 20, row_y[0] + 25), "DENOMINACIÓN", fontsize=10, fontname="helv", color=(0, 0, 0))
    page.insert_text(fitz.Point(col_x[2] + 20, row_y[0] + 25), "NORMA", fontsize=10, fontname="helv", color=(0, 0, 0))

    # Filas de datos
    specs = [
        {"name": "Puerta Cortafuego F-60", "norm": "OGUC Art. 4.3.4", "draw": lambda p, cx, cy: (
            p.draw_rect(fitz.Rect(cx - 15, cy - 15, cx + 15, cy + 15), color=(0, 0, 0), width=1.5),
            p.draw_line(fitz.Point(cx - 15, cy + 15), fitz.Point(cx + 8, cy - 8), color=(0, 0, 0), width=2.0)
        )},
        {"name": "Extintor PQS 10kg", "norm": "DS 594", "draw": lambda p, cx, cy: (
            p.draw_rect(fitz.Rect(cx - 10, cy - 12, cx + 10, cy + 16), color=(0, 0, 0), fill=(0.1, 0.1, 0.1), width=1.5),
            p.draw_line(fitz.Point(cx, cy - 12), fitz.Point(cx, cy - 20), color=(0, 0, 0), width=2.0)
        )},
        {"name": "Pulsador de Alarma Manual", "norm": "NFPA 72", "draw": lambda p, cx, cy: (
            p.draw_circle(fitz.Point(cx, cy), 16, color=(0, 0, 0), width=1.5),
            p.draw_circle(fitz.Point(cx, cy), 6, color=(0, 0, 0), fill=(0, 0, 0))
        )},
    ]

    for i, spec in enumerate(specs):
        r = i + 1
        cy = (row_y[r] + row_y[r + 1]) / 2
        cx = (col_x[0] + col_x[1]) / 2
        spec["draw"](page, cx, cy)
        page.insert_text(fitz.Point(col_x[1] + 15, cy + 4), spec["name"], fontsize=9, fontname="helv", color=(0, 0, 0))
        page.insert_text(fitz.Point(col_x[2] + 15, cy + 4), spec["norm"], fontsize=9, fontname="helv", color=(0, 0, 0))

    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes, {
        "table_bbox_norm": [col_x[0] / 800.0, row_y[0] / 600.0, col_x[-1] / 800.0, row_y[-1] / 600.0],
        "symbols_count": len(specs)
    }


def create_col_major_legend_pdf() -> tuple[bytes, dict]:
    """
    Crea un PDF con una tabla tipo Excel con orientación COL_MAJOR:
    - Fila 0: Encabezados de tipos de válvula
    - Fila 1: Símbolos gráficos en cada columna (Col 0, Col 1, Col 2)
    - Fila 2: Descripción técnica debajo de cada símbolo
    """
    doc = fitz.open()
    page = doc.new_page(width=800, height=600)

    col_x = [60, 280, 500, 720]  # 3 columnas
    row_y = [80, 120, 200, 260]  # 3 filas: 0=Header, 1=Símbolo, 2=Descripción abajo

    # Dibujar cuadrícula
    for y in row_y:
        page.draw_line(fitz.Point(col_x[0], y), fitz.Point(col_x[-1], y), color=(0, 0, 0), width=1.0)
    for x in col_x:
        page.draw_line(fitz.Point(x, row_y[0]), fitz.Point(x, row_y[-1]), color=(0, 0, 0), width=1.0)

    # Símbolos en Fila 1 (horizontal en múltiples columnas)
    symbols = [
        {"header": "TIPO A", "name": "Valvula Compuerta", "draw": lambda p, cx, cy: (
            p.draw_line(fitz.Point(cx - 15, cy - 10), fitz.Point(cx + 15, cy + 10), color=(0, 0, 0), width=2.0),
            p.draw_line(fitz.Point(cx - 15, cy + 10), fitz.Point(cx + 15, cy - 10), color=(0, 0, 0), width=2.0),
            p.draw_line(fitz.Point(cx, cy), fitz.Point(cx, cy - 15), color=(0, 0, 0), width=1.5)
        )},
        {"header": "TIPO B", "name": "Valvula Globo", "draw": lambda p, cx, cy: (
            p.draw_circle(fitz.Point(cx, cy), 12, color=(0, 0, 0), width=1.5),
            p.draw_line(fitz.Point(cx - 15, cy), fitz.Point(cx + 15, cy), color=(0, 0, 0), width=2.0)
        )},
        {"header": "TIPO C", "name": "Valvula Check", "draw": lambda p, cx, cy: (
            p.draw_rect(fitz.Rect(cx - 12, cy - 12, cx + 12, cy + 12), color=(0, 0, 0), width=1.5),
            p.draw_line(fitz.Point(cx - 12, cy), fitz.Point(cx + 12, cy), color=(0, 0, 0), width=2.0)
        )},
    ]

    for col_idx, sym in enumerate(symbols):
        cx = (col_x[col_idx] + col_x[col_idx + 1]) / 2

        # Fila 0: Header
        page.insert_text(fitz.Point(cx - 30, row_y[0] + 25), sym["header"], fontsize=10, fontname="helv", color=(0, 0, 0))

        # Fila 1: Símbolo
        cy1 = (row_y[1] + row_y[2]) / 2
        sym["draw"](page, cx, cy1)

        # Fila 2: Descripción técnica debajo
        cy2 = (row_y[2] + row_y[3]) / 2
        page.insert_text(fitz.Point(cx - 40, cy2 + 4), sym["name"], fontsize=9, fontname="helv", color=(0, 0, 0))

    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes, {
        "table_bbox_norm": [col_x[0] / 800.0, row_y[0] / 600.0, col_x[-1] / 800.0, row_y[-1] / 600.0],
        "symbols_count": len(symbols)
    }


def create_text_only_table_pdf() -> tuple[bytes, dict]:
    """
    Crea un PDF con una tabla puramente documental (solo texto, 0 dibujos en celdas).
    Esta tabla DEBE SER DESCARTADA del pipeline de simbología.
    """
    doc = fitz.open()
    page = doc.new_page(width=800, height=600)

    col_x = [60, 200, 450, 720]
    row_y = [80, 120, 160, 200, 240]

    for y in row_y:
        page.draw_line(fitz.Point(col_x[0], y), fitz.Point(col_x[-1], y), color=(0, 0, 0), width=1.0)
    for x in col_x:
        page.draw_line(fitz.Point(x, row_y[0]), fitz.Point(x, row_y[-1]), color=(0, 0, 0), width=1.0)

    headers = ["CÓDIGO", "DESCRIPCIÓN DEL MATERIAL", "PROVEEDOR"]
    for i, h in enumerate(headers):
        page.insert_text(fitz.Point(col_x[i] + 15, row_y[0] + 25), h, fontsize=9, fontname="helv", color=(0, 0, 0))

    data_rows = [
        ["MAT-01", "Tubo PVC Hidráulico Clase 10 110mm", "Vinilit Chile"],
        ["MAT-02", "Codo Acero Galvanizado 90° 2 pulg", "Tigre S.A."],
        ["MAT-03", "Válvula Mariposa Hierro Dúctil", "Valvulas del Sur"],
    ]
    for r_idx, row in enumerate(data_rows):
        y = row_y[r_idx + 1] + 25
        for c_idx, val in enumerate(row):
            page.insert_text(fitz.Point(col_x[c_idx] + 15, y), val, fontsize=8.5, fontname="helv", color=(0, 0, 0))

    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes, {
        "table_bbox_norm": [col_x[0] / 800.0, row_y[0] / 600.0, col_x[-1] / 800.0, row_y[-1] / 600.0]
    }


def create_multipage_duplicate_symbol_pdf() -> bytes:
    """
    Crea un PDF de 2 páginas con el mismo símbolo (Extintor PQS 10kg) en ambas páginas.
    Esto permite probar la deduplicación canónica y la lista de ocurrencias multipágina.
    """
    doc = fitz.open()

    for page_num in range(2):
        page = doc.new_page(width=800, height=600)
        col_x = [50, 180, 520, 750]
        row_y = [70, 110, 180]

        for y in row_y:
            page.draw_line(fitz.Point(col_x[0], y), fitz.Point(col_x[-1], y), color=(0, 0, 0), width=1.0)
        for x in col_x:
            page.draw_line(fitz.Point(x, row_y[0]), fitz.Point(x, row_y[-1]), color=(0, 0, 0), width=1.0)

        page.insert_text(fitz.Point(col_x[0] + 20, row_y[0] + 25), "SÍMBOLO", fontsize=10, fontname="helv", color=(0, 0, 0))
        page.insert_text(fitz.Point(col_x[1] + 20, row_y[0] + 25), "DENOMINACIÓN", fontsize=10, fontname="helv", color=(0, 0, 0))
        page.insert_text(fitz.Point(col_x[2] + 20, row_y[0] + 25), "NORMA", fontsize=10, fontname="helv", color=(0, 0, 0))

        # Dibujar Extintor PQS
        cy = (row_y[1] + row_y[2]) / 2
        cx = (col_x[0] + col_x[1]) / 2
        page.draw_rect(fitz.Rect(cx - 10, cy - 12, cx + 10, cy + 16), color=(0, 0, 0), fill=(0.1, 0.1, 0.1), width=1.5)
        page.draw_line(fitz.Point(cx, cy - 12), fitz.Point(cx, cy - 20), color=(0, 0, 0), width=2.0)

        page.insert_text(fitz.Point(col_x[1] + 15, cy + 4), "Extintor PQS 10kg ABC", fontsize=9, fontname="helv", color=(0, 0, 0))
        page.insert_text(fitz.Point(col_x[2] + 15, cy + 4), f"NCh 1433 - Pág {page_num + 1}", fontsize=9, fontname="helv", color=(0, 0, 0))

    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes


def _extract_page_words_as_texts(page):
    """Extrae palabras de página PyMuPDF como lista de diccionarios de texto."""
    raw_words = page.get_text("words")
    texts = []
    pw, ph = page.rect.width, page.rect.height
    for w in raw_words:
        texts.append({
            "text": w[4],
            "clean_text": w[4].strip(),
            "bbox_normalized": [w[0] / pw, w[1] / ph, w[2] / pw, w[3] / ph],
            "id": str(uuid.uuid4())
        })
    return texts


def test_condition_1_and_3_excel_grid_decomposition_and_orientation_row_major(tmp_path):
    """
    Valida:
    - Condición 1: Registro de orientation, orientation_confidence, orientation_reason.
    - Condición 3: Recorte principal = celda completa; inner_drawing_bbox como metadato.
    - Descomposición tipo Excel: filas, columnas, celdas, indices row/col.
    """
    pdf_bytes, meta = create_row_major_legend_pdf()
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[0]

    texts = _extract_page_words_as_texts(page)
    extractor = TableExtractor(width_px=int(page.rect.width), height_px=int(page.rect.height))
    extracted_table = extractor.extract_from_region(
        region_bbox_norm=meta["table_bbox_norm"],
        texts=texts,
        symbols=[],
        page=page,
        doc_uid="test_row_major",
        crops_dir=str(tmp_path / "crops_row")
    )
    doc.close()

    # 1. Validación de tabla detectada
    assert extracted_table is not None
    assert extracted_table.has_symbols is True
    assert extracted_table.row_count == 4
    assert extracted_table.column_count == 3
    assert len(extracted_table.cells) == 12

    # 2. Condición 1: Orientación obligatoria
    assert extracted_table.reading_orientation == "row_major"
    assert extracted_table.orientation_confidence >= 0.70
    assert extracted_table.orientation_reason is not None
    assert len(extracted_table.orientation_reason) > 5
    print(f"\n[Condición 1] Row-major detectado: {extracted_table.reading_orientation} "
          f"(conf={extracted_table.orientation_confidence:.2f}, reason='{extracted_table.orientation_reason}')")

    # 3. Validación de celdas tipo Excel y clasificación
    # Celdas de encabezado (fila 0): text_only
    header_cells = [c for c in extracted_table.cells if c.row_index == 0]
    for hc in header_cells:
        assert hc.cell_type in ("text_only", "text_cell")
        assert hc.inner_drawing_bbox is None

    # Celdas con símbolos (col 0, filas 1..3): symbol_only / symbol_cell con inner_drawing_bbox
    symbol_cells = [c for c in extracted_table.cells if c.column_index == 0 and c.row_index > 0]
    assert len(symbol_cells) == 3
    for sc in symbol_cells:
        assert sc.cell_type in ("symbol_only", "symbol_cell", "mixed", "mixed_cell")
        assert sc.inner_drawing_bbox is not None
        assert len(sc.inner_drawing_bbox) == 4
        # inner_drawing_bbox debe estar contenido dentro de cell_bbox
        assert sc.inner_drawing_bbox[0] >= sc.bbox_normalized[0] - 0.05
        assert sc.inner_drawing_bbox[1] >= sc.bbox_normalized[1] - 0.05
        assert sc.inner_drawing_bbox[2] <= sc.bbox_normalized[2] + 0.05
        assert sc.inner_drawing_bbox[3] <= sc.bbox_normalized[3] + 0.05

    # 4. Condición 4: Recorte final symbol_crop_bbox = inner_drawing_bbox + 3mm limitado a cell_bbox
    assert len(extracted_table.extracted_symbols) == 3
    for sym in extracted_table.extracted_symbols:
        # El bbox final corresponde a symbol_crop_bbox (3mm) y está acotado estrictamente dentro de cell_bbox
        assert sym.bbox_normalized == sym.symbol_crop_bbox
        assert sym.cell_bbox is not None and len(sym.cell_bbox) == 4
        assert sym.cell_bbox[0] <= sym.symbol_crop_bbox[0] + 0.001
        assert sym.cell_bbox[1] <= sym.symbol_crop_bbox[1] + 0.001
        assert sym.symbol_crop_bbox[2] <= sym.cell_bbox[2] + 0.001
        assert sym.symbol_crop_bbox[3] <= sym.cell_bbox[3] + 0.001
        assert sym.inner_drawing_bbox is not None
        # Verificar archivo físico en disco
        crop_filename = Path(sym.crop_image_path).name
        expected_disk_path = Path(settings.STORAGE_LOCAL_ROOT) / "crops" / "symbols" / crop_filename
        if not expected_disk_path.exists():
            expected_disk_path = tmp_path / "crops_row" / crop_filename
        assert expected_disk_path.exists()
        assert expected_disk_path.stat().st_size > 100

        # Orientación registrada en el símbolo
        assert sym.reading_orientation == "row_major"
        assert sym.orientation_confidence >= 0.70
        assert sym.orientation_reason is not None

    print(f"[Condición 3] Símbolos con recorte de celda completa: {len(extracted_table.extracted_symbols)} válidos con inner_drawing_bbox.")


def test_condition_1_orientation_col_major(tmp_path):
    """
    Valida detección de orientación COL_MAJOR cuando los símbolos están
    en una fila (distribuidos en columnas) y el texto descriptivo está debajo.
    """
    pdf_bytes, meta = create_col_major_legend_pdf()
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[0]

    texts = _extract_page_words_as_texts(page)
    extractor = TableExtractor(width_px=int(page.rect.width), height_px=int(page.rect.height))
    extracted_table = extractor.extract_from_region(
        region_bbox_norm=meta["table_bbox_norm"],
        texts=texts,
        symbols=[],
        page=page,
        doc_uid="test_col_major",
        crops_dir=str(tmp_path / "crops_col")
    )
    doc.close()

    assert extracted_table is not None
    assert extracted_table.has_symbols is True
    # Verificación de orientación COL_MAJOR
    assert extracted_table.reading_orientation == "col_major"
    assert extracted_table.orientation_confidence >= 0.70
    assert extracted_table.orientation_reason is not None
    print(f"\n[Condición 1] Col-major detectado: {extracted_table.reading_orientation} "
          f"(conf={extracted_table.orientation_confidence:.2f}, reason='{extracted_table.orientation_reason}')")

    # Los símbolos extraídos heredan col_major
    for sym in extracted_table.extracted_symbols:
        assert sym.reading_orientation == "col_major"
        assert sym.orientation_confidence >= 0.70


def test_condition_2_discard_text_only_tables_from_symbols(tmp_path):
    """
    Valida Condición 2:
    Si no existe ningún símbolo en la tabla (solo texto o vacías),
    la tabla NO debe entrar al pipeline de simbología.
    - extracted_table.has_symbols == False
    - extracted_table.extracted_symbols == []
    """
    pdf_bytes, meta = create_text_only_table_pdf()
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[0]

    texts = _extract_page_words_as_texts(page)
    extractor = TableExtractor(width_px=int(page.rect.width), height_px=int(page.rect.height))
    extracted_table = extractor.extract_from_region(
        region_bbox_norm=meta["table_bbox_norm"],
        texts=texts,
        symbols=[],
        page=page,
        doc_uid="test_text_only",
        crops_dir=str(tmp_path / "crops_txt")
    )
    doc.close()

    assert extracted_table is not None
    # Condición 2: has_symbols DEBE ser False
    assert extracted_table.has_symbols is False
    # extracted_symbols DEBE estar vacío
    assert len(extracted_table.extracted_symbols) == 0

    # Todas las celdas deben ser text_only / text_cell
    for cell in extracted_table.cells:
        assert cell.cell_type in ("text_only", "text_cell")
        assert cell.inner_drawing_bbox is None

    print("\n[Condición 2] Tabla solo texto descartada exitosamente del pipeline de simbología.")


def test_condition_4_canonical_deduplication_and_occurrences(db_session: Session, tmp_path):
    """
    Valida Condición 4:
    - En la UI / candidatos debe mostrarse un solo representante canónico por símbolo.
    - Todas sus ocurrencias deben quedar registradas en metadata_payload["occurrences"].
    - Las ocurrencias guardan page_number, row_index, col_index, cell_bbox, is_primary.
    """
    org_id = str(uuid.uuid4())
    proj_id = str(uuid.uuid4())
    ext_id = str(uuid.uuid4())

    org = Organization(id=org_id, name="Test Org Deduplication", slug=f"slug-{uuid.uuid4().hex[:6]}")
    db_session.add(org)

    project = Project(id=proj_id, organization_id=org_id, code=f"PRJ-{uuid.uuid4().hex[:4].upper()}", name="Test Project Deduplication", status="active")
    db_session.add(project)

    # Crear imágenes falsas para que no falle la verificación de existencia
    crop_1 = tmp_path / "crop_p1.png"
    crop_2 = tmp_path / "crop_p2.png"
    crop_1.write_bytes(b"dummy_png_data_1234")
    crop_2.write_bytes(b"dummy_png_data_5678")

    extraction = SourceExtraction(
        id=ext_id,
        organization_id=org_id,
        project_id=proj_id,
        source_asset_id=f"doc_{uuid.uuid4().hex[:8]}",
        source_origin="document",
        title="Extracción de Prueba Deduplicación",
        status="pending"
    )
    db_session.add(extraction)
    db_session.commit()

    evidence_payload = {
        "tables": [
            {
                "page_number": 1,
                "table_bbox": [50, 70, 750, 180],
                "reading_orientation": "row_major",
                "orientation_confidence": 0.85,
                "orientation_reason": "concentración en columna 0",
                "has_symbols": True,
                "cells": [
                    {"row_index": 1, "col_index": 0, "cell_type": "symbol_only", "cell_bbox": [0.11, 0.06, 0.30, 0.22], "inner_drawing_bbox": [0.13, 0.08, 0.28, 0.20]},
                    {"row_index": 1, "col_index": 1, "cell_type": "text_only", "cell_bbox": [0.11, 0.22, 0.30, 0.65], "text": "Extintor PQS 10kg ABC"}
                ],
                "extracted_symbols": [
                    {
                        "id": "sym_p1_r1",
                        "symbol_name": "Extintor PQS 10kg ABC",
                        "tag_or_code": "PQS-10",
                        "canonical_symbol_family": "fire_safety",
                        "page_number": 1,
                        "bbox_normalized": [0.11, 0.06, 0.30, 0.22],
                        "cell_bbox": [0.11, 0.06, 0.30, 0.22],
                        "inner_drawing_bbox": [0.13, 0.08, 0.28, 0.20],
                        "crop_image_path": str(crop_1),
                        "reading_orientation": "row_major",
                        "orientation_confidence": 0.85,
                        "orientation_reason": "concentración en columna 0",
                        "requires_human_review": False
                    }
                ]
            },
            {
                "page_number": 2,
                "table_bbox": [50, 70, 750, 180],
                "reading_orientation": "row_major",
                "orientation_confidence": 0.85,
                "orientation_reason": "concentración en columna 0",
                "has_symbols": True,
                "cells": [
                    {"row_index": 1, "col_index": 0, "cell_type": "symbol_only", "cell_bbox": [0.11, 0.06, 0.30, 0.22], "inner_drawing_bbox": [0.13, 0.08, 0.28, 0.20]},
                    {"row_index": 1, "col_index": 1, "cell_type": "text_only", "cell_bbox": [0.11, 0.22, 0.30, 0.65], "text": "Extintor PQS 10kg ABC"}
                ],
                "extracted_symbols": [
                    {
                        "id": "sym_p2_r1",
                        "symbol_name": "Extintor PQS 10kg ABC",
                        "tag_or_code": "PQS-10",
                        "canonical_symbol_family": "fire_safety",
                        "page_number": 2,
                        "bbox_normalized": [0.11, 0.06, 0.30, 0.22],
                        "cell_bbox": [0.11, 0.06, 0.30, 0.22],
                        "inner_drawing_bbox": [0.13, 0.08, 0.28, 0.20],
                        "crop_image_path": str(crop_2),
                        "reading_orientation": "row_major",
                        "orientation_confidence": 0.85,
                        "orientation_reason": "concentración en columna 0",
                        "requires_human_review": False
                    }
                ]
            }
        ]
    }

    # Ejecutar generación de candidatos
    gen_service = CandidateGeneratorService(db=db_session)
    candidates = gen_service.generate_candidates_from_evidence(extraction.id, evidence_payload=evidence_payload)

    symbol_candidates = [c for c in candidates if c.item_type == "symbol" or c.candidate_type == "symbol_candidate"]

    # Condición 4: Exactamente 1 representante canónico para el símbolo repetido en Pág 1 y Pág 2
    assert len(symbol_candidates) == 1
    canonical_sym = symbol_candidates[0]

    # Verificar presencia de occurrences
    tech_params = canonical_sym.technical_parameters or {}
    occurrences = tech_params.get("occurrences", [])
    occurrences_count = tech_params.get("occurrences_count", 0)

    assert occurrences_count == 2
    assert len(occurrences) == 2
    assert occurrences[0]["page_number"] == 1
    assert occurrences[0]["is_primary"] is True
    assert occurrences[1]["page_number"] == 2
    assert occurrences[1]["is_primary"] is False

    # Verificar campos de orientación y recorte
    assert tech_params.get("reading_orientation") == "row_major"
    assert tech_params.get("orientation_confidence") == 0.85
    assert tech_params.get("inner_drawing_bbox") == [0.13, 0.08, 0.28, 0.20]

    print(f"\n[Condición 4] Deduplicación canónica exitosa: 1 representante para 2 ocurrencias (Págs: {[o['page_number'] for o in occurrences]})")


def test_condition_5_low_confidence_triggers_human_review(db_session: Session, tmp_path):
    """
    Valida Condición 5:
    Si la orientación no puede determinarse con suficiente confianza (< 0.60),
    marcar el caso para revisión humana en vez de poblar mal los datos:
    - requires_human_review = True
    - completeness_status = 'review_required'
    - review_status = 'to_confirm'
    """
    org_id = str(uuid.uuid4())
    proj_id = str(uuid.uuid4())
    ext_id = str(uuid.uuid4())

    org = Organization(id=org_id, name="Test Org Low Conf", slug=f"slug-{uuid.uuid4().hex[:6]}")
    db_session.add(org)

    project = Project(id=proj_id, organization_id=org_id, code=f"PRJ-{uuid.uuid4().hex[:4].upper()}", name="Test Project Low Conf", status="active")
    db_session.add(project)

    crop_path = tmp_path / "crop_low_conf.png"
    crop_path.write_bytes(b"dummy_crop")

    extraction = SourceExtraction(
        id=ext_id,
        organization_id=org_id,
        project_id=proj_id,
        source_asset_id=f"doc_{uuid.uuid4().hex[:8]}",
        source_origin="document",
        title="Extracción Baja Confianza",
        status="pending"
    )
    db_session.add(extraction)
    db_session.commit()

    evidence_payload = {
        "tables": [
            {
                "page_number": 1,
                "table_bbox": [50, 70, 750, 180],
                "reading_orientation": "undetermined",
                "orientation_confidence": 0.40,  # < 0.60
                "orientation_reason": "Distribución dispersa de celdas gráficas",
                "has_symbols": True,
                "extracted_symbols": [
                    {
                        "id": "sym_ambiguous_1",
                        "symbol_name": "Símbolo Desconocido o Ambiguo",
                        "tag_or_code": "SYM-01",
                        "canonical_symbol_family": "valves",
                        "page_number": 1,
                        "bbox_normalized": [0.10, 0.10, 0.25, 0.25],
                        "cell_bbox": [0.10, 0.10, 0.25, 0.25],
                        "crop_image_path": str(crop_path),
                        "reading_orientation": "undetermined",
                        "orientation_confidence": 0.40,
                        "orientation_reason": "Distribución dispersa de celdas gráficas",
                        "requires_human_review": True
                    }
                ]
            }
        ]
    }

    gen_service = CandidateGeneratorService(db=db_session)
    candidates = gen_service.generate_candidates_from_evidence(extraction.id, evidence_payload=evidence_payload)

    symbol_cands = [c for c in candidates if c.item_type == "symbol" or c.candidate_type == "symbol_candidate"]
    assert len(symbol_cands) == 1
    cand = symbol_cands[0]

    # Condición 5: Marcado para revisión humana
    tech_params = cand.technical_parameters or {}
    assert cand.completeness_status == "review_required"
    assert cand.review_status == "to_confirm"
    assert tech_params.get("reading_orientation") == "undetermined"
    assert tech_params.get("orientation_confidence") == 0.40

    print("\n[Condición 5] Símbolo de baja confianza marcado exitosamente para revisión humana.")


def test_context_viewer_multipage_navigation(db_session: Session, tmp_path):
    """
    Valida que CandidateEnrichmentService.get_item_context permita recibir
    page_number y bbox_override para navegar a cualquier ocurrencia secundaria.
    """
    org_id = str(uuid.uuid4())
    proj_id = str(uuid.uuid4())
    ext_id = str(uuid.uuid4())
    item_id = str(uuid.uuid4())

    org = Organization(id=org_id, name="Test Org Nav", slug=f"slug-{uuid.uuid4().hex[:6]}")
    db_session.add(org)

    project = Project(id=proj_id, organization_id=org_id, code=f"PRJ-{uuid.uuid4().hex[:4].upper()}", name="Test Project Nav", status="active")
    db_session.add(project)

    extraction = SourceExtraction(
        id=ext_id,
        organization_id=org_id,
        project_id=proj_id,
        source_origin="document",
        title="Documento Nav Test",
        status="completed"
    )
    db_session.add(extraction)

    item = ExtractedItem(
        id=item_id,
        extraction_id=ext_id,
        item_type="symbol",
        candidate_type="symbol_candidate",
        title="Símbolo Multipage",
        page_number=1,  # Página primaria = 1
        bbox_normalized=[0.1, 0.1, 0.3, 0.3],
        crop_image_path="/data/crops/symbols/sym_nav_test.png"
    )
    db_session.add(item)
    db_session.commit()

    enrichment_service = CandidateEnrichmentService(db=db_session)

    # 1. Contexto estándar (página primaria)
    ctx_primary = enrichment_service.get_item_context(extraction_id=ext_id, item_id=item.id)
    assert ctx_primary["page_number"] == 1
    assert ctx_primary["bbox_normalized"] == [0.1, 0.1, 0.3, 0.3]

    # 2. Contexto de ocurrencia secundaria en página 3
    ctx_secondary = enrichment_service.get_item_context(
        extraction_id=ext_id,
        item_id=item.id,
        page_number=3,
        bbox_override=[0.2, 0.2, 0.4, 0.4]
    )
    assert ctx_secondary["page_number"] == 3
    assert ctx_secondary["bbox_normalized"] == [0.2, 0.2, 0.4, 0.4]

    print("\n[Navegación Multipage] get_item_context navega correctamente a ocurrencias secundarias.")
