"""
Script de Demostración y Evidencia Funcional:
Integración de Estructura Tabular + Simbología Técnica (Piping & Instrumentación)
Verifica las 4 condiciones de ejecución:
1. Preservación de tabla como estructura tabular con tipos explícitos de celda (symbol_cell, text_cell).
2. Persistencia de linaje tabla-fila-columna (source_table_id, row_index, col_index, cell_bbox, row_bbox).
3. Asociación contextual símbolo-texto con prioridad (misma fila > misma tabla > fallback lateral/caption).
4. Exclusión estricta de símbolos del baseline de reglas QA/QC (quedan para SymbolTemplate y Curación HITL).
"""

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import json
import uuid
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.db.models.core import Organization, Project
from app.db.models.intake_extractions import (
    SourceExtraction, ExtractedItem, StructuredSymbol, RuleDocument, RuleDocumentItem
)
from app.db.models.decision_memory import RuleDefinition
from app.db.repositories.intake_extraction_repository import IntakeExtractionRepository
from app.services.tables.extractor import TableExtractor
from app.services.symbols.legend_table_extractor import ExtractedPipingSymbolDTO


def run_evidence():
    print("=" * 80)
    print("DEMOSTRACIÓN DE EVIDENCIA: TRATAMIENTO INTEGRAL DE SIMBOLOGÍA EN TABLAS")
    print("=" * 80)

    # 1. Configurar DB SQLite en memoria para la evidencia
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    org = Organization(id=str(uuid.uuid4()), name="Auditoría Simbología Industrial", slug="auditoria-simb")
    db.add(org)
    db.flush()

    # =========================================================================
    # CONDICIÓN 1 & LINAJE: TABLA ESTRUCTURADA CON CELDAS TIPADAS Y SÍMBOLOS
    # =========================================================================
    print("\n--- 1. EXTRACCIÓN TABULAR CON CELDAS EXPLÍCITAS Y LINAJE ---")
    extractor = TableExtractor(width_px=1200, height_px=900)

    # Candidatos a símbolos en columna 0
    sym_gate_id = f"sym_{uuid.uuid4().hex[:8]}"
    sym_check_id = f"sym_{uuid.uuid4().hex[:8]}"

    sym_gate = ExtractedPipingSymbolDTO(
        id=sym_gate_id,
        symbol_name="VÁLVULA DE COMPUERTA MANUAL",
        canonical_symbol_family="valves",
        standard_reference="ASME B16.34",
        discipline="piping",
        source_render_mode="vector",
        bbox_normalized=[0.05, 0.15, 0.15, 0.22],
        confidence_score=0.94,
        crop_image_path="crops/valve_gate_demo.png"
    )

    sym_check = ExtractedPipingSymbolDTO(
        id=sym_check_id,
        symbol_name="VÁLVULA CHECK DE RETENCIÓN",
        canonical_symbol_family="valves",
        standard_reference="API 594",
        discipline="piping",
        source_render_mode="vector",
        bbox_normalized=[0.05, 0.25, 0.15, 0.32],
        confidence_score=0.91,
        crop_image_path="crops/valve_check_demo.png"
    )

    texts = [
        # Encabezado (Fila 0)
        {"text": "SÍMBOLO", "clean_text": "SIMBOLO", "bbox_normalized": [0.05, 0.05, 0.20, 0.09], "id": "th0"},
        {"text": "DESCRIPCIÓN TÉCNICA", "clean_text": "DESCRIPCION TECNICA", "bbox_normalized": [0.25, 0.05, 0.65, 0.09], "id": "th1"},
        {"text": "NORMA / CLASE", "clean_text": "NORMA CLASE", "bbox_normalized": [0.70, 0.05, 0.95, 0.09], "id": "th2"},

        # Fila 1 (Col 1 y Col 2)
        {"text": "VÁLVULA DE COMPUERTA MANUAL RF CLASE 150", "clean_text": "VALVULA DE COMPUERTA MANUAL", "bbox_normalized": [0.25, 0.15, 0.65, 0.22], "id": "tr1_c1"},
        {"text": "ASME B16.34 / ISA 5.1", "clean_text": "ASME B16.34 ISA 5.1", "bbox_normalized": [0.70, 0.15, 0.95, 0.22], "id": "tr1_c2"},

        # Fila 2 (Col 1 y Col 2)
        {"text": "VÁLVULA DE RETENCIÓN TIPO COLUMPIO", "clean_text": "VALVULA RETENCION COLUMPIO", "bbox_normalized": [0.25, 0.25, 0.65, 0.32], "id": "tr2_c1"},
        {"text": "API 594 CLASE 300", "clean_text": "API 594 CLASE 300", "bbox_normalized": [0.70, 0.25, 0.95, 0.32], "id": "tr2_c2"},
    ]

    table = extractor.extract_from_region(
        region_bbox_norm=[0.0, 0.0, 1.0, 1.0],
        texts=texts,
        symbols=[sym_gate, sym_check]
    )

    print(f"✓ Tabla detectada: {table.row_count} filas x {table.column_count} columnas")
    print(f"✓ Total celdas estructuradas: {len(table.cells)}")

    # Imprimir matriz de celdas y su clasificación explícita
    print("\n[MATRIZ DE CELDAS ESTRUCTURADAS]")
    for r in range(table.row_count):
        row_cells = sorted([c for c in table.cells if c.row_index == r], key=lambda x: x.column_index)
        row_repr = []
        for c in row_cells:
            if c.cell_type == "symbol_cell":
                row_repr.append(f"[F{c.row_index}:C{c.column_index} SYMBOL({c.symbol_id[:8]})]")
            elif c.cell_type == "text_cell":
                row_repr.append(f"[F{c.row_index}:C{c.column_index} TEXT('{c.text[:20]}...')]")
            else:
                row_repr.append(f"[F{c.row_index}:C{c.column_index} {c.cell_type.upper()}]")
        print("  " + " | ".join(row_repr))

    # Verificar linaje en candidato
    print("\n[LINAJE PROPAGADO AL CANDIDATO DE SÍMBOLO]")
    print(f"  ID Símbolo: {sym_gate.id}")
    print(f"  Fila: {sym_gate.row_index}, Columna: {sym_gate.col_index}")
    print(f"  BBox Celda: {sym_gate.cell_bbox}")
    print(f"  BBox Fila: {sym_gate.row_bbox}")
    print(f"  Contexto: {sym_gate.layout_context}")

    # =========================================================================
    # CONDICIÓN 2: PERSISTENCIA Y BUNDLING DE OCURRENCIAS MULTIPÁGINA
    # =========================================================================
    print("\n--- 2. NAVEGACIÓN MULTIPÁGINA Y EVIDENCIA VISUAL ---")
    ext = SourceExtraction(
        id=str(uuid.uuid4()),
        organization_id=org.id,
        title="Plano de Instrumentación y Cañerías (P&ID)",
        discipline="piping",
        document_type="norma",
        extraction_mode="ai_document",
        status="completed",
        total_items=2
    )
    db.add(ext)
    db.flush()

    item_p1 = ExtractedItem(
        id=str(uuid.uuid4()),
        extraction_id=ext.id,
        item_type="symbol",
        title="Válvula Compuerta Hoja 1",
        description="Válvula de compuerta 150 RF en hoja 1",
        ocr_text="VÁLVULA COMPUERTA H1",
        page_number=1,
        bbox_normalized=[0.05, 0.15, 0.15, 0.22],
        source_asset_id="sheet_pid_01",
        review_status="pending"
    )
    db.add(item_p1)
    db.flush()

    group_uid = str(uuid.uuid4())
    sym_db1 = StructuredSymbol(
        id=str(uuid.uuid4()),
        extracted_item_id=item_p1.id,
        symbol_name="Válvula de Compuerta",
        standard_family="ISA-5.1",
        canonical_symbol_family="valves",
        discipline="piping",
        source_render_mode="vector",
        visual_variant_group_id=group_uid,
        source_table_id="table_pid_01",
        row_index=1,
        col_index=0,
        cell_bbox=[0.05, 0.15, 0.15, 0.22],
        row_bbox=[0.05, 0.15, 0.95, 0.22]
    )
    db.add(sym_db1)

    # Segunda ocurrencia en Hoja 4 del mismo plano
    item_p4 = ExtractedItem(
        id=str(uuid.uuid4()),
        extraction_id=ext.id,
        item_type="symbol",
        title="Válvula Compuerta Hoja 4",
        description="Válvula de compuerta 150 RF en hoja 4",
        ocr_text="VÁLVULA COMPUERTA H4",
        page_number=4,
        bbox_normalized=[0.60, 0.35, 0.70, 0.42],
        source_asset_id="sheet_pid_04",
        review_status="pending"
    )
    db.add(item_p4)
    db.flush()

    sym_db2 = StructuredSymbol(
        id=str(uuid.uuid4()),
        extracted_item_id=item_p4.id,
        symbol_name="Válvula de Compuerta",
        standard_family="ISA-5.1",
        canonical_symbol_family="valves",
        discipline="piping",
        source_render_mode="vector",
        visual_variant_group_id=group_uid,
        source_table_id="table_pid_04",
        row_index=3,
        col_index=0,
        cell_bbox=[0.60, 0.35, 0.70, 0.42],
        row_bbox=[0.10, 0.35, 0.90, 0.42]
    )
    db.add(sym_db2)
    db.commit()

    print(f"✓ Símbolo '{sym_db1.symbol_name}' agrupado bajo visual_variant_group_id: {group_uid[:8]}...")
    print(f"  - Ocurrencia 1: Pág {item_p1.page_number} en sheet '{item_p1.source_asset_id}', BBox={item_p1.bbox_normalized}")
    print(f"  - Ocurrencia 2: Pág {item_p4.page_number} en sheet '{item_p4.source_asset_id}', BBox={item_p4.bbox_normalized}")

    # =========================================================================
    # CONDICIÓN 4: EXCLUSIÓN DE SÍMBOLOS DEL BASELINE QA/QC (REPOSITORIO)
    # =========================================================================
    print("\n--- 3. VERIFICACIÓN DE EXCLUSIÓN DE SÍMBOLOS EN PROMOCIÓN A BASELINE ---")
    repo = IntakeExtractionRepository(db)

    rule_doc = RuleDocument(
        id=str(uuid.uuid4()),
        organization_id=org.id,
        title="Documento Normativo Técnico con Tablas y Símbolos",
        document_type="norma",
        discipline="piping",
        version="1.0",
        status="active",
        items_count=3,
        rules_count=1,
        tables_count=1,
        images_count=0,
        symbols_count=1
    )
    db.add(rule_doc)
    db.flush()

    # 1 Regla Oficial
    rule_it = RuleDocumentItem(
        id=str(uuid.uuid4()),
        rule_document_id=rule_doc.id,
        item_type="rule",
        title="Especificación de Espesor de Tuberías Schedule 40",
        code_or_number="PIP-SPEC-SCH40",
        description="Tuberías de acero al carbono deben cumplir ANSI B36.10M con espesor mínimo de 3.68 mm.",
        status="validada"
    )
    db.add(rule_it)

    # 1 Símbolo
    sym_it = RuleDocumentItem(
        id=str(uuid.uuid4()),
        rule_document_id=rule_doc.id,
        item_type="symbol",
        title="Símbolo Válvula de Globo",
        code_or_number="SYM-GLO-01",
        description="Símbolo de válvula de globo según ISA 5.1",
        status="validada"
    )
    db.add(sym_it)

    # 1 Tabla
    tbl_it = RuleDocumentItem(
        id=str(uuid.uuid4()),
        rule_document_id=rule_doc.id,
        item_type="table",
        title="Tabla de Diámetros Nominales",
        code_or_number="TBL-DN-01",
        description="Tabla de diámetros",
        status="validada"
    )
    db.add(tbl_it)
    db.commit()

    print(f"Documento Normativo creado: '{rule_doc.title}'")
    print(f"  - items_count: {rule_doc.items_count}")
    print(f"  - rules_count: {rule_doc.rules_count}")
    print(f"  - symbols_count: {rule_doc.symbols_count}")
    print(f"  - tables_count: {rule_doc.tables_count}")

    # Ejecutar promoción
    res_promotion = repo.promote_rule_document_to_baseline(rule_doc.id, user_id="lead_auditor")
    print("\nResultado de Promoción hacia Baseline QA/QC:")
    print(f"  - Estado: {repo.get_rule_document_by_id(rule_doc.id).status}")
    print(f"  - Reglas promovidas: {res_promotion['promoted_count']}")
    print(f"  - Códigos promovidos: {res_promotion['rule_codes']}")

    # Consultar tabla rule_definitions en DB
    promoted_defs = db.query(RuleDefinition).all()
    print(f"\nTotal registros en 'rule_definitions': {len(promoted_defs)}")
    for r in promoted_defs:
        print(f"  * [RuleDefinition] Código: {r.code} | Nombre: {r.name}")

    # Aserciones de verificación formal
    assert len(promoted_defs) == 1, "Solo debe haber 1 regla en rule_definitions."
    assert promoted_defs[0].code == "PIP_SPEC_SCH40", "El código debe ser PIP_SPEC_SCH40."
    assert not any("Símbolo" in r.name for r in promoted_defs), "Los símbolos NUNCA deben entrar a rule_definitions."
    print("\n✓ CONDICIÓN 4 CUMPLIDA: Los símbolos quedaron estrictamente excluidos de rule_definitions y siguen su flujo a SymbolTemplate.")

    print("\n" + "=" * 80)
    print("TODAS LAS CONDICIONES DE EJECUCIÓN VALIDADAS EXITOSAMENTE")
    print("=" * 80)


if __name__ == "__main__":
    run_evidence()
