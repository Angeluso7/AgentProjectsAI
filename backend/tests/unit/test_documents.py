import io
import os
import pytest
from app.services.ingest.service import FITZ_AVAILABLE, IngestService
from app.db.models.document_memory import Document, DocumentSheet

MINIMAL_PDF_BYTES = (
    b"%PDF-1.4\n"
    b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] >>\nendobj\n"
    b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n"
    b"trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n190\n%%EOF"
)

def test_upload_pdf_basic(client):
    """Verifica la subida de un archivo PDF válido sin auto-procesamiento inmediato."""
    # 1. Crear proyecto previo
    proj_res = client.post("/api/v1/projects/", json={
        "code": "PRJ-DOC-001",
        "name": "Proyecto Para Test Documentos",
        "discipline": "architecture"
    })
    assert proj_res.status_code == 201
    project_id = proj_res.json()["id"]

    # 2. Subir PDF con auto_process=False
    pdf_file = io.BytesIO(MINIMAL_PDF_BYTES)
    res = client.post(
        "/api/v1/documents/upload",
        data={"project_id": project_id, "auto_process": "false"},
        files={"file": ("plano_test.pdf", pdf_file, "application/pdf")}
    )
    assert res.status_code == 201
    doc_data = res.json()
    assert doc_data["filename"] == "plano_test.pdf"
    assert doc_data["status"] == "uploaded"
    assert len(doc_data["file_hash_sha256"]) == 64
    assert doc_data["project_id"] == project_id
    doc_id = doc_data["id"]

    # 3. Obtener detalle de documento por ID
    get_res = client.get(f"/api/v1/documents/{doc_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == doc_id

    # 4. Listar documentos del proyecto
    list_res = client.get(f"/api/v1/documents/?project_id={project_id}")
    assert list_res.status_code == 200
    docs = list_res.json()
    assert len(docs) >= 1
    assert any(d["id"] == doc_id for d in docs)

    # 5. Listar hojas del documento
    sheets_res = client.get(f"/api/v1/documents/{doc_id}/sheets")
    assert sheets_res.status_code == 200
    assert isinstance(sheets_res.json(), list)

def test_upload_invalid_pdf_format(client):
    """Verifica que subir un archivo que no es PDF retorne error 400."""
    proj_res = client.post("/api/v1/projects/", json={
        "code": "PRJ-DOC-002",
        "name": "Proyecto Test Error",
        "discipline": "architecture"
    })
    project_id = proj_res.json()["id"]

    invalid_file = io.BytesIO(b"ESTO NO ES UN PDF VALIDO")
    res = client.post(
        "/api/v1/documents/upload",
        data={"project_id": project_id},
        files={"file": ("archivo.txt", invalid_file, "text/plain")}
    )
    assert res.status_code == 400
    assert "no tiene formato PDF válido" in res.json()["detail"]

def test_upload_empty_file(client):
    """Verifica que subir un archivo vacío retorne error 400."""
    proj_res = client.post("/api/v1/projects/", json={
        "code": "PRJ-DOC-003",
        "name": "Proyecto Test Vacio",
        "discipline": "architecture"
    })
    project_id = proj_res.json()["id"]

    empty_file = io.BytesIO(b"")
    res = client.post(
        "/api/v1/documents/upload",
        data={"project_id": project_id},
        files={"file": ("vacio.pdf", empty_file, "application/pdf")}
    )
    assert res.status_code == 400

@pytest.mark.skipif(not FITZ_AVAILABLE, reason="PyMuPDF no instalado en host local")
def test_real_pdf_processing_and_rasterization(client, db_session):
    """Verifica el procesamiento completo y rasterizado de hojas a imagen cuando PyMuPDF está disponible."""
    proj_res = client.post("/api/v1/projects/", json={
        "code": "PRJ-FITZ-001",
        "name": "Proyecto Test Raster",
        "discipline": "architecture"
    })
    project_id = proj_res.json()["id"]

    pdf_file = io.BytesIO(MINIMAL_PDF_BYTES)
    res = client.post(
        "/api/v1/documents/upload",
        data={"project_id": project_id, "auto_process": "true", "dpi": "100"},
        files={"file": ("plano_raster.pdf", pdf_file, "application/pdf")}
    )
    assert res.status_code == 201
    doc_data = res.json()
    assert doc_data["status"] == "ready"
    assert doc_data["page_count"] == 1
    assert len(doc_data["sheets"]) == 1
    
    sheet = doc_data["sheets"][0]
    assert sheet["sheet_number"] == 1
    assert sheet["dpi"] == 100
    assert sheet["width_px"] > 0
    assert sheet["height_px"] > 0
    assert sheet["raster_image_path"] is not None
    assert os.path.exists(sheet["raster_image_path"])
