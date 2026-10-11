import pytest
import fitz
from app.db.models.document_memory import Document, DocumentSheet, SheetRegion, DetectedSymbol
from app.db.models.template_memory import SymbolLibrary, SymbolTemplate
from app.db.models.operations import ReviewTask, DecisionTrace
from app.services.symbols.service import SymbolService

def test_detect_symbols_on_sheet(client, db_session):
    """Verifica la detección visual de símbolos sobre la región drawing_area y el resumen por categoría."""
    # 1. Crear proyecto, documento y lámina
    proj_res = client.post("/api/v1/projects/", json={
        "code": "PRJ-SYM-001",
        "name": "Proyecto Para Test Símbolos",
        "discipline": "architecture"
    })
    project_id = proj_res.json()["id"]

    doc = Document(
        project_id=project_id,
        filename="plano_arquitectura_simbolos.pdf",
        file_path="dummy_sym_path.pdf",
        file_hash_sha256="hash_sym_test_001",
        file_size_bytes=8192,
        status="ready",
        page_count=1
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)

    sheet = DocumentSheet(
        document_id=doc.id,
        sheet_number=1,
        sheet_code="ARQ-10",
        title="Planta de Arquitectura y Electricidad",
        width_px=8000,
        height_px=6000,
        dpi=150
    )
    db_session.add(sheet)
    db_session.commit()
    db_session.refresh(sheet)

    # 2. Crear macro-región drawing_area
    drawing_reg = SheetRegion(
        sheet_id=sheet.id,
        region_type="drawing_area",
        polygon_points=[[0.05, 0.05], [0.75, 0.05], [0.75, 0.90], [0.05, 0.90]],
        bbox=[400.0, 300.0, 6000.0, 5400.0],
        bbox_normalized=[0.05, 0.05, 0.75, 0.90],
        confidence=0.98,
        detection_method="hybrid_heuristic"
    )
    db_session.add(drawing_reg)
    db_session.commit()
    db_session.refresh(drawing_reg)

    # 3. Invocar detección síncrona en modo sandbox
    res = client.post(f"/api/v1/symbols/sheets/{sheet.id}", json={"force_reprocess": True, "environment": "sandbox"})
    assert res.status_code == 200
    symbols = res.json()
    assert len(symbols) > 0

    # Validar categorías detectadas
    sym_types = [s["symbol_type"] for s in symbols]
    assert "door_symbol" in sym_types
    assert "window_symbol" in sym_types
    assert "luminaire_symbol" in sym_types
    assert "outlet_symbol" in sym_types

    # Validar coordenadas y normalización
    for s in symbols:
        assert len(s["bbox"]) == 4
        assert len(s["bbox_normalized"]) == 4
        assert 0.0 <= s["bbox_normalized"][0] <= 1.0
        assert s["confidence"] > 0.0

    # 4. Consultar endpoint de resumen agregado
    sum_res = client.get(f"/api/v1/symbols/sheets/{sheet.id}/summary")
    assert sum_res.status_code == 200
    summary = sum_res.json()
    assert summary["sheet_id"] == sheet.id
    assert summary["total_symbols"] == len(symbols)
    assert len(summary["by_category"]) >= 4

    # 5. Endpoint Asíncrono (HTTP 202)
    async_res = client.post(f"/api/v1/symbols/sheets/{sheet.id}/async", json={"environment": "sandbox"})
    assert async_res.status_code == 202
    assert "job_id" in async_res.json()
    assert async_res.json()["status"] == "queued"

def test_production_mode_does_not_generate_synthetic_symbols(client, db_session):
    """Garantiza que en modo 'production' NUNCA se generen símbolos sintéticos placeholder."""
    proj_res = client.post("/api/v1/projects/", json={
        "code": "PRJ-PROD-GUARD",
        "name": "Proyecto Prod Sin Placeholders",
        "discipline": "piping"
    })
    project_id = proj_res.json()["id"]

    doc = Document(
        project_id=project_id,
        filename="dummy_prod.pdf",
        file_path="no_file_exists.pdf",
        file_hash_sha256="hash_prod_001",
        file_size_bytes=1024,
        status="ready",
        page_count=1
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)

    sheet = DocumentSheet(
        document_id=doc.id,
        sheet_number=1,
        width_px=8000,
        height_px=6000,
        dpi=150
    )
    db_session.add(sheet)
    db_session.commit()
    db_session.refresh(sheet)

    service = SymbolService(db_session)
    symbols = service.detect_sheet_symbols(sheet_id=sheet.id, force_reprocess=True, environment="production")
    # En producción sin modelo ni archivo real, debe ser estrictamente lista vacía
    assert symbols == []
    assert len(symbols) == 0

def test_unknown_symbol_candidate_triggers_review_task(client, db_session):
    """Verifica que símbolos inciertos o unknown_symbol_candidate generen ReviewTask y DecisionTrace."""
    proj_res = client.post("/api/v1/projects/", json={
        "code": "PRJ-UNKNOWN-SYM",
        "name": "Proyecto Simbolo Incierto",
        "discipline": "electrical"
    })
    project_id = proj_res.json()["id"]

    doc = Document(
        project_id=project_id,
        filename="plano_con_simbolo_raro.pdf",
        file_path="dummy_path.pdf",
        file_hash_sha256="hash_unknown_sym_001",
        file_size_bytes=2048,
        status="ready",
        page_count=1
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)

    sheet = DocumentSheet(
        document_id=doc.id,
        sheet_number=1,
        width_px=4000,
        height_px=3000,
        dpi=150
    )
    db_session.add(sheet)
    db_session.commit()
    db_session.refresh(sheet)

    service = SymbolService(db_session)
    symbols = service.detect_sheet_symbols(sheet_id=sheet.id, force_reprocess=True, environment="sandbox")
    assert len(symbols) > 0

    # Verificar que unknown_symbol_candidate generó ReviewTask
    tasks = db_session.query(ReviewTask).filter(ReviewTask.sheet_id == sheet.id).all()
    assert len(tasks) >= 1
    assert any(t.task_type == "symbol_detection_review" for t in tasks)

    # Verificar que se registraron DecisionTraces
    traces = db_session.query(DecisionTrace).filter(DecisionTrace.sheet_id == sheet.id).all()
    assert len(traces) >= 1
    assert any(tr.trace_type == "symbol_detection" for tr in traces)


def test_hitl_approval_promotes_symbol_to_canonical(db_session, tmp_path):
    """Verifica Fase 3: la aprobación/corrección en HITL promueve el símbolo a SymbolTemplate canónico."""
    import numpy as np
    import cv2
    from app.services.operations.service import OperationsService
    from app.db.models.template_memory import SymbolTemplate
    from app.db.models.core import Project

    # Generar un crop físico válido para la prueba
    crop_file = tmp_path / "valve_ball_crop.png"
    crop_img = np.ones((64, 64, 3), dtype=np.uint8) * 255
    cv2.circle(crop_img, (32, 32), 16, (0, 0, 0), 2)
    cv2.imwrite(str(crop_file), crop_img)

    proj = Project(
        code="PRJ-HITL-001",
        name="Proyecto HITL",
        discipline="piping"
    )
    db_session.add(proj)
    db_session.commit()

    doc = Document(
        project_id=proj.id,
        filename="hitl_test.pdf",
        file_path="dummy.pdf",
        file_hash_sha256="hitl_hash_1",
        file_size_bytes=1024,
        status="ready",
        page_count=1
    )
    db_session.add(doc)
    db_session.commit()

    sheet = DocumentSheet(
        document_id=doc.id,
        sheet_number=1,
        width_px=1000,
        height_px=1000,
        dpi=150
    )
    db_session.add(sheet)
    db_session.commit()

    sym = DetectedSymbol(
        document_id=doc.id,
        sheet_id=sheet.id,
        symbol_type="unknown_symbol_candidate",
        discipline="piping",
        bbox=[100, 100, 200, 200],
        bbox_normalized=[0.1, 0.1, 0.2, 0.2],
        crop_image_path=str(crop_file),
        confidence=0.62,
        matching_status="unknown_symbol",
        source_engine="vector_symbol_extractor",
        environment="production"
    )
    db_session.add(sym)
    db_session.commit()

    task = ReviewTask(
        task_type="symbol_detection_review",
        reason_code="UNKNOWN_SYMBOL_CANDIDATE",
        reason_message="Símbolo desconocido para revisión humana",
        confidence=0.62,
        priority="high",
        document_id=doc.id,
        sheet_id=sheet.id,
        evidence_refs={"symbol_id": sym.id},
        payload={"symbol_id": sym.id, "symbol_type": "unknown_symbol_candidate", "discipline": "piping"}
    )
    db_session.add(task)
    db_session.commit()

    ops_svc = OperationsService(db_session)
    decision = ops_svc.resolve_review_task(
        task_id=task.id,
        decision="corrected",
        reviewer="lead_engineer",
        corrected_value={"symbol_type": "PIP-VALVE-BALL", "discipline": "piping"},
        notes="Confirmado como válvula de bola en línea 01"
    )

    assert decision is not None
    assert decision.decision == "corrected"
    assert task.status in ["corrected", "resolved"]

    db_session.refresh(sym)
    assert sym.symbol_type == "PIP-VALVE-BALL"
    assert sym.matching_status == "matched"
    assert sym.matched_template_id is not None
    assert sym.match_score == 1.0

    # Verificar que existe la plantilla creada en BD
    created_tpl = db_session.query(SymbolTemplate).filter(SymbolTemplate.id == sym.matched_template_id).first()
    assert created_tpl is not None
    assert "PIP-VALVE-BALL" in created_tpl.display_name or "PIP-VALVE-BALL" in created_tpl.symbol_class or created_tpl.is_active_for_detection


def test_ocr_text_exclusion_and_3mm_margin():
    """Valida que los extractores descarten candidatos que se solapan con texto OCR y apliquen margen de 3mm."""
    from app.services.symbols.vector_extractor import VectorSymbolExtractor, PT_TO_MM
    from app.services.symbols.raster_extractor import RasterSymbolExtractor
    import numpy as np

    vec_extractor = VectorSymbolExtractor()
    rast_extractor = RasterSymbolExtractor()

    # 1. Validación de _overlaps_with_text en vector y raster
    candidate_box = [0.10, 0.10, 0.15, 0.15]
    overlapping_text = [[0.09, 0.09, 0.16, 0.16]]
    non_overlapping_text = [[0.50, 0.50, 0.60, 0.60]]

    assert vec_extractor._overlaps_with_text(candidate_box, overlapping_text) is True
    assert vec_extractor._overlaps_with_text(candidate_box, non_overlapping_text) is False

    assert rast_extractor._overlaps_with_text(candidate_box, overlapping_text) is True
    assert rast_extractor._overlaps_with_text(candidate_box, non_overlapping_text) is False

    # 2. Extracción raster sobre imagen sintética con y sin exclusión de texto OCR
    # Crear imagen blanca de 400x400 con un símbolo técnico hueco de 30x30 (100 a 130)
    img = np.ones((400, 400, 3), dtype=np.uint8) * 255
    img[100:130, 100:102] = 0
    img[100:130, 128:130] = 0
    img[100:102, 100:130] = 0
    img[128:130, 100:130] = 0

    # Sin texto conocido: debe extraer el candidato con margen de 3mm
    cands_no_text = rast_extractor.extract_candidates_from_image(
        image_input=img,
        dpi=150,
        page_number=1,
        known_text_bboxes_norm=None
    )
    assert len(cands_no_text) == 1
    cand = cands_no_text[0]

    # Verificar que el bbox expandido incluye el margen de 3mm (3mm * (150/25.4) ~ 17.7 -> 18px)
    margin_px = int(round(3.0 * (150 / 25.4)))
    assert cand.bbox_pixel[0] == max(0, 100 - margin_px)
    assert cand.bbox_pixel[1] == max(0, 100 - margin_px)
    assert cand.bbox_pixel[2] == min(400, 130 + margin_px)
    assert cand.bbox_pixel[3] == min(400, 130 + margin_px)

    # Con texto OCR que cubre el candidato: debe ser descartado
    text_covering_cand = [[0.24, 0.24, 0.33, 0.33]] # ~100/400=0.25 a 130/400=0.325
    cands_with_text = rast_extractor.extract_candidates_from_image(
        image_input=img,
        dpi=150,
        page_number=1,
        known_text_bboxes_norm=text_covering_cand
    )
    assert len(cands_with_text) == 0


def test_piping_line_extraction_and_symbol_association(db_session, client):
    """
    Fase 4: Verifica la extracción de líneas de piping desde trazos vectoriales,
    la persistencia en PipingLineSegment y la asociación espacial en-línea vs callout.
    """
    from app.services.symbols.vector_extractor import VectorSymbolExtractor
    from app.db.models.document_memory import PipingLineSegment

    vec_extractor = VectorSymbolExtractor()

    # 1. Verificación de lógica geométrica pura
    line_polyline = [[0.1, 0.5], [0.9, 0.5]]
    inline_symbol_bbox = [0.45, 0.48, 0.55, 0.52]      # Cruza la línea en y=0.5
    callout_symbol_bbox = [0.45, 0.10, 0.55, 0.15]     # Lejos de la línea (y=0.10-0.15)

    assert vec_extractor.check_symbol_intersects_line(inline_symbol_bbox, line_polyline) is True
    assert vec_extractor.check_symbol_intersects_line(callout_symbol_bbox, line_polyline) is False

    # 2. Verificación de extracción vectorial con PyMuPDF
    doc = fitz.open()
    page = doc.new_page(width=600, height=400) # ~211mm x 141mm

    # Trazar línea de proceso principal (400 pt ~ 141 mm > umbral de 40mm)
    page.draw_line(fitz.Point(100, 200), fitz.Point(500, 200), color=(0, 0, 0), width=2.0)

    # Trazar línea discontinua de instrumentación secundaria (300 pt ~ 105 mm)
    page.draw_line(fitz.Point(100, 300), fitz.Point(400, 300), color=(0, 0, 1), width=1.0, dashes="[3 3] 0")

    lines = vec_extractor.extract_piping_lines_from_page(page, page_number=1, min_length_mm=40.0)
    assert len(lines) >= 2

    solid_lines = [l for l in lines if l.line_style == "solid"]
    dashed_lines = [l for l in lines if l.line_style == "dashed"]

    assert len(solid_lines) >= 1
    assert len(dashed_lines) >= 1
    assert solid_lines[0].is_main_process_line is True
    assert solid_lines[0].length_mm > 100.0

    # 3. Verificación de persistencia en base de datos con modelo PipingLineSegment
    proj_res = client.post("/api/v1/projects/", json={
        "code": "PRJ-PIPING-LINES",
        "name": "Proyecto Piping Lines Prototype",
        "discipline": "piping"
    })
    project_id = proj_res.json()["id"]

    db_doc = Document(
        project_id=project_id,
        filename="piping_drawing.pdf",
        file_path="dummy_piping.pdf",
        file_hash_sha256="hash_piping_001",
        file_size_bytes=2048,
        status="ready",
        page_count=1
    )
    db_session.add(db_doc)
    db_session.commit()

    db_sheet = DocumentSheet(
        document_id=db_doc.id,
        sheet_number=1,
        width_px=6000,
        height_px=4000,
        dpi=150
    )
    db_session.add(db_sheet)
    db_session.commit()

    # Persistir un segmento de línea
    segment = PipingLineSegment(
        sheet_id=db_sheet.id,
        polyline_points=solid_lines[0].polyline_points,
        bbox_normalized=solid_lines[0].bbox_normalized,
        line_style=solid_lines[0].line_style,
        length_mm=solid_lines[0].length_mm,
        stroke_width_pt=solid_lines[0].stroke_width_pt,
        connected_symbol_ids=["sym_001"],
        is_main_process_line=solid_lines[0].is_main_process_line,
        attributes={"test": True}
    )
    db_session.add(segment)
    db_session.commit()
    db_session.refresh(segment)

    persisted = db_session.query(PipingLineSegment).filter(PipingLineSegment.sheet_id == db_sheet.id).first()
    assert persisted is not None
    assert persisted.length_mm > 100.0
    assert persisted.connected_symbol_ids == ["sym_001"]
    assert persisted.is_main_process_line is True

