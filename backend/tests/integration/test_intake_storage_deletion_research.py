import os
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_intake_file_storage_lifecycle_and_research():
    # 1. Registrar fuente mediante subida física de archivo PDF
    sample_pdf_content = b"%PDF-1.4 sample content for intake local storage test\nArt. 4.1.7 OGUC\n%%EOF"
    files = {
        "file": ("OGUC_Capitulo_4.pdf", sample_pdf_content, "application/pdf")
    }
    data = {
        "source_type": "normative_document",
        "title": "OGUC Capítulo 4 - Evacuación y Seguridad",
        "discipline": "Arquitectura",
        "document_type": "norma",
        "authority": "MINVU",
        "description": "Documento normativo de evacuación y pasillos",
        "version": "2026.1"
    }

    resp = client.post("/api/v1/intake/sources/upload", data=data, files=files)
    assert resp.status_code == 201, f"Error subiendo fuente: {resp.text}"
    source_json = resp.json()
    source_id = source_json["id"]
    assert source_json["title"] == "OGUC Capítulo 4 - Evacuación y Seguridad"
    assert source_json["source_origin"] == "local_upload"
    assert source_json["file_path"] is not None
    assert source_json["original_filename"] == "OGUC_Capitulo_4.pdf"
    assert source_json["file_size_bytes"] == len(sample_pdf_content)

    # Verificar que el archivo existe físicamente en disco
    assert os.path.exists(source_json["file_path"]), f"El archivo no existe en disco en {source_json['file_path']}"

    # 2. Consultar dependencias (debe estar en 0 inicialmente)
    dep_resp = client.get(f"/api/v1/intake/sources/{source_id}/dependencies")
    assert dep_resp.status_code == 200
    dep_data = dep_resp.json()
    assert dep_data["source_id"] == source_id
    assert dep_data["has_file"] is True
    assert dep_data["extractions_count"] == 0
    assert dep_data["can_hard_delete"] is True

    # 3. Procesar con IA usando la referencia del archivo guardado (sin volver a subirlo)
    ai_proc_payload = {
        "title": "Extracción IA OGUC Cap 4",
        "document_type": "norma",
        "authority": "MINVU",
        "discipline": "Arquitectura",
        "source_asset_id": source_id
    }
    ai_resp = client.post("/api/v1/intake/extractions/process-with-ai", json=ai_proc_payload)
    assert ai_resp.status_code in [200, 201], f"Error procesando con IA: {ai_resp.text}"
    extraction_json = ai_resp.json()
    assert extraction_json["source_origin"] == "document"
    assert extraction_json["source_asset_id"] == source_id
    assert len(extraction_json["items"]) > 0

    # 4. Consultar dependencias nuevamente (ahora debe tener 1 extracción vinculada)
    dep_resp2 = client.get(f"/api/v1/intake/sources/{source_id}/dependencies")
    assert dep_resp2.status_code == 200
    dep_data2 = dep_resp2.json()
    assert dep_data2["extractions_count"] == 1
    assert dep_data2["can_hard_delete"] is False

    # 5. Ejecutar investigación web estructurada y verificar persistencia en research_*
    web_payload = {
        "search_prompt": "Criterios sísmicos NCh433 para edificios habitacionales",
        "discipline": "Estructuras",
        "document_type": "norma",
        "authority": "INN",
        "focus_areas": ["deriva de piso", "espectro de diseño", "suelos tipo D"],
        "selected_sources": [
            {
                "url": "https://example.com/sismica",
                "title": "Criterios Sísmicos",
                "snippet": "NCh433 detallada",
                "domain": "example.com"
            }
        ]
    }
    web_resp = client.post("/api/v1/intake/extractions/process-web-research", json=web_payload)
    assert web_resp.status_code in [200, 201], f"Error en web research: {web_resp.text}"
    web_json = web_resp.json()
    assert web_json["source_origin"] == "web"
    assert len(web_json["search_citations"]) > 0

    # 6. Consultar histórico estructurado de investigaciones web
    q_resp = client.get("/api/v1/intake/research/queries")
    assert q_resp.status_code == 200
    queries = q_resp.json()
    assert len(queries) >= 1
    matching_query = next((q for q in queries if "NCh433" in q["search_prompt"]), None)
    assert matching_query is not None
    assert matching_query["discipline"] == "Estructuras"

    # Detalle de investigación web
    detail_resp = client.get(f"/api/v1/intake/research/queries/{matching_query['id']}")
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()
    assert len(detail_data["results"]) >= 1
    assert len(detail_data["results"][0]["sources"]) >= 1

    # 7. Probar eliminación de la fuente
    # A) Soft-delete por tener dependencias
    del_soft = client.delete(f"/api/v1/intake/sources/{source_id}?hard_delete=false")
    assert del_soft.status_code == 200
    del_data = del_soft.json()
    assert del_data["deleted"] is True
    assert del_data["mode"] == "soft_delete_archived"

    # B) Hard-delete forzado
    saved_path = source_json["file_path"]
    del_hard = client.delete(f"/api/v1/intake/sources/{source_id}?hard_delete=true")
    assert del_hard.status_code == 200
    del_hard_data = del_hard.json()
    assert del_hard_data["mode"] == "hard_delete"
    assert del_hard_data["file_removed"] is True

    # Verificar que el archivo en disco fue borrado
    assert not os.path.exists(saved_path), f"El archivo {saved_path} no debió existir tras hard delete"
