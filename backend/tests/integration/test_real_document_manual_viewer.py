import os
import io
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal
from app.db.models.intake import SourceAsset
from app.db.models.intake_extractions import SourceExtraction, ExtractedItem, RuleDocument, RuleDocumentItem

client = TestClient(app)

@pytest.fixture
def test_db():
    db = SessionLocal()
    yield db
    db.close()

def test_real_document_manual_viewer_flow(test_db):
    """
    Prueba integral del Visor Documental Real SIN IA / Manual Asistido:
    1. Carga de documento PDF real.
    2. Renderizado de páginas reales (GET /sources/{id}/pages).
    3. Recorte preciso con botón Imagen (POST /sources/{id}/crop) con tipos (tabla, figura, símbolo).
    4. Extracción y resumen con botón Texto (POST /sources/summarize-rule).
    5. Incorporación al Motor de Reglas QA/QC (commit).
    """
    # 1. Subir PDF real
    pdf_bytes = (
        b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
        b"xref\n0 4\n0000000000 65535 f\n0000000010 00000 n\n0000000060 00000 n\n0000000117 00000 n\n"
        b"trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n180\n%%EOF"
    )
    
    files = {
        'file': ('Manual_OGUC_Accesibilidad.pdf', io.BytesIO(pdf_bytes), 'application/pdf')
    }
    form_data = {
        'title': 'Manual OGUC - Criterios de Accesibilidad y Seguridad',
        'source_type': 'normative_document',
        'discipline': 'Arquitectura',
        'document_type': 'norma',
        'authority': 'MINVU'
    }
    
    res_upload = client.post("/api/v1/intake/sources/upload", data=form_data, files=files)
    assert res_upload.status_code == 201
    source_id = res_upload.json()["id"]

    # 2. Obtener páginas reales para el visor continuo
    res_pages = client.get(f"/api/v1/intake/sources/{source_id}/pages")
    assert res_pages.status_code == 200
    pages_data = res_pages.json()
    assert pages_data["total_pages"] >= 1
    assert pages_data["file_exists"] is True
    assert len(pages_data["pages"]) >= 1
    assert pages_data["pages"][0]["image_url"].startswith("/data/intake_sources/")

    # 3. Flujo Botón "Imagen": Recortar región y clasificar (ej: tabla o figura)
    crop_payload = {
        "page_number": 1,
        "bbox": [0.1, 0.2, 0.7, 0.5],
        "title": "Figura 1: Detalle Rampa Accesible",
        "item_type": "figura"
    }
    res_crop = client.post(f"/api/v1/intake/sources/{source_id}/crop", json=crop_payload)
    assert res_crop.status_code == 200
    crop_data = res_crop.json()
    assert crop_data["crop_image_url"].startswith("/data/intake_sources/")
    assert crop_data["crop_image_base64"] is not None

    # 4. Flujo Botón "Texto": Resumir texto a formato de regla
    sum_payload = {
        "text_content": "Art. 4.1.7 Las rampas de acceso no podrán superar una pendiente máxima del 8% y su ancho libre mínimo será de 1.20 m.",
        "discipline": "Arquitectura",
        "title": "OGUC Accesibilidad",
        "item_type": "rule"
    }
    res_sum = client.post("/api/v1/intake/sources/summarize-rule", json=sum_payload)
    assert res_sum.status_code == 200
    sum_data = res_sum.json()
    assert "8%" in sum_data["rule_statement"] or "1.20 m" in sum_data["rule_statement"]
    assert len(sum_data["extracted_parameters"]) > 0

    # 5. Crear sesión manual y registrar ambos elementos (Imagen y Texto)
    session_res = client.post("/api/v1/intake/extractions/create-manual", json={
        "title": "Sesión Manual Asistida OGUC",
        "document_type": "norma",
        "discipline": "Arquitectura",
        "source_asset_id": source_id
    })
    assert session_res.status_code == 201
    extraction_id = session_res.json()["id"]

    # Agregar elemento Imagen
    item_img = client.post(f"/api/v1/intake/extractions/{extraction_id}/items", json={
        "item_type": "figura",
        "title": "Figura 1: Detalle Rampa Accesible",
        "description": "Detalle técnico de pendiente máxima 8%",
        "crop_image_path": crop_data["crop_image_url"],
        "bbox_normalized": crop_data["bbox"],
        "page_number": 1,
        "target_destination": "rules_engine",
        "review_status": "accepted"
    })
    assert item_img.status_code == 201

    # Agregar elemento Texto / Regla
    item_txt = client.post(f"/api/v1/intake/extractions/{extraction_id}/items", json={
        "item_type": "rule",
        "title": sum_data["rule_code"],
        "code_or_number": sum_data["rule_code"],
        "description": sum_data["rule_statement"],
        "ocr_text": sum_payload["text_content"],
        "content_text": sum_data["rule_statement"],
        "bbox_normalized": [0.1, 0.6, 0.9, 0.8],
        "page_number": 1,
        "target_destination": "rules_engine",
        "review_status": "accepted"
    })
    assert item_txt.status_code == 201

    # 6. Commit al Motor de Reglas QA/QC
    commit_res = client.post(f"/api/v1/intake/extractions/{extraction_id}/commit", json={
        "target_rule_document_title": "Manual OGUC Accesibilidad (Incorporado)",
        "target_rule_document_description": "Documento con figura y regla capturadas manualmente."
    })
    assert commit_res.status_code == 200
    commit_data = commit_res.json()
    assert commit_data["rules_incorporated_count"] == 2
    assert commit_data["rule_document_id"] is not None

    # 7. Verificar que el documento normativo está en el Motor de Reglas
    rule_doc_res = client.get(f"/api/v1/rules/documents/{commit_data['rule_document_id']}")
    assert rule_doc_res.status_code == 200
    assert len(rule_doc_res.json()["items"]) == 2
