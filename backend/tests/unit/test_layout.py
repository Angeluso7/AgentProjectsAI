import pytest
from app.db.models.document_memory import Document, DocumentSheet, ExtractedText, SheetRegion, TitleBlockExtraction
from app.db.models.template_memory import TitleBlockTemplate

def test_layout_segmentation_and_title_block_extraction(client, db_session):
    """Verifica la segmentación de layout, detección de viñeta y extracción de metadatos estructurados."""
    # 1. Crear proyecto
    proj_res = client.post("/api/v1/projects/", json={
        "code": "PRJ-LAYOUT-001",
        "name": "Proyecto Para Test Layout",
        "discipline": "architecture"
    })
    assert proj_res.status_code == 201
    project_id = proj_res.json()["id"]

    # 2. Crear documento y hoja
    doc = Document(
        project_id=project_id,
        filename="plano_layout_test.pdf",
        file_path="dummy_path.pdf",
        file_hash_sha256="hash_layout_test_001",
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
        sheet_code="SHEET-01",
        title="Lámina Provisional",
        width_px=8000,
        height_px=6000,
        dpi=150,
        raster_image_path="dummy_render.png"
    )
    db_session.add(sheet)
    db_session.commit()
    db_session.refresh(sheet)

    # 3. Crear plantilla en template_memory
    tb_tpl = TitleBlockTemplate(
        name="Test-A0-Template",
        client_or_standard="ISO-General",
        discipline="architecture",
        relative_position="bottom_right",
        expected_bbox=[0.70, 0.70, 0.98, 0.98],
        field_anchors={
            "sheet_code": ["PLANO N°", "CODIGO"],
            "scale": ["ESCALA", "ESC."],
            "revision": ["REV", "REVISION"]
        }
    )
    db_session.add(tb_tpl)
    db_session.commit()

    # 4. Insertar textos OCR en la esquina inferior derecha con datos de viñeta
    texts = [
        ExtractedText(
            sheet_id=sheet.id,
            text="PLANO N°: ARQ-101",
            clean_text="PLANO N°: ARQ-101",
            bbox=[6000.0, 4800.0, 7500.0, 5000.0],
            bbox_normalized=[0.75, 0.80, 0.9375, 0.833],
            confidence=0.98,
            source="vector_pdf"
        ),
        ExtractedText(
            sheet_id=sheet.id,
            text="ESCALA: 1:50",
            clean_text="ESCALA: 1:50",
            bbox=[6000.0, 5100.0, 7200.0, 5250.0],
            bbox_normalized=[0.75, 0.85, 0.90, 0.875],
            confidence=0.99,
            source="vector_pdf"
        ),
        ExtractedText(
            sheet_id=sheet.id,
            text="REVISION: C",
            clean_text="REVISION: C",
            bbox=[6000.0, 5300.0, 7000.0, 5450.0],
            bbox_normalized=[0.75, 0.883, 0.875, 0.908],
            confidence=0.96,
            source="vector_pdf"
        ),
        ExtractedText(
            sheet_id=sheet.id,
            text="PLANTA PRIMER PISO Y ACCESOS",
            clean_text="PLANTA PRIMER PISO Y ACCESOS",
            bbox=[6000.0, 4500.0, 7800.0, 4700.0],
            bbox_normalized=[0.75, 0.75, 0.975, 0.783],
            confidence=0.97,
            source="vector_pdf"
        )
    ]
    db_session.add_all(texts)
    db_session.commit()

    # 5. Ejecutar layout sobre la lámina mediante endpoint
    res = client.post(f"/api/v1/layout/sheets/{sheet.id}", json={"force_reprocess": True})
    assert res.status_code == 200
    data = res.json()
    assert data["regions_count"] >= 2
    tb_data = data["title_block"]
    assert tb_data["sheet_code"] == "ARQ-101"
    assert tb_data["scale"] == "1:50"
    assert tb_data["revision"] == "C"
    assert tb_data["match_score"] > 0.60
    assert tb_data["status"] == "extracted"

    # 6. Consultar regiones por endpoint
    regions_res = client.get(f"/api/v1/layout/sheets/{sheet.id}/regions")
    assert regions_res.status_code == 200
    regions = regions_res.json()
    assert len(regions) >= 2
    assert any(r["region_type"] == "title_block" for r in regions)
    assert any(r["region_type"] == "drawing_area" for r in regions)

    # 7. Consultar title-block por endpoint
    tb_res = client.get(f"/api/v1/layout/sheets/{sheet.id}/title-block")
    assert tb_res.status_code == 200
    tb_record = tb_res.json()
    assert tb_record["sheet_code"] == "ARQ-101"

    # 8. Validar idempotencia de reproceso
    res_2 = client.post(f"/api/v1/layout/sheets/{sheet.id}", json={"force_reprocess": False})
    assert res_2.status_code == 200
    assert res_2.json()["regions_count"] == data["regions_count"]

    # Verificar que en base de datos no se hayan multiplicado las regiones
    regions_in_db = db_session.query(SheetRegion).filter(SheetRegion.sheet_id == sheet.id).all()
    assert len(regions_in_db) == len(regions)

def test_layout_fallback_when_no_title_block(client, db_session):
    """Verifica que si no hay textos de viñeta se genere una región fallback sin fallar."""
    proj_res = client.post("/api/v1/projects/", json={
        "code": "PRJ-EMPTY-001",
        "name": "Proyecto Vacio Layout",
        "discipline": "architecture"
    })
    project_id = proj_res.json()["id"]

    doc = Document(
        project_id=project_id,
        filename="plano_vacio.pdf",
        file_path="dummy_empty.pdf",
        file_hash_sha256="hash_empty_001",
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
        width_px=5000,
        height_px=4000,
        dpi=150
    )
    db_session.add(sheet)
    db_session.commit()
    db_session.refresh(sheet)

    res = client.post(f"/api/v1/layout/sheets/{sheet.id}", json={"force_reprocess": True})
    assert res.status_code == 200
    data = res.json()
    assert data["regions_count"] >= 1
    assert data["title_block"]["status"] == "not_found"
