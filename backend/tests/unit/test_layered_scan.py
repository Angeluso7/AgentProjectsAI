import os
import pytest
import fitz
from app.db.models.core import Project
from app.db.models.document_memory import (
    Document, DocumentSheet, SheetRegion, DetectedSymbol, ExtractedText,
    ExtractedTable, ExtractedTableCell, PipingLine, PipingLineSegment, TitleBlockExtraction
)
from app.db.models.operations import ReviewTask
from app.db.models.decision_memory import ReviewRun, ReviewRunDocument
from app.services.scanning.layered_scan_service import DocumentLayeredScanService
from app.services.operations.service import OperationsService
from app.services.symbols.vector_extractor import VectorSymbolExtractor
from app.services.review.export_service import ReviewExportService
import openpyxl


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


def test_manual_piping_line_crud_api(client, db_session, test_setup_project_and_sheet):
    """Verifica endpoints GET, POST y DELETE para trazado manual de PipingLine."""
    proj, doc, sheet = test_setup_project_and_sheet

    # 1. POST crear línea trazada manualmente
    create_payload = {
        "polyline_points": [[0.1, 0.2], [0.4, 0.2], [0.4, 0.6]],
        "line_number": "03-4\"-SS304-001",
        "nominal_size": "4\"",
        "service_fluid": "P",
        "spec_class": "SS304",
        "insulation": "N",
        "from_equipment_tag": "TK-101",
        "to_equipment_tag": "P-102",
        "flow_direction": "forward"
    }
    res_post = client.post(f"/api/v1/symbols/sheets/{sheet.id}/piping-lines", json=create_payload)
    assert res_post.status_code == 201
    created_line = res_post.json()
    line_id = created_line["id"]
    assert created_line["line_number"] == "03-4\"-SS304-001"
    assert created_line["source"] == "manual_trace"
    assert created_line["confidence_status"] == "manual_confirmed"
    assert len(created_line["segments"]) == 1
    assert created_line["segments"][0]["polyline_points"] == [[0.1, 0.2], [0.4, 0.2], [0.4, 0.6]]

    # 2. GET listar líneas de la lámina
    res_get = client.post(f"/api/v1/symbols/sheets/{sheet.id}/piping-lines", json=create_payload) if False else client.get(f"/api/v1/symbols/sheets/{sheet.id}/piping-lines")
    assert res_get.status_code == 200
    lines_list = res_get.json()
    assert len(lines_list) >= 1
    assert any(l["id"] == line_id for l in lines_list)

    # 3. DELETE eliminar línea de piping
    res_del = client.delete(f"/api/v1/symbols/piping-lines/{line_id}")
    assert res_del.status_code == 200
    assert res_del.json()["id"] == line_id

    # Verificar que ya no exista
    res_after = client.get(f"/api/v1/symbols/sheets/{sheet.id}/piping-lines")
    assert not any(l["id"] == line_id for l in res_after.json())


def test_phase_4_sequential_symbol_ordering_upstream_downstream(db_session, test_setup_project_and_sheet):
    """
    Fase 4: Verifica la proyección paramétrica t (0->1) y el ordenamiento secuencial
    de símbolos 'inline' a lo largo de una tubería tanto aguas arriba como aguas abajo.
    """
    proj, doc, sheet = test_setup_project_and_sheet
    scan_service = DocumentLayeredScanService(db_session)
    vec_extractor = VectorSymbolExtractor()

    # 1. Crear PipingLine y su segmento horizontal de x=0.1 a x=0.9 en y=0.5
    pline = PipingLine(
        project_id=proj.id,
        line_number="10-6\"-P-001",
        flow_direction="forward",
        source="auto_vector_extraction",
        confidence_status="auto_high",
        attributes={}
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
        length_mm=400.0,
        connected_symbol_ids=[]
    )
    db_session.add(seg)
    db_session.commit()
    db_session.refresh(seg)

    # 2. Probar VectorSymbolExtractor.compute_symbol_projection_t
    bbox_start = [0.18, 0.48, 0.22, 0.52]  # Centro en x=0.20 -> t = (0.2 - 0.1) / (0.9 - 0.1) = 0.1 / 0.8 = 0.125
    bbox_mid = [0.48, 0.48, 0.52, 0.52]    # Centro en x=0.50 -> t = (0.5 - 0.1) / 0.8 = 0.4 / 0.8 = 0.500
    bbox_end = [0.78, 0.48, 0.82, 0.52]    # Centro en x=0.80 -> t = (0.8 - 0.1) / 0.8 = 0.7 / 0.8 = 0.875

    t_start = vec_extractor.compute_symbol_projection_t(bbox_start, seg.polyline_points)
    t_mid = vec_extractor.compute_symbol_projection_t(bbox_mid, seg.polyline_points)
    t_end = vec_extractor.compute_symbol_projection_t(bbox_end, seg.polyline_points)

    assert abs(t_start - 0.125) < 0.01
    assert abs(t_mid - 0.500) < 0.01
    assert abs(t_end - 0.875) < 0.01

    # 3. Crear 3 DetectedSymbol y evaluar con Capa 2
    s_inlet = DetectedSymbol(
        document_id=doc.id,
        sheet_id=sheet.id,
        symbol_type="gate_valve_inlet",
        discipline="piping",
        bbox_normalized=bbox_start,
        confidence=0.92,
        attributes={}
    )
    s_control = DetectedSymbol(
        document_id=doc.id,
        sheet_id=sheet.id,
        symbol_type="control_valve",
        discipline="piping",
        bbox_normalized=bbox_mid,
        confidence=0.95,
        attributes={}
    )
    s_outlet = DetectedSymbol(
        document_id=doc.id,
        sheet_id=sheet.id,
        symbol_type="check_valve_outlet",
        discipline="piping",
        bbox_normalized=bbox_end,
        confidence=0.89,
        attributes={}
    )
    db_session.add_all([s_inlet, s_control, s_outlet])
    db_session.commit()

    # Ejecutar Capa 2 del escaneo por capas
    syms, conf = scan_service._layer_2_symbols_in_corridor(
        sheet=sheet,
        piping_lines=[pline],
        pw=1000.0,
        ph=1000.0
    )

    db_session.refresh(s_inlet)
    db_session.refresh(s_control)
    db_session.refresh(s_outlet)

    assert s_inlet.attributes.get("piping_line_relation") == "inline"
    assert s_control.attributes.get("piping_line_relation") == "inline"
    assert s_outlet.attributes.get("piping_line_relation") == "inline"

    assert s_inlet.attributes.get("sequence_position") is not None
    assert s_control.attributes.get("sequence_position") is not None
    assert s_outlet.attributes.get("sequence_position") is not None

    assert s_inlet.attributes["sequence_position"] < s_control.attributes["sequence_position"] < s_outlet.attributes["sequence_position"]

    # 4. Probar ordenamiento aguas arriba -> aguas abajo
    ordered_forward = scan_service.get_ordered_symbols_for_line(pline.id, flow_direction="forward")
    assert [s.symbol_type for s in ordered_forward] == ["gate_valve_inlet", "control_valve", "check_valve_outlet"]

    # 5. Probar ordenamiento inverso (flujo reverso)
    ordered_reverse = scan_service.get_ordered_symbols_for_line(pline.id, flow_direction="reverse")
    assert [s.symbol_type for s in ordered_reverse] == ["check_valve_outlet", "control_valve", "gate_valve_inlet"]


def test_phase_5_export_line_list_and_layered_scan_sections(db_session, test_setup_project_and_sheet):
    """
    Fase 5: Verifica la generación de reportes con la tabla 'Line List', secciones de
    leyendas (Capa 5), notas técnicas (Capa 6) y metadatos de cajetín (Capa 7) en XLSX y PDF.
    """
    proj, doc, sheet = test_setup_project_and_sheet

    # 1. Crear ReviewRun y vincular documento
    run = ReviewRun(
        project_id=proj.id,
        run_name="Auditoría P&ID con Line List",
        execution_mode="production",
        status="succeeded",
        summary_stats={"passed": 5, "failed": 0, "warning": 1, "not_evaluable": 2}
    )
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)

    r_doc = ReviewRunDocument(
        review_run_id=run.id,
        document_id=doc.id,
        status="completed",
        document_role="primary"
    )
    db_session.add(r_doc)

    # 2. Crear datos de PipingLine
    pline = PipingLine(
        project_id=proj.id,
        line_number="01-6\"-CS150-001",
        nominal_size="6\"",
        service_fluid="P",
        spec_class="CS150",
        insulation="No",
        from_equipment_tag="TK-101",
        to_equipment_tag="P-101",
        flow_direction="forward",
        source="manual_trace",
        confidence_status="manual_confirmed",
        attributes={}
    )
    db_session.add(pline)
    db_session.commit()
    db_session.refresh(pline)

    seg = PipingLineSegment(
        sheet_id=sheet.id,
        piping_line_id=pline.id,
        polyline_points=[[0.1, 0.2], [0.8, 0.2]],
        bbox_normalized=[0.1, 0.19, 0.8, 0.21],
        line_style="solid",
        length_mm=350.0,
        connected_symbol_ids=[]
    )
    db_session.add(seg)

    # 3. Crear leyenda (Capa 5)
    leg_tbl = ExtractedTable(
        document_id=doc.id,
        sheet_id=sheet.id,
        title="LEYENDA GENERAL DE INSTRUMENTACION",
        table_type="leyenda_simbolos",
        row_count=5,
        column_count=2,
        raw_structure={"is_symbol_legend": True, "description": "Símbolos ISA 5.1"}
    )
    db_session.add(leg_tbl)

    # 4. Crear nota técnica (Capa 6)
    note_txt = ExtractedText(
        sheet_id=sheet.id,
        text="NOTA 1: REVISAR SOLDADURAS SEGUN ASME B31.3 CATEGORIA D",
        confidence=0.98,
        bbox=[100, 200, 400, 220],
        bbox_normalized=[0.1, 0.2, 0.4, 0.22]
    )
    db_session.add(note_txt)

    # 5. Crear cajetín técnico (Capa 7)
    tb_ext = TitleBlockExtraction(
        sheet_id=sheet.id,
        sheet_code="PID-001-REV-A",
        sheet_title="DIAGRAMA DE TUBERIAS E INSTRUMENTACION PLANTA SUR",
        project_name=proj.name,
        revision="A",
        scale_text="S/E",
        discipline="piping",
        date_text="2026-10-10",
        drawn_by="J. PEREZ",
        checked_by="M. GOMEZ",
        approved_by="R. DIAZ",
        raw_fields={"revisions": [{"rev": "A", "date": "2026-10-10", "desc": "EMISION INICIAL"}]}
    )
    db_session.add(tb_ext)
    db_session.commit()

    # 6. Probar generación de reporte XLSX
    report_xlsx = ReviewExportService.create_report(
        db=db_session,
        review_run_id=run.id,
        export_format="xlsx"
    )
    assert report_xlsx is not None
    assert os.path.exists(report_xlsx.artifact_path)

    wb = openpyxl.load_workbook(report_xlsx.artifact_path)
    sheet_names = wb.sheetnames
    assert "Line List" in sheet_names
    assert "Leyendas de Símbolos" in sheet_names
    assert "Notas Técnicas" in sheet_names
    assert "Metadatos Cajetín" in sheet_names

    ws_ll = wb["Line List"]
    # Fila 1 encabezados, Fila 2 datos de la línea
    assert ws_ll.cell(row=2, column=1).value == "01-6\"-CS150-001"
    assert ws_ll.cell(row=2, column=2).value == "6\""
    assert ws_ll.cell(row=2, column=3).value == "P"
    assert ws_ll.cell(row=2, column=4).value == "CS150"
    assert ws_ll.cell(row=2, column=10).value == "MANUAL"

    # 7. Probar generación de reporte PDF
    report_pdf = ReviewExportService.create_report(
        db=db_session,
        review_run_id=run.id,
        export_format="pdf"
    )
    assert report_pdf is not None
    assert os.path.exists(report_pdf.artifact_path)
    assert os.path.getsize(report_pdf.artifact_path) > 1000

    with open(report_pdf.artifact_path, "rb") as f:
        pdf_bytes = f.read()
    assert pdf_bytes.startswith(b"%PDF")


def test_heuristic_classification_leader_line_vs_piping_line(db_session, test_setup_project_and_sheet):
    """
    Fase 2: Valida la heurística de clasificación y desambiguación entre leader-lines y líneas de piping:
    - Caso Claro 1: Leader-line recta, corta (<45mm), trazo fino, conectada a callout.
    - Caso Claro 2: Piping-line larga (>=50mm), trazo grueso.
    - Caso Claro 3: Piping-line corta pero con codo a 90° (presencia de curvas/bends).
    - Caso Ambiguo 4: Longitud intermedia (44mm), recta, con callout -> clasifica a leader_line (evita stubs fantasma).
    - Caso Ambiguo 5: Longitud intermedia (44mm), recta, sin callout -> clasifica a piping_line.
    """
    proj, doc, sheet = test_setup_project_and_sheet
    scan_service = DocumentLayeredScanService(db_session)
    pw, ph = 842.0, 595.0

    # Crear símbolo de callout (globo de instrumento ISA) en coordenadas normalizadas
    callout_sym = DetectedSymbol(
        document_id=doc.id,
        sheet_id=sheet.id,
        symbol_type="instrument_balloon",
        bbox=[168, 119, 210, 149],
        bbox_normalized=[0.20, 0.20, 0.25, 0.25],
        confidence=0.94,
        attributes={"primitive_shape": "circle"}
    )
    db_session.add(callout_sym)
    db_session.commit()
    db_session.refresh(callout_sym)

    from app.services.symbols.vector_extractor import PipingLineCandidateDTO

    # Caso 1: Leader-line clara (recta, 25mm, grosor 0.5pt, conectada al callout)
    cand_leader = PipingLineCandidateDTO(
        polyline_points=[[0.25, 0.225], [0.30, 0.225]],
        bbox_normalized=[0.25, 0.22, 0.30, 0.23],
        line_style="solid",
        length_mm=25.0,
        stroke_width_pt=0.5
    )
    cls_1, meta_1 = scan_service.classify_stroke_candidate(cand_leader, [callout_sym], pw=pw, ph=ph)
    assert cls_1 == "leader_line"
    assert meta_1["decision_rule"] == "clear_leader_line"
    assert meta_1["near_callout"] is True
    assert meta_1["has_bends"] is False

    # Caso 2: Piping-line clara (recta, 120mm, grosor 2.0pt)
    cand_piping = PipingLineCandidateDTO(
        polyline_points=[[0.10, 0.60], [0.80, 0.60]],
        bbox_normalized=[0.10, 0.59, 0.80, 0.61],
        line_style="solid",
        length_mm=120.0,
        stroke_width_pt=2.0
    )
    cls_2, meta_2 = scan_service.classify_stroke_candidate(cand_piping, [callout_sym], pw=pw, ph=ph)
    assert cls_2 == "piping_line"
    assert meta_2["decision_rule"] == "clear_piping_line"

    # Caso 3: Piping-line con codos ortogonales (aunque sea corta)
    cand_elbow = PipingLineCandidateDTO(
        polyline_points=[[0.25, 0.225], [0.28, 0.225], [0.28, 0.260]],
        bbox_normalized=[0.25, 0.225, 0.28, 0.260],
        line_style="solid",
        length_mm=30.0,
        stroke_width_pt=0.8
    )
    cls_3, meta_3 = scan_service.classify_stroke_candidate(cand_elbow, [callout_sym], pw=pw, ph=ph)
    assert cls_3 == "piping_line"
    assert meta_3["has_bends"] is True
    assert meta_3["elbow_count"] >= 1

    # Caso 4 (Ambiguo resuelto a leader_line): longitud 44mm, recto, extremo cerca de callout
    cand_ambig_leader = PipingLineCandidateDTO(
        polyline_points=[[0.25, 0.225], [0.35, 0.225]],
        bbox_normalized=[0.25, 0.22, 0.35, 0.23],
        line_style="solid",
        length_mm=44.0,
        stroke_width_pt=0.8
    )
    cls_4, meta_4 = scan_service.classify_stroke_candidate(cand_ambig_leader, [callout_sym], pw=pw, ph=ph)
    assert cls_4 == "leader_line"
    assert meta_4["decision_rule"] == "ambiguous_resolved_to_leader"

    # Caso 5 (Ambiguo resuelto a piping_line): longitud 44mm, recto, sin callout en extremos
    cand_ambig_piping = PipingLineCandidateDTO(
        polyline_points=[[0.60, 0.80], [0.70, 0.80]],
        bbox_normalized=[0.60, 0.79, 0.70, 0.81],
        line_style="solid",
        length_mm=44.0,
        stroke_width_pt=0.8
    )
    cls_5, meta_5 = scan_service.classify_stroke_candidate(cand_ambig_piping, [callout_sym], pw=pw, ph=ph)
    assert cls_5 == "piping_line"
    assert meta_5["decision_rule"] == "ambiguous_resolved_to_piping"


def test_flow_direction_with_arrow_prioritization_and_conflict_resolution(db_session, test_setup_project_and_sheet):
    """
    Fase 3: Valida la dirección de flujo (flow_direction) en PipingLine:
    - Escenario 1: Línea con flecha clara alineada con orden de trazado -> alta confianza ('forward').
    - Escenario 2: Línea sin flecha -> fallback a orden de trazado con baja confianza ('forward').
    - Escenario 3: Línea con conflicto entre orden de trazado (forward) y flecha física (reverse)
                   -> Prioriza flecha ('reverse'), marca 'flow_direction_conflict=True' y crea ReviewTask HITL.
    """
    proj, doc, sheet = test_setup_project_and_sheet
    scan_service = DocumentLayeredScanService(db_session)
    pw, ph = 842.0, 595.0

    # 1. Escenario 1: Flecha clara alineada (forward)
    pline_1 = PipingLine(
        project_id=proj.id,
        line_number="LINE-FLOW-01",
        flow_direction="unconfirmed",
        source="auto_vector_extraction",
        confidence_status="auto_high",
        attributes={"trace_direction": "forward"}
    )
    db_session.add(pline_1)
    db_session.commit()
    db_session.refresh(pline_1)

    seg_1 = PipingLineSegment(
        sheet_id=sheet.id,
        piping_line_id=pline_1.id,
        polyline_points=[[0.10, 0.30], [0.90, 0.30]], # horizontal hacia derecha (+x)
        bbox_normalized=[0.10, 0.29, 0.90, 0.31],
        line_style="solid",
        length_mm=250.0,
        stroke_width_pt=2.0
    )
    db_session.add(seg_1)

    arrow_sym_1 = DetectedSymbol(
        document_id=doc.id,
        sheet_id=sheet.id,
        symbol_type="flow_direction_arrow",
        bbox=[420, 175, 440, 185],
        bbox_normalized=[0.48, 0.295, 0.52, 0.305],
        confidence=0.91,
        match_rotation_deg=0.0, # apunta a derecha (+x)
        attributes={"rotation_deg": 0.0}
    )
    db_session.add(arrow_sym_1)
    db_session.commit()

    symbols_1, _ = scan_service._layer_2_symbols_in_corridor(
        sheet=sheet,
        piping_lines=[pline_1],
        pw=pw,
        ph=ph
    )
    db_session.refresh(pline_1)
    assert pline_1.flow_direction == "forward"
    assert pline_1.attributes.get("flow_direction_conflict") is False
    assert pline_1.attributes.get("flow_direction_source") == "detected_arrow"
    assert pline_1.attributes.get("flow_direction_confidence") == "high"

    # 2. Escenario 2: Línea sin flecha (fallback a orden de trazado)
    pline_2 = PipingLine(
        project_id=proj.id,
        line_number="LINE-FLOW-02",
        flow_direction="unconfirmed",
        source="auto_vector_extraction",
        confidence_status="auto_high",
        attributes={"trace_direction": "forward"}
    )
    db_session.add(pline_2)
    db_session.commit()
    db_session.refresh(pline_2)

    seg_2 = PipingLineSegment(
        sheet_id=sheet.id,
        piping_line_id=pline_2.id,
        polyline_points=[[0.10, 0.70], [0.90, 0.70]],
        bbox_normalized=[0.10, 0.69, 0.90, 0.71],
        line_style="solid",
        length_mm=250.0,
        stroke_width_pt=2.0
    )
    db_session.add(seg_2)
    db_session.commit()

    symbols_2, _ = scan_service._layer_2_symbols_in_corridor(
        sheet=sheet,
        piping_lines=[pline_2],
        pw=pw,
        ph=ph
    )
    db_session.refresh(pline_2)
    assert pline_2.flow_direction == "forward"
    assert pline_2.attributes.get("arrow_detected") is False
    assert pline_2.attributes.get("flow_direction_source") == "trace_order_fallback"
    assert pline_2.attributes.get("flow_direction_confidence") == "low"

    # 3. Escenario 3: Conflicto entre orden de trazado (forward) y flecha física (reverse)
    pline_3 = PipingLine(
        project_id=proj.id,
        line_number="LINE-FLOW-03",
        flow_direction="unconfirmed",
        source="manual_trace",
        confidence_status="manual_confirmed",
        attributes={"trace_direction": "forward"}
    )
    db_session.add(pline_3)
    db_session.commit()
    db_session.refresh(pline_3)

    seg_3 = PipingLineSegment(
        sheet_id=sheet.id,
        piping_line_id=pline_3.id,
        polyline_points=[[0.10, 0.50], [0.90, 0.50]], # trazado izq -> der (+x)
        bbox_normalized=[0.10, 0.49, 0.90, 0.51],
        line_style="solid",
        length_mm=250.0,
        stroke_width_pt=2.0
    )
    db_session.add(seg_3)

    # Flecha orientada a 180° (apunta a la izquierda, en contra del trazado)
    arrow_sym_reverse = DetectedSymbol(
        document_id=doc.id,
        sheet_id=sheet.id,
        symbol_type="flow_direction_arrow",
        bbox=[420, 295, 440, 305],
        bbox_normalized=[0.48, 0.495, 0.52, 0.505],
        confidence=0.95,
        match_rotation_deg=180.0, # apunta en dirección opuesta (-x)
        attributes={"rotation_deg": 180.0}
    )
    db_session.add(arrow_sym_reverse)
    db_session.commit()

    symbols_3, _ = scan_service._layer_2_symbols_in_corridor(
        sheet=sheet,
        piping_lines=[pline_3],
        pw=pw,
        ph=ph
    )
    db_session.refresh(pline_3)

    # Debe priorizar la flecha ('reverse') sobre el orden manual ('forward')
    assert pline_3.flow_direction == "reverse"
    # Debe marcarse como conflicto y con estado para revisión HITL
    assert pline_3.attributes.get("flow_direction_conflict") is True
    assert pline_3.confidence_status == "auto_low_needs_review"
    assert pline_3.attributes.get("arrow_orientation") == "reverse"
    assert pline_3.attributes.get("trace_order_direction") == "forward"

    # Verificar que se creó la ReviewTask HITL correspondiente
    tasks = db_session.query(ReviewTask).filter(
        ReviewTask.sheet_id == sheet.id,
        ReviewTask.reason_code == "flow_direction_conflict"
    ).all()
    assert len(tasks) >= 1
    assert any(t.payload.get("line_id") == pline_3.id for t in tasks)

