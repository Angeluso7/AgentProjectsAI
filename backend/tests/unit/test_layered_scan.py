import os
import pytest
import fitz
from app.db.models.core import Project
from app.db.models.document_memory import (
    Document, DocumentSheet, SheetRegion, DetectedSymbol, ExtractedText,
    ExtractedTable, ExtractedTableCell, PipingLine, PipingLineSegment, TitleBlockExtraction
)
from app.db.models.operations import ReviewTask
from app.services.scanning.layered_scan_service import DocumentLayeredScanService
from app.services.operations.service import OperationsService


@pytest.fixture
def test_setup_project_and_sheet(db_session):
    """Crea un proyecto, documento y lámina base para pruebas del escaneo por capas."""
    proj = Project(
        code=f"PRJ-SCAN-{os.urandom(3).hex().upper()}",
        name="Proyecto de Prueba Escaneo P&ID",
        discipline="piping"
    )
    db_session.add(proj)
    db_session.commit()
    db_session.refresh(proj)

    doc = Document(
        project_id=proj.id,
        filename="pid_unit_test.pdf",
        file_path="dummy_path.pdf",
        file_hash_sha256=f"hash_{os.urandom(4).hex()}",
        file_size_bytes=10240,
        status="ready",
        page_count=1
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)

    sheet = DocumentSheet(
        document_id=doc.id,
        sheet_number=1,
        sheet_code="PID-101",
        title="P&ID Sistema de Bombeo y Proceso",
        width_px=6000,
        height_px=4000,
        dpi=150
    )
    db_session.add(sheet)
    db_session.commit()
    db_session.refresh(sheet)

    return proj, doc, sheet


def test_layer_1_piping_lines_extraction_and_grouping(db_session, test_setup_project_and_sheet):
    """Capa 1: Verifica agrupamiento de segmentos continuos en PipingLine y generación de ReviewTask."""
    proj, doc, sheet = test_setup_project_and_sheet
    scan_service = DocumentLayeredScanService(db_session)

    # Crear synthetic page con fitz
    fitz_doc = fitz.open()
    page = fitz_doc.new_page(width=842, height=595)  # A4 horizontal en puntos
    # Dibujar dos trazos contiguos horizontales
    # Trazo 1: x=100 a x=300 en y=250 (longitud 200pt ~ 70.5mm)
    page.draw_line(fitz.Point(100, 250), fitz.Point(300, 250), color=(0, 0, 0), width=2.0)

    # Trazo 2: x=302 a x=550 en y=250 (extremo cercano ~2pt <= 5mm, longitud 248pt ~ 87.5mm)
    page.draw_line(fitz.Point(302, 250), fitz.Point(550, 250), color=(0, 0, 0), width=2.0)

    drawings = page.get_drawings()
    pw, ph = page.rect.width, page.rect.height

    lines, segments, tasks, conf = scan_service._layer_1_piping_lines(
        sheet=sheet,
        project_id=proj.id,
        page=page,
        cached_drawings=drawings,
        pw=pw,
        ph=ph
    )

    fitz_doc.close()

    assert len(lines) == 1
    assert len(segments) == 2
    pline = lines[0]
    assert pline.project_id == proj.id
    assert pline.flow_direction == "unconfirmed"
    assert pline.source == "auto_vector_extraction"
    assert pline.confidence_status in ("auto_high", "auto_low_needs_review")
    assert pline.attributes["segments_count"] == 2
    assert pline.attributes["buffer_margin_mm"] == 10.0


def test_layer_2_symbols_in_corridor_and_flow_direction(db_session, test_setup_project_and_sheet):
    """Capa 2: Prueba inclusión de símbolos en la franja de 10mm, proyección t paramétrica y flechas de flujo."""
    proj, doc, sheet = test_setup_project_and_sheet
    scan_service = DocumentLayeredScanService(db_session)
    pw, ph = 842.0, 595.0

    # Crear PipingLine con un segmento horizontal normalizado en y = 0.5
    pline = PipingLine(
        project_id=proj.id,
        line_number="01-4\"-P-001",
        flow_direction="unconfirmed",
        source="auto_vector_extraction",
        confidence_status="auto_high"
    )
    db_session.add(pline)
    db_session.commit()
    db_session.refresh(pline)

    seg = PipingLineSegment(
        sheet_id=sheet.id,
        piping_line_id=pline.id,
        polyline_points=[[0.1, 0.5], [0.9, 0.5]],
        bbox_normalized=[0.1, 0.49, 0.9, 0.51],
        line_style="solid",
        length_mm=200.0,
        stroke_width_pt=2.0,
        connected_symbol_ids=[]
    )
    db_session.add(seg)
    db_session.commit()
    db_session.refresh(pline)

    # 1. Símbolo de válvula dentro del buffer (en y=0.5, x=0.3 -> t=0.25)
    valv_sym = DetectedSymbol(
        document_id=doc.id,
        sheet_id=sheet.id,
        symbol_type="ball_valve",
        bbox=[280, 280, 320, 320],
        bbox_normalized=[0.28, 0.48, 0.32, 0.52],
        confidence=0.92,
        attributes={}
    )
    # 2. Símbolo de flecha de flujo dentro del buffer (en y=0.5, x=0.5 -> orientada hacia adelante)
    arrow_sym = DetectedSymbol(
        document_id=doc.id,
        sheet_id=sheet.id,
        symbol_type="flow_direction_arrow",
        bbox=[490, 290, 510, 310],
        bbox_normalized=[0.49, 0.49, 0.51, 0.51],
        confidence=0.88,
        match_rotation_deg=0.0,
        attributes={"rotation_deg": 0.0}
    )
    # 3. Símbolo lejano fuera del buffer (en y=0.1)
    far_sym = DetectedSymbol(
        document_id=doc.id,
        sheet_id=sheet.id,
        symbol_type="centrifugal_pump",
        bbox=[450, 50, 550, 70],
        bbox_normalized=[0.45, 0.08, 0.55, 0.12],
        confidence=0.95,
        attributes={}
    )
    db_session.add_all([valv_sym, arrow_sym, far_sym])
    db_session.commit()

    symbols, conf = scan_service._layer_2_symbols_in_corridor(
        sheet=sheet,
        piping_lines=[pline],
        pw=pw,
        ph=ph
    )

    db_session.refresh(valv_sym)
    db_session.refresh(arrow_sym)
    db_session.refresh(far_sym)
    db_session.refresh(pline)

    # Válvula clasificada como inline con sequence_position
    assert valv_sym.attributes.get("piping_line_relation") == "inline"
    assert valv_sym.attributes.get("piping_line_id") == pline.id
    assert 0.20 <= valv_sym.attributes.get("sequence_position") <= 0.30

    # Flecha de flujo clasificada como inline y actualiza la dirección de la línea
    assert arrow_sym.attributes.get("piping_line_relation") == "inline"
    assert pline.flow_direction == "forward"

    # Símbolo lejano queda como callout_candidate para evaluación posterior
    assert far_sym.attributes.get("piping_line_relation") == "callout_candidate"


def test_layer_3_resolve_callouts_with_leader_lines(db_session, test_setup_project_and_sheet):
    """Capa 3: Resuelve callout_candidate a 'resolved' mediante trazos cortos adyacentes a texto."""
    proj, doc, sheet = test_setup_project_and_sheet
    scan_service = DocumentLayeredScanService(db_session)
    pw, ph = 842.0, 595.0

    # Símbolo callout_candidate ubicado en x=0.5, y=0.5 (421pt, 297.5pt)
    callout_sym = DetectedSymbol(
        document_id=doc.id,
        sheet_id=sheet.id,
        symbol_type="orifice_plate",
        bbox=[400, 280, 440, 310],
        bbox_normalized=[0.48, 0.48, 0.52, 0.52],
        confidence=0.90,
        attributes={"piping_line_relation": "callout_candidate", "callout_leader_line_status": "unresolved_trace"}
    )
    db_session.add(callout_sym)

    # Texto técnico ("FE-101") a 15mm (~42.5pt)
    target_text = ExtractedText(
        sheet_id=sheet.id,
        text="FE-101",
        confidence=0.99,
        bbox=[460, 290, 505, 305],
        bbox_normalized=[0.55, 0.49, 0.60, 0.51]
    )
    db_session.add(target_text)
    db_session.commit()

    # Trazo corto de líder entre el símbolo y el texto (longitud 25pt ~ 8.8mm)
    stroke_rect = fitz.Rect(430, 297, 455, 298)
    cached_drawings = [
        {"rect": stroke_rect, "type": "s"}
    ]

    conf = scan_service._layer_3_resolve_callouts(
        sheet=sheet,
        symbols=[callout_sym],
        cached_drawings=cached_drawings,
        pw=pw,
        ph=ph
    )

    db_session.refresh(callout_sym)
    assert callout_sym.attributes["callout_leader_line_status"] == "resolved"
    assert callout_sym.attributes["callout_target_text"] == "FE-101"
    assert callout_sym.attributes["callout_target_text_id"] == target_text.id


def test_layer_4_outside_symbols_endpoints_association(db_session, test_setup_project_and_sheet):
    """Capa 4: Asocia símbolos fuera de franja cercanos a extremos como from_equipment_tag y to_equipment_tag."""
    proj, doc, sheet = test_setup_project_and_sheet
    scan_service = DocumentLayeredScanService(db_session)
    pw, ph = 842.0, 595.0

    # Línea que va de x=0.2 a x=0.8 en y=0.5
    pline = PipingLine(
        project_id=proj.id,
        line_number="10-8\"-CW-002",
        source="auto_vector_extraction"
    )
    db_session.add(pline)
    db_session.commit()
    db_session.refresh(pline)

    seg = PipingLineSegment(
        sheet_id=sheet.id,
        piping_line_id=pline.id,
        polyline_points=[[0.2, 0.5], [0.8, 0.5]],
        bbox_normalized=[0.2, 0.49, 0.8, 0.51],
        line_style="solid",
        length_mm=180.0,
        stroke_width_pt=2.0
    )
    db_session.add(seg)

    # Tanque TK-200 ubicado a 5mm del inicio (x=0.19, y=0.5)
    tk_sym = DetectedSymbol(
        document_id=doc.id,
        sheet_id=sheet.id,
        symbol_type="storage_tank",
        detected_tag_or_code="TK-200",
        bbox=[150, 280, 170, 310],
        bbox_normalized=[0.18, 0.48, 0.20, 0.52],
        confidence=0.95,
        attributes={"piping_line_relation": "callout_candidate"}
    )
    # Bomba P-200A ubicada a 5mm del final (x=0.81, y=0.5)
    pump_sym = DetectedSymbol(
        document_id=doc.id,
        sheet_id=sheet.id,
        symbol_type="centrifugal_pump",
        detected_tag_or_code="P-200A",
        bbox=[670, 280, 690, 310],
        bbox_normalized=[0.80, 0.48, 0.82, 0.52],
        confidence=0.96,
        attributes={"piping_line_relation": "callout_candidate"}
    )
    db_session.add_all([tk_sym, pump_sym])
    db_session.commit()

    conf = scan_service._layer_4_outside_symbols_endpoints(
        symbols=[tk_sym, pump_sym],
        piping_lines=[pline],
        pw=pw,
        ph=ph
    )

    db_session.refresh(pline)
    db_session.refresh(tk_sym)
    db_session.refresh(pump_sym)

    assert pline.from_equipment_tag == "TK-200"
    assert pline.to_equipment_tag == "P-200A"
    assert tk_sym.attributes.get("piping_line_endpoint") == "from_equipment"
    assert pump_sym.attributes.get("piping_line_endpoint") == "to_equipment"


def test_layer_5_tables_and_legends_classification(db_session, test_setup_project_and_sheet):
    """Capa 5: Clasifica tablas en leyenda vs datos y enruta símbolos a ReviewTask HITL."""
    proj, doc, sheet = test_setup_project_and_sheet
    scan_service = DocumentLayeredScanService(db_session)

    # Crear tabla de leyenda de símbolos
    legend_tbl = ExtractedTable(
        document_id=doc.id,
        sheet_id=sheet.id,
        title="LEYENDA DE INSTRUMENTOS Y SIMBOLOGIA",
        row_count=2,
        column_count=2,
        confidence=0.94,
        table_type="desconocido"
    )
    db_session.add(legend_tbl)
    db_session.commit()
    db_session.refresh(legend_tbl)

    # Celdas: fila 0 encabezado, fila 1 símbolo + descripción
    c00 = ExtractedTableCell(table_id=legend_tbl.id, row_index=0, column_index=0, text="SIMBOLO", is_header=True)
    c01 = ExtractedTableCell(table_id=legend_tbl.id, row_index=0, column_index=1, text="DESCRIPCION", is_header=True)
    c10 = ExtractedTableCell(table_id=legend_tbl.id, row_index=1, column_index=0, has_symbol=True, cell_type="symbol_cell")
    c11 = ExtractedTableCell(table_id=legend_tbl.id, row_index=1, column_index=1, text="Valvula de Compuerta")
    db_session.add_all([c00, c01, c10, c11])
    db_session.commit()

    tables, tasks, conf = scan_service._layer_5_tables_and_legends(sheet=sheet, project_id=proj.id)

    db_session.refresh(legend_tbl)
    assert legend_tbl.table_type == "leyenda_simbolos"
    assert legend_tbl.raw_structure.get("is_symbol_legend") is True
    assert len(tasks) == 1
    rt = tasks[0]
    assert rt.task_type == "symbol_detection_review"
    assert rt.payload["suggested_name"] == "Valvula De Compuerta"


def test_layer_6_notes_extraction_and_referencing(db_session, test_setup_project_and_sheet):
    """Capa 6: Extrae notas técnicas y vincula 'NOTA 3' en atributos de símbolos adyacentes."""
    proj, doc, sheet = test_setup_project_and_sheet
    scan_service = DocumentLayeredScanService(db_session)

    # Texto de nota técnica
    note_text = ExtractedText(
        sheet_id=sheet.id,
        text="NOTA 3: TODAS LAS LINEAS DE DRENAJE DEBEN LLEVAR PENDIENTE 1%",
        confidence=0.98,
        bbox=[600, 800, 800, 830],
        bbox_normalized=[0.70, 0.85, 0.95, 0.88]
    )
    # Texto de llamada de nota cerca del símbolo
    marker_text = ExtractedText(
        sheet_id=sheet.id,
        text="VER NOTA 3",
        confidence=0.95,
        bbox=[350, 470, 390, 490],
        bbox_normalized=[0.42, 0.49, 0.46, 0.51]
    )
    # Símbolo adyacente a la llamada de nota
    sym = DetectedSymbol(
        document_id=doc.id,
        sheet_id=sheet.id,
        symbol_type="drain_valve",
        bbox=[340, 460, 380, 500],
        bbox_normalized=[0.40, 0.48, 0.44, 0.52],
        confidence=0.91,
        attributes={}
    )
    db_session.add_all([note_text, marker_text, sym])
    db_session.commit()

    notes, conf = scan_service._layer_6_notes_and_references(
        sheet=sheet,
        symbols=[sym],
        piping_lines=[]
    )

    assert len(notes) == 1
    assert notes[0]["number"] == "3"
    db_session.refresh(sym)
    refs = sym.attributes.get("referenced_notes", [])
    assert len(refs) == 1
    assert refs[0]["note_number"] == "3"
    assert "PENDIENTE 1%" in refs[0]["note_text"]


def test_layer_7_title_block_metadata_persistence(db_session, test_setup_project_and_sheet):
    """Capa 7: Extrae metadatos del cajetín y actualiza DocumentSheet."""
    proj, doc, sheet = test_setup_project_and_sheet
    scan_service = DocumentLayeredScanService(db_session)

    # Pre-crear TitleBlockExtraction en la lámina
    tb_record = TitleBlockExtraction(
        sheet_id=sheet.id,
        sheet_code="DWG-PID-999",
        sheet_title="Diagrama de Tuberias e Instrumentacion",
        scale_text="S/E",
        revision="B",
        date_text="2026-10-10",
        project_name="Proyecto Minero Sulfuros",
        discipline="Piping",
        drawn_by="J.P.",
        checked_by="M.A.",
        approved_by="R.C.",
        raw_fields={"customer": "Codelco"}
    )
    db_session.add(tb_record)
    db_session.commit()

    meta, conf = scan_service._layer_7_title_block(sheet=sheet)

    db_session.refresh(sheet)
    assert sheet.sheet_code == "DWG-PID-999"
    assert sheet.title == "Diagrama de Tuberias e Instrumentacion"
    assert sheet.scale == "S/E"
    assert sheet.revision == "B"
    assert sheet.date_str == "2026-10-10"
    assert meta["drawn_by"] == "J.P."


def test_operations_service_resolves_line_trace_review(db_session, test_setup_project_and_sheet):
    """Verifica que OperationsService.resolve_review_task actualiza PipingLine al aprobar o corregir un trazo."""
    proj, doc, sheet = test_setup_project_and_sheet
    ops_service = OperationsService(db_session)

    pline = PipingLine(
        project_id=proj.id,
        line_number=None,
        source="auto_vector_extraction",
        confidence_status="auto_low_needs_review"
    )
    db_session.add(pline)
    db_session.commit()
    db_session.refresh(pline)

    seg = PipingLineSegment(
        sheet_id=sheet.id,
        piping_line_id=pline.id,
        polyline_points=[[0.1, 0.1], [0.5, 0.1]],
        bbox_normalized=[0.1, 0.09, 0.5, 0.11],
        line_style="solid",
        length_mm=120.0,
        stroke_width_pt=1.5
    )
    db_session.add(seg)

    task = ReviewTask(
        task_type="line_trace_review",
        reason_code="low_confidence_line_trace",
        reason_message="Trazo automático que requiere confirmación humana",
        sheet_id=sheet.id,
        project_id=proj.id,
        status="open",
        priority="medium",
        payload={"line_id": pline.id},
        evidence_refs={"line_id": pline.id}
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    # Resolver con corrección
    decision = ops_service.resolve_review_task(
        task_id=task.id,
        decision="corrected",
        corrected_value={
            "line_number": "02-8\"-CS-005",
            "nominal_size": "8\"",
            "service_fluid": "CS",
            "spec_class": "150#",
            "flow_direction": "forward"
        },
        reviewer="user_admin"
    )

    assert decision.decision == "corrected"
    db_session.refresh(pline)
    assert pline.source == "manual_corrected"
    assert pline.confidence_status == "manual_confirmed"
    assert pline.line_number == "02-8\"-CS-005"
    assert pline.nominal_size == "8\""
    assert pline.service_fluid == "CS"
    assert pline.flow_direction == "forward"
    db_session.refresh(seg)
    assert seg.attributes.get("review_decision") == "corrected"
