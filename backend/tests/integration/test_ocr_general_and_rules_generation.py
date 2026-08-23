import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_ocr_general_and_rules_generation():
    headers = {
        "x-organization-id": "org_ocr_rules_test",
        "x-user-id": "user_qa_qc"
    }

    # 1. Test Document OCR Endpoint (General)
    ocr_res = client.post(
        "/api/v1/intake/extractions/document-ocr",
        headers=headers,
        json={}
    )
    assert ocr_res.status_code == 200
    ocr_data = ocr_res.json()
    assert ocr_data["total_pages"] >= 1
    assert len(ocr_data["full_text"]) > 20
    assert len(ocr_data["pages"]) >= 1

    # 2. Test Generate Structured Rules List from OCR Text
    sample_ocr = (
        "ORDENANZA GENERAL DE URBANISMO Y CONSTRUCCIONES\n"
        "Art. 4.1.7 Toda escalera de uso público deberá contar con pasamanos continuo a 0.90 m de altura.\n"
        "Art. 4.3.1 Todo edificio de más de 5 pisos deberá contar con zona vertical de seguridad protegida contra humo y fuego.\n"
        "Art. 4.3.7 Las puertas de escape deberán abrir en el sentido de la evacuación sin llave ni traba."
    )

    gen_payload = {
        "ocr_text": sample_ocr,
        "discipline": "Arquitectura",
        "document_title": "OGUC Título 4",
        "page_number": 2
    }

    gen_res = client.post(
        "/api/v1/intake/extractions/generate-rules-from-ocr",
        headers=headers,
        json=gen_payload
    )
    assert gen_res.status_code == 200
    gen_data = gen_res.json()
    assert "rules" in gen_data
    rules = gen_data["rules"]
    assert len(rules) >= 3

    # Verificar estructura de cada regla generada
    for r in rules:
        assert "code" in r
        assert "title" in r
        assert "statement" in r
        assert r["item_type"] == "rule"
        assert r["page_number"] == 2
        assert len(r["statement"]) > 10

    # 3. Test Manual Extraction Session & Adding Generated Rules to Session Items
    session_payload = {
        "title": "OGUC T4 Evacuación y Reglas",
        "document_type": "norma",
        "discipline": "Arquitectura",
        "authority": "MINVU"
    }
    session_res = client.post(
        "/api/v1/intake/extractions/create-manual",
        headers=headers,
        json=session_payload
    )
    assert session_res.status_code == 201
    session_id = session_res.json()["id"]

    # Agregar dos reglas generadas a la sesión (simulando incorporación desde la ventana T OCR General)
    added_item_ids = []
    for r in rules[:2]:
        add_res = client.post(
            f"/api/v1/intake/extractions/{session_id}/items",
            headers=headers,
            json={
                "item_type": r["item_type"],
                "title": f"{r['code']}: {r['title']}",
                "code_or_number": r["code"],
                "description": r["statement"],
                "content_text": r["statement"],
                "ocr_text": r["statement"],
                "page_number": r["page_number"],
                "target_destination": "rules_engine",
                "review_status": "validada"
            }
        )
        assert add_res.status_code == 201
        added_item_ids.append(add_res.json()["id"])

    # 4. Commit Extraction
    commit_res = client.post(
        f"/api/v1/intake/extractions/{session_id}/commit",
        headers=headers,
        json={
            "approved_item_ids": added_item_ids,
            "target_rule_document_title": "Norma OGUC T4 con Reglas OCR General"
        }
    )
    assert commit_res.status_code == 200
    commit_data = commit_res.json()
    assert commit_data["rules_incorporated_count"] == 2
