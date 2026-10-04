import pytest
from app.db.models.document_memory import (
    Document, DocumentSheet, SheetRegion, ExtractedText, ExtractedTable, ExtractedTableCell
)
from app.db.models.operations import ReviewTask, DecisionTrace
from app.services.tables.service import TableService

def test_extract_window_schedule_table(client, db_session):
    """Verifica la extracción estructurada de un Cuadro de Ventanas, sus celdas y su clasificación."""
    # 1. Crear proyecto, documento y lámina
    proj_res = client.post("/api/v1/projects/", json={
        "code": "PRJ-TABLE-001",
        "name": "Proyecto Para Test Tablas",
        "discipline": "architecture"
    })
    proj_data = proj_res.json()
    project_id = proj_data["id"]
    org_id = proj_data.get("organization_id") or "default-org-uuid"

    doc = Document(
        organization_id=org_id,
        project_id=project_id,
        filename="plano_con_cuadro_vanos.pdf",
        file_path="dummy_table_path.pdf",
        file_hash_sha256="hash_table_test_001",
        file_size_bytes=4096,
        status="ready",
        page_count=1
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)

    sheet = DocumentSheet(
        document_id=doc.id,
        sheet_number=1,
        sheet_code="ARQ-02",
        title="Planta y Cuadros",
        width_px=8000,
        height_px=6000,
        dpi=150
    )
    db_session.add(sheet)
    db_session.commit()
    db_session.refresh(sheet)

    # 2. Crear macro-región table_candidate en el plano
    region = SheetRegion(
        sheet_id=sheet.id,
        region_type="table_candidate",
        polygon_points=[[0.60, 0.10], [0.95, 0.10], [0.95, 0.40], [0.60, 0.40]],
        bbox=[4800.0, 600.0, 7600.0, 2400.0],
        bbox_normalized=[0.60, 0.10, 0.95, 0.40],
        confidence=0.95,
        detection_method="hybrid_heuristic"
    )
    db_session.add(region)
    db_session.commit()
    db_session.refresh(region)

    # 3. Insertar textos OCR simulando un cuadro de ventanas
    texts = [
        # Título
        ExtractedText(sheet_id=sheet.id, text="CUADRO DE VENTANAS", bbox=[5000.0, 650.0, 7400.0, 750.0], bbox_normalized=[0.625, 0.108, 0.925, 0.125], confidence=0.98),
        # Fila 0 (Headers)
        ExtractedText(sheet_id=sheet.id, text="TIPO", bbox=[4900.0, 800.0, 5200.0, 900.0], bbox_normalized=[0.612, 0.133, 0.650, 0.150], confidence=0.97),
        ExtractedText(sheet_id=sheet.id, text="ANCHO", bbox=[5300.0, 800.0, 5700.0, 900.0], bbox_normalized=[0.662, 0.133, 0.712, 0.150], confidence=0.99),
        ExtractedText(sheet_id=sheet.id, text="ALTO", bbox=[5800.0, 800.0, 6200.0, 900.0], bbox_normalized=[0.725, 0.133, 0.775, 0.150], confidence=0.98),
        ExtractedText(sheet_id=sheet.id, text="CANTIDAD", bbox=[6300.0, 800.0, 6900.0, 900.0], bbox_normalized=[0.787, 0.133, 0.862, 0.150], confidence=0.96),
        # Fila 1
        ExtractedText(sheet_id=sheet.id, text="V-1", bbox=[4900.0, 1000.0, 5200.0, 1100.0], bbox_normalized=[0.612, 0.166, 0.650, 0.183], confidence=0.95),
        ExtractedText(sheet_id=sheet.id, text="1.50", bbox=[5300.0, 1000.0, 5700.0, 1100.0], bbox_normalized=[0.662, 0.166, 0.712, 0.183], confidence=0.99),
        ExtractedText(sheet_id=sheet.id, text="1.20", bbox=[5800.0, 1000.0, 6200.0, 1100.0], bbox_normalized=[0.725, 0.166, 0.775, 0.183], confidence=0.97),
        ExtractedText(sheet_id=sheet.id, text="4", bbox=[6300.0, 1000.0, 6900.0, 1100.0], bbox_normalized=[0.787, 0.166, 0.862, 0.183], confidence=0.99),
        # Fila 2
        ExtractedText(sheet_id=sheet.id, text="V-2", bbox=[4900.0, 1200.0, 5200.0, 1300.0], bbox_normalized=[0.612, 0.200, 0.650, 0.216], confidence=0.96),
        ExtractedText(sheet_id=sheet.id, text="2.00", bbox=[5300.0, 1200.0, 5700.0, 1300.0], bbox_normalized=[0.662, 0.200, 0.712, 0.216], confidence=0.98),
        ExtractedText(sheet_id=sheet.id, text="1.80", bbox=[5800.0, 1200.0, 6200.0, 1300.0], bbox_normalized=[0.725, 0.200, 0.775, 0.216], confidence=0.98),
        ExtractedText(sheet_id=sheet.id, text="2", bbox=[6300.0, 1200.0, 6900.0, 1300.0], bbox_normalized=[0.787, 0.200, 0.862, 0.216], confidence=0.95),
    ]
    db_session.add_all(texts)
    db_session.commit()

    # 4. Invocar extracción síncrona mediante endpoint
    res = client.post(f"/api/v1/tables/sheets/{sheet.id}", json={"force_reprocess": True})
    assert res.status_code == 200
    tables = res.json()
    assert len(tables) == 1
    table_data = tables[0]

    assert table_data["table_type"] == "window_schedule"
    assert "CUADRO DE VENTANAS" in table_data["title"].upper()
    assert table_data["row_count"] == 3 # Headers + 2 filas de datos
    assert table_data["column_count"] == 4
    assert table_data["confidence"] > 0.75

    table_id = table_data["id"]

    # 5. Consultar celdas estructuradas
    cells_res = client.get(f"/api/v1/tables/{table_id}/cells")
    assert cells_res.status_code == 200
    cells = cells_res.json()
    assert len(cells) == 12 # 3 filas * 4 columnas

    # Verificar que los encabezados tengan is_header=True
    headers = [c for c in cells if c["is_header"]]
    assert len(headers) == 4
    header_texts = [h["text"] for h in headers]
    assert "TIPO" in header_texts
    assert "ANCHO" in header_texts
    assert "ALTO" in header_texts

    # 6. Validar endpoints asíncronos (HTTP 202)
    async_res = client.post(f"/api/v1/tables/sheets/{sheet.id}/async")
    assert async_res.status_code == 202
    assert "job_id" in async_res.json()
    assert async_res.json()["status"] == "queued"

def test_extract_incomplete_table_generates_review_task(client, db_session):
    """Verifica que una tabla con datos incompletos o desconocidos genere una ReviewTask."""
    proj_res = client.post("/api/v1/projects/", json={
        "code": "PRJ-INCOMPLETE-TAB",
        "name": "Proyecto Tabla Incompleta",
        "discipline": "architecture"
    })
    proj_data = proj_res.json()
    project_id = proj_data["id"]
    org_id = proj_data.get("organization_id") or "default-org-uuid"

    doc = Document(
        organization_id=org_id,
        project_id=project_id,
        filename="plano_incompleto.pdf",
        file_path="dummy_path.pdf",
        file_hash_sha256="hash_inc_001",
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
        width_px=4000,
        height_px=3000,
        dpi=150
    )
    db_session.add(sheet)
    db_session.commit()
    db_session.refresh(sheet)

    region = SheetRegion(
        sheet_id=sheet.id,
        region_type="table_candidate",
        polygon_points=[[0.70, 0.70], [0.90, 0.70], [0.90, 0.90], [0.70, 0.90]],
        bbox=[2800.0, 2100.0, 3600.0, 2700.0],
        bbox_normalized=[0.70, 0.70, 0.90, 0.90]
    )
    db_session.add(region)
    db_session.commit()
    db_session.refresh(region)

    # Texto escaso sin estructura
    text = ExtractedText(
        sheet_id=sheet.id,
        text="VALOR AISLADO",
        bbox=[3000.0, 2300.0, 3200.0, 2400.0],
        bbox_normalized=[0.75, 0.76, 0.80, 0.80],
        confidence=0.50
    )
    db_session.add(text)
    db_session.commit()

    service = TableService(db_session)
    tables = service.extract_tables_from_sheet(sheet_id=sheet.id, force_reprocess=True)
    assert len(tables) == 1
    t = tables[0]
    assert t.table_type == "unknown_table"

    # Verificar que se creó ReviewTask
    tasks = db_session.query(ReviewTask).filter(ReviewTask.sheet_id == sheet.id).all()
    assert len(tasks) >= 1
    assert any(task.task_type == "table_structure_review" for task in tasks)
