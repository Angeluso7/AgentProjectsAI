import pytest
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

    # 3. Invocar detección síncrona
    res = client.post(f"/api/v1/symbols/sheets/{sheet.id}", json={"force_reprocess": True})
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
    async_res = client.post(f"/api/v1/symbols/sheets/{sheet.id}/async")
    assert async_res.status_code == 202
    assert "job_id" in async_res.json()
    assert async_res.json()["status"] == "queued"

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
    symbols = service.detect_sheet_symbols(sheet_id=sheet.id, force_reprocess=True)
    assert len(symbols) > 0

    # Verificar que unknown_symbol_candidate generó ReviewTask
    tasks = db_session.query(ReviewTask).filter(ReviewTask.sheet_id == sheet.id).all()
    assert len(tasks) >= 1
    assert any(t.task_type == "symbol_detection_review" for t in tasks)

    # Verificar que se registraron DecisionTraces
    traces = db_session.query(DecisionTrace).filter(DecisionTrace.sheet_id == sheet.id).all()
    assert len(traces) >= 1
    assert any(tr.trace_type == "symbol_detection" for tr in traces)
