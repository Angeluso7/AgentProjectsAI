import os
import io
import pytest
from PIL import Image, ImageDraw
from app.db.models.document_memory import Document, DocumentSheet, ExtractedText
from app.services.ocr.engines import normalize_and_clamp_bbox, clean_text_string

def test_clean_text_string():
    """Valida normalización de texto y remoción de espacios redundantes."""
    assert clean_text_string("  PLANO DE   ARQUITECTURA \n\n ") == "PLANO DE ARQUITECTURA"
    assert clean_text_string("") == ""

def test_normalize_and_clamp_bbox():
    """Valida que las coordenadas normalizadas permanezcan estrictamente en rango [0.0, 1.0]."""
    px_bbox, norm_bbox = normalize_and_clamp_bbox(
        x0=100.0, y0=200.0, x1=500.0, y1=800.0,
        width_px=1000, height_px=2000
    )
    assert px_bbox == [100.0, 200.0, 500.0, 800.0]
    assert norm_bbox == [0.1, 0.1, 0.5, 0.4]

    # Caso con coordenadas fuera de límites
    _, clamped_norm = normalize_and_clamp_bbox(
        x0=-50.0, y0=0.0, x1=1500.0, y1=3000.0,
        width_px=1000, height_px=2000
    )
    assert clamped_norm[0] == 0.0
    assert clamped_norm[2] == 1.0
    assert clamped_norm[3] == 1.0

def test_get_available_ocr_engines(client):
    """Verifica que el endpoint de motores retorne el diccionario de disponibilidad."""
    res = client.get("/api/v1/ocr/engines")
    assert res.status_code == 200
    data = res.json()
    assert "paddleocr" in data
    assert "tesseract" in data
    assert "vector_pdf" in data

def test_ocr_sheet_pipeline_and_idempotency(client, db_session, tmp_path):
    """Verifica el flujo completo de persistencia, consulta y reprocesamiento de OCR sobre una lámina."""
    # 1. Crear proyecto demo
    proj_res = client.post("/api/v1/projects/", json={
        "code": "PRJ-OCR-001",
        "name": "Proyecto Para Test OCR",
        "discipline": "architecture"
    })
    assert proj_res.status_code == 201
    project_id = proj_res.json()["id"]

    # 2. Crear una imagen PNG sintética en disco
    test_img_path = str(tmp_path / "sheet_sample.png")
    img = Image.new("RGB", (1000, 800), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((100, 100), "PLANO GENERAL DE ARQUITECTURA", fill=(0, 0, 0))
    img.save(test_img_path)

    # 3. Crear documento y hoja en BD
    doc = Document(
        project_id=project_id,
        filename="plano_ocr_test.pdf",
        file_path="dummy_path.pdf",
        file_hash_sha256="abc123hash_ocr_test",
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
        sheet_code="ARQ-01",
        title="Lámina de prueba",
        width_px=1000,
        height_px=800,
        dpi=150,
        raster_image_path=test_img_path
    )
    db_session.add(sheet)
    db_session.commit()
    db_session.refresh(sheet)

    # 4. Insertar bloques de texto OCR simulados para verificar persistencia y endpoints
    sample_text = ExtractedText(
        sheet_id=sheet.id,
        text="PLANO GENERAL DE ARQUITECTURA",
        clean_text="PLANO GENERAL DE ARQUITECTURA",
        bbox=[100.0, 100.0, 450.0, 140.0],
        bbox_normalized=[0.10, 0.125, 0.45, 0.175],
        confidence=0.98,
        angle=0.0,
        source="test_engine"
    )
    db_session.add(sample_text)
    db_session.commit()

    # 5. Consultar textos por hoja
    sheet_texts_res = client.get(f"/api/v1/ocr/sheets/{sheet.id}/texts")
    assert sheet_texts_res.status_code == 200
    texts = sheet_texts_res.json()
    assert len(texts) == 1
    assert texts[0]["text"] == "PLANO GENERAL DE ARQUITECTURA"
    assert texts[0]["bbox_normalized"] == [0.10, 0.125, 0.45, 0.175]

    # 6. Consultar textos por documento
    doc_texts_res = client.get(f"/api/v1/ocr/documents/{doc.id}/texts")
    assert doc_texts_res.status_code == 200
    doc_texts = doc_texts_res.json()
    assert len(doc_texts) == 1

    # 7. Disparar endpoint de OCR sobre la hoja sin forzar (idempotente: no debe duplicar)
    post_res = client.post(f"/api/v1/ocr/sheets/{sheet.id}", json={"force_reprocess": False})
    assert post_res.status_code == 200
    assert len(post_res.json()) == 1

def test_ocr_missing_sheet_returns_404(client):
    """Verifica que solicitar OCR sobre un sheet inexistente retorne 404."""
    res = client.post("/api/v1/ocr/sheets/non-existent-id", json={"force_reprocess": False})
    assert res.status_code == 404
