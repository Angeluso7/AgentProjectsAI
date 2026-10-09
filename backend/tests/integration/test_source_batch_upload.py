import os
import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_source_batch_upload_successful_with_folder_paths():
    """
    Escenario 1: Lote exitoso de múltiples fuentes con estructura de carpetas simulada.
    Verifica que se generan los títulos con prefijo, se guardan los archivos físicos,
    y se preservan las rutas relativas en metadatos.
    """
    unique_marker = uuid.uuid4().hex[:8]
    file1_content = f"Contenido normativo ASME B31.3 - Tuberías de proceso {unique_marker}".encode("utf-8")
    file2_content = f"Contenido de especificación técnica API 6D - Válvulas {unique_marker}".encode("utf-8")
    file3_content = f"Contenido de catálogo de instrumentos ISA 5.1 {unique_marker}".encode("utf-8")

    files = [
        ("files", ("piping/specs/ASME_B31_3.txt", file1_content, "text/plain")),
        ("files", ("piping/valves/API_6D.txt", file2_content, "text/plain")),
        ("files", ("instrumentation/ISA_5_1.txt", file3_content, "text/plain")),
    ]

    data = {
        "title_prefix": "Norma Técnica",
        "source_type": "normative_document",
        "discipline": "Piping",
        "document_type": "standard_doc",
        "authority": "ASME / API",
        "description": "Lote de normativas técnicas de proceso",
        "version": "1.0",
        "owner": "auditor_qa"
    }

    resp = client.post("/api/v1/intake/sources/batch-upload", data=data, files=files)
    assert resp.status_code == 201, f"Error en batch-upload: {resp.text}"
    body = resp.json()

    assert body["total_files"] == 3
    assert body["successful_count"] == 3
    assert body["duplicated_count"] == 0
    assert body["failed_count"] == 0
    assert len(body["sources"]) == 3
    assert len(body["results"]) == 3

    # Verificar títulos con prefijo y rutas relativas tanto en sources como en results
    titles = [s["title"] for s in body["sources"]]
    assert any("Norma Técnica - ASME B31 3" in t for t in titles)
    assert any("Norma Técnica - API 6D" in t for t in titles)
    assert any("Norma Técnica - ISA 5 1" in t for t in titles)

    # Validar explícitamente el contrato de results[].title para evitar desalineaciones silenciosas de esquema
    result_titles = [r["title"] for r in body["results"]]
    assert len(result_titles) == 3
    assert all(t is not None and len(t) > 0 for t in result_titles)
    assert any("Norma Técnica - ASME B31 3" in t for t in result_titles)
    assert any("Norma Técnica - API 6D" in t for t in result_titles)
    assert any("Norma Técnica - ISA 5 1" in t for t in result_titles)

    # Verificar que el relative_path se preservó en metadata_payload
    for source in body["sources"]:
        meta = source.get("metadata_payload") or {}
        assert "relative_path" in meta
        assert any(meta["relative_path"].endswith(ext) for ext in [".txt"])
        assert "/" in meta["relative_path"]  # Estructura jerárquica de carpeta

        # Verificar existencia física
        assert source["file_path"] is not None
        assert os.path.exists(source["file_path"])


def test_source_batch_upload_partial_failure_does_not_abort_batch():
    """
    Escenario 2: Lote con un archivo vacío (0 bytes) que falla individualmente
    sin abortar el registro de los demás archivos válidos del lote.
    """
    unique_marker = uuid.uuid4().hex[:8]
    valid_content = f"Contenido válido para prueba de fallo defensivo {unique_marker}".encode("utf-8")
    empty_content = b""

    files = [
        ("files", ("valido_1.txt", valid_content, "text/plain")),
        ("files", ("corrupto_vacio.txt", empty_content, "text/plain")),
    ]

    data = {
        "source_type": "normative_document",
        "discipline": "Mecánica",
        "document_type": "standard_doc",
        "authority": "INN",
        "owner": "auditor_qa"
    }

    resp = client.post("/api/v1/intake/sources/batch-upload", data=data, files=files)
    assert resp.status_code == 201, f"Error en batch-upload defensivo: {resp.text}"
    body = resp.json()

    assert body["total_files"] == 2
    assert body["successful_count"] == 1
    assert body["failed_count"] == 1
    assert len(body["sources"]) == 1

    # Verificar resultado individual
    res_map = {r["filename"]: r for r in body["results"]}
    assert "valido_1.txt" in res_map
    assert res_map["valido_1.txt"]["status"] == "uploaded"

    assert "corrupto_vacio.txt" in res_map
    assert res_map["corrupto_vacio.txt"]["status"] == "failed"
    assert "vacío" in res_map["corrupto_vacio.txt"]["error_message"].lower()


def test_source_batch_upload_duplicate_detection():
    """
    Escenario 3: Lote con archivo duplicado (mismo sha256).
    Verifica que el segundo archivo con mismo hash se reporte como already_exists
    y no genere duplicación en la base de datos de fuentes.
    """
    unique_marker = uuid.uuid4().hex[:8]
    identical_content = f"Contenido único idéntico para deduplicación {unique_marker}".encode("utf-8")

    # Primera subida: registro inicial
    initial_files = [
        ("files", ("original.txt", identical_content, "text/plain")),
    ]
    initial_data = {
        "source_type": "normative_document",
        "discipline": "Instrumentación",
        "authority": "ISA",
    }
    resp1 = client.post("/api/v1/intake/sources/batch-upload", data=initial_data, files=initial_files)
    assert resp1.status_code == 201
    body1 = resp1.json()
    assert body1["successful_count"] == 1
    orig_source_id = body1["sources"][0]["id"]

    # Segunda subida: lote que incluye el archivo duplicado y uno nuevo
    different_content = f"Contenido diferente {unique_marker}".encode("utf-8")
    batch_files = [
        ("files", ("copia_duplicada.txt", identical_content, "text/plain")),
        ("files", ("archivo_nuevo.txt", different_content, "text/plain")),
    ]

    resp2 = client.post("/api/v1/intake/sources/batch-upload", data=initial_data, files=batch_files)
    assert resp2.status_code == 201
    body2 = resp2.json()

    assert body2["total_files"] == 2
    assert body2["successful_count"] == 1
    assert body2["duplicated_count"] == 1
    assert body2["failed_count"] == 0

    res_map = {r["filename"]: r for r in body2["results"]}
    assert res_map["copia_duplicada.txt"]["status"] == "already_exists"
    assert res_map["copia_duplicada.txt"]["source_id"] == orig_source_id
    assert res_map["copia_duplicada.txt"]["title"] is not None
    assert res_map["archivo_nuevo.txt"]["status"] == "uploaded"
    assert res_map["archivo_nuevo.txt"]["title"] is not None
