import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import uuid
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.core import Organization, Project
from app.db.models.intake_extractions import (
    SourceExtraction, ExtractedItem, StructuredSymbol, RuleDocument, RuleDocumentItem
)
from app.db.models.decision_memory import RuleDefinition
from app.db.repositories.intake_extraction_repository import IntakeExtractionRepository
from app.services.tables.extractor import TableExtractor, ExtractedCellDTO
from app.services.symbols.legend_table_extractor import LegendTableExtractor, ExtractedPipingSymbolDTO


def test_table_extractor_preserves_symbol_cells_and_lineage():
    """
    Condición 1 y Linaje:
    1. La tabla debe seguir representándose como tabla estructurada con tipos explícitos
       de celda (symbol_cell, text_cell, empty_cell, mixed_cell) y vínculo a symbol_id.
    2. La persistencia de linaje (row_index, col_index, cell_bbox, row_bbox)
       debe quedar registrada directamente en el candidato de símbolo.
    """
    extractor = TableExtractor(width_px=1000, height_px=1000)

    # Definir textos de la tabla:
    # Encabezados en y in [0.05, 0.08]
    # Fila 1 en y in [0.15, 0.20] (Col 0: símbolo, Col 1: texto descripción, Col 2: texto norma)
    # Fila 2 en y in [0.25, 0.30] (Col 0: símbolo, Col 1: texto descripción, Col 2: texto norma)
    texts = [
        # Encabezados (Fila 0)
        {"text": "SÍMBOLO", "clean_text": "SIMBOLO", "bbox_normalized": [0.05, 0.05, 0.20, 0.08], "id": "t_h0"},
        {"text": "DESCRIPCIÓN DEL EQUIPO", "clean_text": "DESCRIPCION", "bbox_normalized": [0.25, 0.05, 0.70, 0.08], "id": "t_h1"},
        {"text": "NORMA APLICABLE", "clean_text": "NORMA", "bbox_normalized": [0.75, 0.05, 0.95, 0.08], "id": "t_h2"},

        # Fila 1 Textos (Col 1 y Col 2)
        {"text": "VÁLVULA DE COMPUERTA ASME B16.34", "clean_text": "VALVULA DE COMPUERTA", "bbox_normalized": [0.25, 0.15, 0.70, 0.19], "id": "t_r1_c1"},
        {"text": "ASME B16.34 CLASE 150", "clean_text": "ASME B16.34", "bbox_normalized": [0.75, 0.15, 0.95, 0.19], "id": "t_r1_c2"},

        # Fila 2 Textos (Col 1 y Col 2)
        {"text": "VÁLVULA CHECK / RETENCIÓN DE COLUMPIO", "clean_text": "VALVULA CHECK", "bbox_normalized": [0.25, 0.25, 0.70, 0.29], "id": "t_r2_c1"},
        {"text": "API 594 / ISA 5.1", "clean_text": "API 594", "bbox_normalized": [0.75, 0.25, 0.95, 0.29], "id": "t_r2_c2"},
    ]

    # Candidatos de símbolos en Columna 0
    sym1_id = f"sym_{uuid.uuid4().hex[:8]}"
    sym2_id = f"sym_{uuid.uuid4().hex[:8]}"

    sym1_cand = ExtractedPipingSymbolDTO(
        id=sym1_id,
        symbol_name="VÁLVULA DE COMPUERTA",
        canonical_symbol_family="valves",
        standard_reference="ASME B16.34",
        discipline="piping",
        source_render_mode="vector",
        bbox_normalized=[0.08, 0.15, 0.17, 0.19],
        confidence_score=0.92,
        crop_image_path="crops/valve_gate.png"
    )

    sym2_cand = ExtractedPipingSymbolDTO(
        id=sym2_id,
        symbol_name="VÁLVULA CHECK",
        canonical_symbol_family="valves",
        standard_reference="API 594",
        discipline="piping",
        source_render_mode="vector",
        bbox_normalized=[0.08, 0.25, 0.17, 0.29],
        confidence_score=0.89,
        crop_image_path="crops/valve_check.png"
    )

    table = extractor.extract_from_region(
        region_bbox_norm=[0.0, 0.0, 1.0, 1.0],
        texts=texts,
        symbols=[sym1_cand, sym2_cand]
    )

    assert table is not None, "La tabla estructurada debe ser detectada."
    assert table.row_count == 3, f"Debe tener 3 filas (encabezado + 2 filas), obtuvo: {table.row_count}"
    assert table.column_count == 3, f"Debe tener 3 columnas, obtuvo: {table.column_count}"

    # Validar celda con símbolo Fila 1, Columna 0
    cell_r1_c0 = next((c for c in table.cells if c.row_index == 1 and c.column_index == 0), None)
    assert cell_r1_c0 is not None, "Debe existir la celda en fila 1, columna 0."
    assert cell_r1_c0.cell_type == "symbol_cell", f"La celda con símbolo debe ser 'symbol_cell', obtuvo: {cell_r1_c0.cell_type}"
    assert cell_r1_c0.has_symbol is True, "has_symbol debe ser True."
    assert cell_r1_c0.symbol_id == sym1_id, "symbol_id debe coincidir con el candidato."

    # Validar celda de texto Fila 1, Columna 1
    cell_r1_c1 = next((c for c in table.cells if c.row_index == 1 and c.column_index == 1), None)
    assert cell_r1_c1 is not None
    assert cell_r1_c1.cell_type == "text_cell", f"La celda de texto debe ser 'text_cell', obtuvo: {cell_r1_c1.cell_type}"
    assert "VÁLVULA DE COMPUERTA" in cell_r1_c1.text

    # Validar celda con símbolo Fila 2, Columna 0
    cell_r2_c0 = next((c for c in table.cells if c.row_index == 2 and c.column_index == 0), None)
    assert cell_r2_c0 is not None
    assert cell_r2_c0.cell_type == "symbol_cell"
    assert cell_r2_c0.has_symbol is True
    assert cell_r2_c0.symbol_id == sym2_id

    # Validar linaje propagado a los objetos candidatos
    assert getattr(sym1_cand, "row_index") == 1, "Linaje: row_index debe ser 1."
    assert getattr(sym1_cand, "col_index") == 0, "Linaje: col_index debe ser 0."
    assert getattr(sym1_cand, "cell_bbox") is not None, "Linaje: cell_bbox no debe ser nulo."
    assert getattr(sym1_cand, "row_bbox") is not None, "Linaje: row_bbox no debe ser nulo."
    assert getattr(sym1_cand, "layout_context") == "inside_table", "Contexto debe ser inside_table."

    assert getattr(sym2_cand, "row_index") == 2, "Linaje: row_index debe ser 2."
    assert getattr(sym2_cand, "col_index") == 0, "Linaje: col_index debe ser 0."


def test_symbol_text_association_priorities(db_session: Session):
    """
    Condición 3:
    La asociación símbolo-texto debe priorizar:
    1. Misma fila en tabla estructurada (row_band / same_row_cells),
    2. Misma tabla (celdas adyacentes de la misma tabla si la fila no tiene texto),
    3. Fallback lateral/caption band.
    """
    extractor = LegendTableExtractor(db_session)

    # Simular candidatos
    cand_p1 = ExtractedPipingSymbolDTO(
        id=f"c1_{uuid.uuid4().hex[:6]}",
        symbol_name="SIMBOLO_FILA_1",
        canonical_symbol_family="valves",
        discipline="piping",
        source_render_mode="vector",
        bbox_normalized=[0.05, 0.20, 0.15, 0.25],
        confidence_score=0.9
    )
    # Candidato con linaje de fila 1
    cand_p1.row_index = 1
    cand_p1.col_index = 0

    # Crear tabla estructurada mock usando TableExtractor
    te = TableExtractor(1000, 1000)
    texts_table = [
        {"text": "COL SÍMBOLO", "clean_text": "SIMBOLO", "bbox_normalized": [0.05, 0.05, 0.20, 0.09], "id": "th0"},
        {"text": "COL DESCRIPCIÓN", "clean_text": "DESCRIPCION", "bbox_normalized": [0.25, 0.05, 0.80, 0.09], "id": "th1"},
        {"text": "VÁLVULA DE SEGURIDAD Y ALIVIO POR PRESIÓN", "clean_text": "VALVULA DE SEGURIDAD", "bbox_normalized": [0.25, 0.20, 0.80, 0.25], "id": "tr1_c1"}
    ]
    extracted_table = te.extract_from_region(
        region_bbox_norm=[0.0, 0.0, 1.0, 1.0],
        texts=texts_table,
        symbols=[cand_p1]
    )

    # Verificar Prioridad 1: Misma fila
    same_row_cells = [
        c for c in extracted_table.cells
        if c.row_index == cand_p1.row_index and c.column_index != cand_p1.col_index and c.text
    ]
    assert len(same_row_cells) > 0
    assert "VÁLVULA DE SEGURIDAD" in same_row_cells[0].text


def test_curation_candidates_multi_page_occurrences(client: TestClient, db_session: Session):
    """
    Condición 2:
    Para la navegación por páginas, cada ocurrencia debe incluir:
    - page_number
    - bbox_normalized
    - source_document_id o sheet_id
    de modo que el click abra el visor en la página correcta y enfoque la región.
    """
    org = Organization(id=str(uuid.uuid4()), name="MultiPage Engineering", slug=f"mp-{uuid.uuid4().hex[:6]}")
    db_session.add(org)
    db_session.flush()

    ext = SourceExtraction(
        id=str(uuid.uuid4()),
        organization_id=org.id,
        title="Lámina de Piping Multipágina",
        discipline="piping",
        document_type="norma",
        extraction_mode="ai_document",
        status="completed",
        total_items=2
    )
    db_session.add(ext)
    db_session.flush()

    group_id = f"group_gate_valve_{uuid.uuid4().hex[:6]}"

    # Ocurrencia 1 en Página 1
    item1 = ExtractedItem(
        id=str(uuid.uuid4()),
        extraction_id=ext.id,
        item_type="symbol",
        title="Válvula de Compuerta P1",
        description="Válvula de compuerta 150 RF",
        ocr_text="VÁLVULA DE COMPUERTA P1",
        page_number=1,
        bbox_normalized=[0.1, 0.2, 0.18, 0.28],
        source_asset_id="sheet_page_1",
        review_status="pending"
    )
    db_session.add(item1)
    db_session.flush()

    sym1 = StructuredSymbol(
        id=str(uuid.uuid4()),
        extracted_item_id=item1.id,
        symbol_name="Válvula de Compuerta",
        standard_family="ISA-5.1",
        canonical_symbol_family="valves",
        discipline="piping",
        source_render_mode="vector",
        visual_variant_group_id=group_id,
        source_table_id="table_p1",
        row_index=1,
        col_index=0,
        cell_bbox=[0.08, 0.19, 0.20, 0.29],
        row_bbox=[0.05, 0.19, 0.95, 0.29]
    )
    db_session.add(sym1)

    # Ocurrencia 2 en Página 3 (misma variante/grupo visual en otra página)
    item2 = ExtractedItem(
        id=str(uuid.uuid4()),
        extraction_id=ext.id,
        item_type="symbol",
        title="Válvula de Compuerta P3",
        description="Válvula de compuerta 150 RF en hoja 3",
        ocr_text="VÁLVULA DE COMPUERTA P3",
        page_number=3,
        bbox_normalized=[0.4, 0.6, 0.48, 0.68],
        source_asset_id="sheet_page_3",
        review_status="pending"
    )
    db_session.add(item2)
    db_session.flush()

    sym2 = StructuredSymbol(
        id=str(uuid.uuid4()),
        extracted_item_id=item2.id,
        symbol_name="Válvula de Compuerta",
        standard_family="ISA-5.1",
        canonical_symbol_family="valves",
        discipline="piping",
        source_render_mode="vector",
        visual_variant_group_id=group_id,
        source_table_id="table_p3",
        row_index=4,
        col_index=0,
        cell_bbox=[0.38, 0.59, 0.50, 0.69],
        row_bbox=[0.05, 0.59, 0.95, 0.69]
    )
    db_session.add(sym2)
    db_session.commit()

    # Consultar endpoint de candidatos
    resp = client.get(f"/api/v1/symbols/curation-candidates?extraction_id={ext.id}")
    assert resp.status_code == 200, f"Error listando candidatos: {resp.text}"
    candidates = resp.json()
    assert len(candidates) >= 2

    # Verificar que el grupo visual consolida las ocurrencias multipágina
    first_cand = candidates[0]
    assert len(first_cand["occurrences"]) >= 2, "Debe consolidar las ocurrencias de todas las páginas del grupo."

    pages = [occ["page_number"] for occ in first_cand["occurrences"]]
    assert 1 in pages and 3 in pages, f"Debe incluir la página 1 y la página 3, obtuvo: {pages}"

    for occ in first_cand["occurrences"]:
        assert "page_number" in occ
        assert "bbox_normalized" in occ and len(occ["bbox_normalized"]) == 4
        assert occ["sheet_id"] is not None or occ["source_document_id"] is not None, "Debe proveer sheet_id o source_document_id para navegación."

    # Verificar linaje estructural de tabla
    assert first_cand["source_table_id"] is not None
    assert first_cand["row_index"] is not None
    assert first_cand["col_index"] is not None
    assert first_cand["cell_bbox"] is not None
    assert first_cand["row_bbox"] is not None


def test_symbols_strictly_excluded_from_rule_definition_promotion(db_session: Session):
    """
    Condición 4:
    Los símbolos deben quedar excluidos del flujo que promueve `RuleDefinition`.
    Deben seguir su propio ciclo hacia curación y `SymbolTemplate`.
    """
    org = Organization(id=str(uuid.uuid4()), name="Normative Safety Corp", slug=f"nsc-{uuid.uuid4().hex[:6]}")
    db_session.add(org)
    db_session.flush()

    repo = IntakeExtractionRepository(db_session)

    # 1. Crear documento normativo con mezcla de reglas y símbolos
    rule_doc = RuleDocument(
        id=str(uuid.uuid4()),
        organization_id=org.id,
        title="Norma Técnica NCh 382 con Simbología",
        document_type="norma",
        discipline="seguridad",
        version="2.0",
        status="active",
        items_count=4,
        rules_count=2,
        tables_count=1,
        images_count=0,
        symbols_count=1
    )
    db_session.add(rule_doc)
    db_session.flush()

    # Regla 1 (Normativa) -> DEBE promoverse
    item_rule1 = RuleDocumentItem(
        id=str(uuid.uuid4()),
        rule_document_id=rule_doc.id,
        item_type="rule",
        title="Distancia Mínima de Válvula de Seguridad",
        code_or_number="NCh-SEC-01",
        description="La válvula de seguridad debe ubicarse a menos de 500 mm del cabezal.",
        status="validada"
    )
    db_session.add(item_rule1)

    # Regla 2 (Normativa) -> DEBE promoverse
    item_rule2 = RuleDocumentItem(
        id=str(uuid.uuid4()),
        rule_document_id=rule_doc.id,
        item_type="rule",
        title="Presión de Tarado de Alivio",
        code_or_number="NCh-SEC-02",
        description="La presión no debe exceder 1.1 veces la presión de diseño.",
        status="validada"
    )
    db_session.add(item_rule2)

    # Símbolo 1 -> DEBE QUEDAR EXCLUIDO DE RuleDefinition
    item_sym = RuleDocumentItem(
        id=str(uuid.uuid4()),
        rule_document_id=rule_doc.id,
        item_type="symbol",
        title="Símbolo Válvula PSV-101",
        code_or_number="SYM-PSV-101",
        description="Válvula de seguridad y alivio con resorte según ISA 5.1",
        status="validada"
    )
    db_session.add(item_sym)

    # Tabla 1 -> DEBE QUEDAR EXCLUIDA DE RuleDefinition
    item_tbl = RuleDocumentItem(
        id=str(uuid.uuid4()),
        rule_document_id=rule_doc.id,
        item_type="table",
        title="Tabla 4.1 de Presiones Máximas",
        code_or_number="TBL-04-01",
        description="Tabla de tolerancias",
        status="validada"
    )
    db_session.add(item_tbl)
    db_session.commit()

    # 2. Ejecutar promoción hacia Baseline QA/QC
    res = repo.promote_rule_document_to_baseline(rule_doc.id, user_id="test_auditor")

    doc_after = repo.get_rule_document_by_id(rule_doc.id)
    assert doc_after.status == "promovido_baseline"
    # Solo deben promoverse las 2 reglas normativas
    assert res["promoted_count"] == 2, f"Se esperaban 2 reglas promovidas, obtuvo {res['promoted_count']}"
    assert doc_after.symbols_count == 1, "symbols_count debe mantenerse en 1."

    # 3. Verificar en base de datos la tabla rule_definitions
    promoted_rules = db_session.query(RuleDefinition).all()
    # Filtrar por las creadas en esta prueba
    rule_names = [r.name for r in promoted_rules]
    assert "Distancia Mínima de Válvula de Seguridad" in rule_names
    assert "Presión de Tarado de Alivio" in rule_names

    # Verificar que el símbolo NUNCA se convirtió en RuleDefinition
    assert "Símbolo Válvula PSV-101" not in rule_names, "El símbolo NO debe existir en rule_definitions."
    assert "Tabla 4.1 de Presiones Máximas" not in rule_names, "La tabla NO debe existir en rule_definitions."

    # 4. Confirmar que el item del símbolo no tiene promoted_to_baseline=True
    sym_db_item = repo.get_rule_document_item_by_id(item_sym.id)
    assert sym_db_item.metadata_payload is None or not sym_db_item.metadata_payload.get("promoted_to_baseline", False)
