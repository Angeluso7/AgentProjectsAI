import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import io
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.core import Organization, User, OrganizationMembership, Project
from app.core.security import hash_password, create_access_token
from app.services.operations.dispatcher import wait_for_all_jobs


def _get_test_context(client: TestClient, db_session: Session):
    # 1. Crear Organización
    org_id = str(uuid.uuid4())
    org = Organization(
        id=org_id,
        name="Batch Upload Org",
        slug=f"batch-upload-{uuid.uuid4().hex[:6]}"
    )
    db_session.add(org)

    # 2. Crear Usuario y Membresía
    user_id = str(uuid.uuid4())
    user = User(
        id=user_id,
        email=f"lead.auditor.{uuid.uuid4().hex[:6]}@batchtest.com",
        display_name="Lead Auditor",
        password_hash=hash_password("PasswordSeguro123!"),
        is_active=True,
        is_superuser=False
    )
    db_session.add(user)

    membership = OrganizationMembership(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        user_id=user_id,
        role="admin",
        status="active"
    )
    db_session.add(membership)

    # 3. Crear Proyecto
    project_id = str(uuid.uuid4())
    project = Project(
        id=project_id,
        organization_id=org_id,
        code="PRJ-PIP-001",
        name="Proyecto Piloto Piping & Plantas",
        client_name="PetroChemical Corp",
        discipline="piping",
        status="active"
    )
    db_session.add(project)
    db_session.commit()

    # 4. Token JWT
    token = create_access_token(
        subject=user.id,
        email=user.email,
        extra_claims={
            "org_id": org_id,
            "role": "admin"
        }
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Organization-Id": org_id
    }

    return {
        "client": client,
        "headers": headers,
        "org": org,
        "user": user,
        "project": project,
        "db": db_session
    }


def _create_dummy_pdf_bytes(title: str = "Demo Sheet") -> bytes:
    """Genera un archivo PDF sintético válido con PyMuPDF o bytes estándar."""
    import fitz
    doc = fitz.open()
    page = doc.new_page(width=595, height=842) # A4
    page.insert_text((50, 72), f"PLANO TECNICO: {title}", fontsize=14)
    page.insert_text((50, 100), "LINEA PIPING 4-CW-102-CS150", fontsize=10)
    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes


def _create_dummy_png_bytes(width: int = 400, height: int = 300) -> bytes:
    """Genera una imagen PNG sintética válida con Pillow."""
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (width, height), color=(30, 41, 59))
    draw = ImageDraw.Draw(img)
    draw.rectangle([20, 20, width - 20, height - 20], outline=(59, 130, 246), width=3)
    draw.text((30, 30), "ESQUEMA PIPING P&ID", fill=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_single_document_upload_pdf(client: TestClient, db_session: Session):
    """Escenario A1: Carga simple de un plano técnico PDF."""
    ctx = _get_test_context(client, db_session)
    headers = ctx["headers"]
    project_id = ctx["project"].id

    pdf_bytes = _create_dummy_pdf_bytes("Plano Isométrico 01")
    
    files = {
        "file": ("plano_isometrico_01.pdf", pdf_bytes, "application/pdf")
    }
    data = {
        "project_id": project_id,
        "auto_process": "true"
    }

    res = client.post("/api/v1/documents/upload", headers=headers, data=data, files=files)
    assert res.status_code == 201, f"Error: {res.text}"
    doc_data = res.json()
    assert doc_data["filename"] == "plano_isometrico_01.pdf"
    assert doc_data["project_id"] == project_id
    assert doc_data["status"] == "ready"
    assert doc_data["page_count"] == 1
    assert len(doc_data["sheets"]) == 1
    assert doc_data["sheets"][0]["sheet_number"] == 1


def test_single_document_upload_image(client: TestClient, db_session: Session):
    """Escenario A2: Carga simple de un plano/croquis en formato imagen PNG."""
    ctx = _get_test_context(client, db_session)
    headers = ctx["headers"]
    project_id = ctx["project"].id

    png_bytes = _create_dummy_png_bytes(500, 400)
    files = {
        "file": ("esquema_pid_01.png", png_bytes, "image/png")
    }
    data = {
        "project_id": project_id,
        "auto_process": "true"
    }

    res = client.post("/api/v1/documents/upload", headers=headers, data=data, files=files)
    assert res.status_code == 201, f"Error: {res.text}"
    doc_data = res.json()
    assert doc_data["filename"] == "esquema_pid_01.png"
    assert doc_data["project_id"] == project_id
    assert doc_data["status"] == "ready"
    assert len(doc_data["sheets"]) == 1


def test_single_document_upload_dxf_cad(client: TestClient, db_session: Session):
    """Escenario A3: Carga simple de un archivo técnico CAD/DXF."""
    ctx = _get_test_context(client, db_session)
    headers = ctx["headers"]
    project_id = ctx["project"].id

    dxf_content = b"0\nSECTION\n2\nHEADER\n0\nENDSEC\n0\nEOF\n"
    files = {
        "file": ("layout_piping_revA.dxf", dxf_content, "application/acad")
    }
    data = {
        "project_id": project_id,
        "auto_process": "true"
    }

    res = client.post("/api/v1/documents/upload", headers=headers, data=data, files=files)
    assert res.status_code == 201, f"Error: {res.text}"
    doc_data = res.json()
    assert doc_data["filename"] == "layout_piping_revA.dxf"
    assert doc_data["project_id"] == project_id
    assert doc_data["status"] == "ready"


def test_batch_document_upload_multi_files(client: TestClient, db_session: Session):
    """Escenario B: Carga por lotes de mezcla de PDFs, imágenes y especificaciones."""
    ctx = _get_test_context(client, db_session)
    headers = ctx["headers"]
    project_id = ctx["project"].id

    pdf_bytes_1 = _create_dummy_pdf_bytes("Plano Piping Área 100")
    pdf_bytes_2 = _create_dummy_pdf_bytes("Plano Piping Área 200")
    png_bytes = _create_dummy_png_bytes(600, 400)
    spec_txt = b"ESPECIFICACION TECNICA PIPING ASME B31.3 - MATERIAL CS A106 Gr.B\n"

    files = [
        ("files", ("plano_area_100.pdf", pdf_bytes_1, "application/pdf")),
        ("files", ("plano_area_200.pdf", pdf_bytes_2, "application/pdf")),
        ("files", ("croquis_valvulas.png", png_bytes, "image/png")),
        ("files", ("especificacion_materiales.txt", spec_txt, "text/plain")),
    ]
    data = {
        "project_id": project_id,
        "auto_process": "true"
    }

    res = client.post("/api/v1/documents/batch-upload", headers=headers, data=data, files=files)
    assert res.status_code == 201, f"Error: {res.text}"
    batch_res = res.json()

    assert batch_res["total_files"] == 4
    assert batch_res["successful_count"] == 4, f"Fallo en batch upload: {batch_res['results']}"
    assert batch_res["duplicated_count"] == 0
    assert batch_res["failed_count"] == 0
    assert len(batch_res["results"]) == 4
    assert len(batch_res["documents"]) == 4

    # Verificar que el listado de documentos del proyecto devuelve los 4 archivos
    list_res = client.get(f"/api/v1/documents?project_id={project_id}", headers=headers)
    assert list_res.status_code == 200
    docs_in_proj = list_res.json()
    assert len(docs_in_proj) >= 4
    wait_for_all_jobs(timeout=5.0)


def test_batch_upload_edge_cases_duplicate_and_failure(client: TestClient, db_session: Session):
    """Escenario C: Casos de borde en lote (duplicado + archivo vacío sin tumbar el lote)."""
    ctx = _get_test_context(client, db_session)
    headers = ctx["headers"]
    project_id = ctx["project"].id

    # 1. Cargar previamente un archivo
    existing_pdf = _create_dummy_pdf_bytes("Plano Base Preexistente")
    client.post(
        "/api/v1/documents/upload",
        headers=headers,
        data={"project_id": project_id},
        files={"file": ("plano_base.pdf", existing_pdf, "application/pdf")}
    )

    # 2. Enviar un lote con:
    #   a) Archivo nuevo válido
    #   b) Archivo duplicado (mismo hash SHA-256)
    #   c) Archivo vacío (0 bytes)
    new_pdf = _create_dummy_pdf_bytes("Plano Nuevo Único")
    files = [
        ("files", ("plano_nuevo_unico.pdf", new_pdf, "application/pdf")),
        ("files", ("plano_duplicado.pdf", existing_pdf, "application/pdf")),
        ("files", ("archivo_vacio.pdf", b"", "application/pdf")),
    ]
    data = {
        "project_id": project_id,
        "auto_process": "true"
    }

    res = client.post("/api/v1/documents/batch-upload", headers=headers, data=data, files=files)
    assert res.status_code == 201
    batch_res = res.json()

    assert batch_res["total_files"] == 3
    assert batch_res["successful_count"] == 1, f"Fallo en batch edge cases: {batch_res['results']}"
    assert batch_res["duplicated_count"] == 1
    assert batch_res["failed_count"] == 1

    # Verificar detalles por ítem
    results_map = {r["filename"]: r for r in batch_res["results"]}
    assert results_map["plano_nuevo_unico.pdf"]["status"] in ["ready", "uploaded"]
    assert results_map["plano_duplicado.pdf"]["status"] == "already_exists"
    assert results_map["archivo_vacio.pdf"]["status"] == "failed"
    assert "vacío" in results_map["archivo_vacio.pdf"]["error_message"].lower()
    wait_for_all_jobs(timeout=5.0)



def test_batch_upload_invalid_project(client: TestClient, db_session: Session):
    """Escenario C2: Intento de carga a un proyecto inexistente."""
    ctx = _get_test_context(client, db_session)
    headers = ctx["headers"]

    pdf_bytes = _create_dummy_pdf_bytes("Test")
    files = [("files", ("test.pdf", pdf_bytes, "application/pdf"))]
    data = {"project_id": "prj-inexistente-9999"}

    res = client.post("/api/v1/documents/batch-upload", headers=headers, data=data, files=files)
    assert res.status_code == 404
    assert "Proyecto no encontrado" in res.json()["detail"]


def test_downstream_integrity_sheet_image_and_metadata(client: TestClient, db_session: Session):
    """Escenario D: Integridad posterior (acceso a láminas rasterizadas para visor/OCR)."""
    ctx = _get_test_context(client, db_session)
    headers = ctx["headers"]
    project_id = ctx["project"].id

    pdf_bytes = _create_dummy_pdf_bytes("Plano Visor Test")
    files = {"file": ("plano_para_visor.pdf", pdf_bytes, "application/pdf")}
    res = client.post("/api/v1/documents/upload", headers=headers, data={"project_id": project_id}, files=files)
    assert res.status_code == 201
    doc_id = res.json()["id"]

    # 1. Consultar láminas
    sheets_res = client.get(f"/api/v1/documents/{doc_id}/sheets", headers=headers)
    assert sheets_res.status_code == 200
    sheets = sheets_res.json()
    assert len(sheets) == 1
    sheet_id = sheets[0]["id"]
    assert sheets[0]["width_px"] > 0
    assert sheets[0]["height_px"] > 0

    # 2. Consultar imagen maestra de la lámina
    img_res = client.get(f"/api/v1/documents/sheets/{sheet_id}/image", headers=headers)
    assert img_res.status_code == 200
    assert img_res.headers["content-type"] == "image/png"
    assert len(img_res.content) > 100 # Contenido PNG binario real


def test_upload_explicit_api_contract_and_persistence(client: TestClient, db_session: Session):
    """Escenario E: Validación estricta del contrato de API de upload (Sección 4 del procedimiento)."""
    ctx = _get_test_context(client, db_session)
    headers = ctx["headers"]
    project_id = ctx["project"].id

    pdf_bytes = _create_dummy_pdf_bytes("Plano Contrato P&ID 001")
    filename = "PID-001.pdf"
    files = {"file": (filename, pdf_bytes, "application/pdf")}
    data = {
        "project_id": project_id,
        "discipline": "piping",
        "document_type": "p_and_id",
        "evidence_classification": "sandbox",
        "execution_mode": "sandbox",
        "metadata_json": '{"author": "Ingeniero Auditor", "plant": "Refinería Norte"}',
        "auto_process": "true"
    }

    res = client.post("/api/v1/documents/upload", headers=headers, data=data, files=files)
    assert res.status_code == 201, f"Error en upload: {res.text}"
    body = res.json()

    # Campos obligatorios del contrato explícito
    assert "document_id" in body and body["document_id"]
    assert body["filename"] == "PID-001.pdf"
    assert body["content_type"] == "application/pdf"
    assert body["size_bytes"] == len(pdf_bytes)
    assert "sha256" in body and len(body["sha256"]) == 64
    assert body["storage_status"] == "stored"
    assert body["processing_status"] in ["ready", "uploaded"]
    assert "upload_timestamp" in body
    assert body["project_id"] == project_id
    assert "warnings" in body and isinstance(body["warnings"], list)

    # Compatibilidad con campos de UI
    assert body["id"] == body["document_id"]
    assert body["status"] == body["processing_status"]

    # Comprobar existencia física en almacenamiento
    from app.core.settings import settings
    expected_path = os.path.join(settings.RAW_DOCUMENTS_DIR, f"{body['sha256']}_{filename}")
    assert os.path.exists(expected_path), f"El archivo no fue persistido en disco: {expected_path}"
    with open(expected_path, "rb") as f:
        stored_bytes = f.read()
    assert stored_bytes == pdf_bytes

    # Comprobar registro en BD
    from app.db.models.document_memory import Document
    db_doc = db_session.query(Document).filter(Document.id == body["document_id"]).first()
    assert db_doc is not None
    assert db_doc.file_hash_sha256 == body["sha256"]
    assert db_doc.file_size_bytes == len(pdf_bytes)
    assert db_doc.project_id == project_id


def test_upload_validation_error_empty_file(client: TestClient, db_session: Session):
    """Escenario F1: Archivo vacío devuelve formato consistente UPLOAD_VALIDATION_ERROR."""
    ctx = _get_test_context(client, db_session)
    headers = ctx["headers"]
    project_id = ctx["project"].id

    files = {"file": ("empty_blueprint.pdf", b"", "application/pdf")}
    data = {"project_id": project_id}

    res = client.post("/api/v1/documents/upload", headers=headers, data=data, files=files)
    assert res.status_code == 400
    body = res.json()
    assert body["code"] == "UPLOAD_VALIDATION_ERROR"
    assert "vacío" in body["message"].lower()
    assert body["details"]["field"] == "file"


def test_upload_validation_error_disallowed_extension(client: TestClient, db_session: Session):
    """Escenario F2: Archivo ejecutable no permitido devuelve UPLOAD_VALIDATION_ERROR."""
    ctx = _get_test_context(client, db_session)
    headers = ctx["headers"]
    project_id = ctx["project"].id

    files = {"file": ("malicious_payload.exe", b"MZ\x90\x00executable_bytes", "application/x-msdownload")}
    data = {"project_id": project_id}

    res = client.post("/api/v1/documents/upload", headers=headers, data=data, files=files)
    assert res.status_code == 400
    body = res.json()
    assert body["code"] == "UPLOAD_VALIDATION_ERROR"
    assert "no permitido" in body["message"].lower()


def test_upload_validation_error_oversized_file(client: TestClient, db_session: Session, monkeypatch):
    """Escenario F3: Archivo que excede el límite máximo devuelve UPLOAD_VALIDATION_ERROR."""
    ctx = _get_test_context(client, db_session)
    headers = ctx["headers"]
    project_id = ctx["project"].id

    from app.core.settings import settings
    # Reducir temporalmente el límite para prueba a 1 MB
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_MB", 1)

    # 1.5 MB de datos
    big_bytes = b"%PDF-" + b"0" * (int(1.5 * 1024 * 1024))
    files = {"file": ("oversized_drawing.pdf", big_bytes, "application/pdf")}
    data = {"project_id": project_id}

    res = client.post("/api/v1/documents/upload", headers=headers, data=data, files=files)
    assert res.status_code == 400
    body = res.json()
    assert body["code"] == "UPLOAD_VALIDATION_ERROR"
    assert "excede el tamaño máximo" in body["message"].lower()


def test_upload_path_traversal_sanitization(client: TestClient, db_session: Session):
    """Escenario G: Sanitización contra ataques de path traversal."""
    ctx = _get_test_context(client, db_session)
    headers = ctx["headers"]
    project_id = ctx["project"].id

    pdf_bytes = _create_dummy_pdf_bytes("Sanitization Test")
    malicious_name = "../../../etc/passwd.pdf"
    files = {"file": (malicious_name, pdf_bytes, "application/pdf")}
    data = {"project_id": project_id}

    res = client.post("/api/v1/documents/upload", headers=headers, data=data, files=files)
    assert res.status_code == 201
    body = res.json()
    assert ".." not in body["filename"]
    assert "/" not in body["filename"]
    assert "\\" not in body["filename"]
    assert body["filename"] == "passwd.pdf"


def test_reprocess_failed_document_retains_id(client: TestClient, db_session: Session):
    """Escenario H: Reintento de procesamiento conserva el mismo document_id sin volver a subir."""
    ctx = _get_test_context(client, db_session)
    headers = ctx["headers"]
    project_id = ctx["project"].id

    # Cargar documento con auto_process=False
    pdf_bytes = _create_dummy_pdf_bytes("Plano para reprocesar")
    files = {"file": ("plano_reproceso.pdf", pdf_bytes, "application/pdf")}
    res = client.post(
        "/api/v1/documents/upload",
        headers=headers,
        data={"project_id": project_id, "auto_process": "false"},
        files=files
    )
    assert res.status_code == 201
    doc_id = res.json()["document_id"]

    # Invocar endpoint de procesamiento manual / reintento
    process_res = client.post(f"/api/v1/documents/{doc_id}/process", headers=headers, json={"dpi": 150})
    assert process_res.status_code == 200
    doc_data = process_res.json()
    assert doc_data["id"] == doc_id
    assert doc_data["status"] == "ready"
    assert len(doc_data["sheets"]) == 1

