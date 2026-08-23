import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_rules_document_content_and_baseline_promotion_flow():
    headers = {
        "x-organization-id": "org_normative_baseline_test",
        "x-user-id": "auditor_qa_qc"
    }

    # =========================================================
    # 1. ETAPA 1 & 2: INTAKE - CREAR SESIÓN Y CAPTURAR REGLAS
    # =========================================================
    session_res = client.post(
        "/api/v1/intake/extractions/create-manual",
        headers=headers,
        json={
            "title": "Norma OGUC Título 4 - Seguridad y Evacuación",
            "document_type": "norma",
            "discipline": "Arquitectura",
            "authority": "MINVU"
        }
    )
    assert session_res.status_code == 201
    extraction_id = session_res.json()["id"]

    # Agregar Regla 1 (Validada)
    r1_res = client.post(
        f"/api/v1/intake/extractions/{extraction_id}/items",
        headers=headers,
        json={
            "item_type": "rule",
            "title": "Pasamanos Continuo en Escaleras",
            "code_or_number": "REG-OGUC-417",
            "description": "Toda escalera de uso público deberá contar con pasamanos continuo a 0.90 m de altura.",
            "content_text": "Toda escalera de uso público deberá contar con pasamanos continuo a 0.90 m de altura.",
            "target_destination": "rules_engine",
            "review_status": "validada",
            "page_number": 1
        }
    )
    assert r1_res.status_code == 201
    item1_id = r1_res.json()["id"]

    # Agregar Regla 2 (Validada)
    r2_res = client.post(
        f"/api/v1/intake/extractions/{extraction_id}/items",
        headers=headers,
        json={
            "item_type": "rule",
            "title": "Apertura de Puertas de Escape en Evacuación",
            "code_or_number": "REG-OGUC-437",
            "description": "Las puertas de escape deberán abrir en el sentido de la evacuación sin llave ni traba.",
            "content_text": "Las puertas de escape deberán abrir en el sentido de la evacuación sin llave ni traba.",
            "target_destination": "rules_engine",
            "review_status": "validada",
            "page_number": 2
        }
    )
    assert r2_res.status_code == 201
    item2_id = r2_res.json()["id"]

    # Agregar Regla 3 (Por confirmar - No debe promoverse si queda pendiente)
    r3_res = client.post(
        f"/api/v1/intake/extractions/{extraction_id}/items",
        headers=headers,
        json={
            "item_type": "rule",
            "title": "Criterio de Resistencia al Fuego Pendiente",
            "code_or_number": "REG-OGUC-431-PEND",
            "description": "Exigencia de resistencia al fuego F-120 pendiente de confirmación.",
            "content_text": "Exigencia de resistencia al fuego F-120 pendiente de confirmación.",
            "target_destination": "rules_engine",
            "review_status": "por_confirmar",
            "page_number": 3
        }
    )
    assert r3_res.status_code == 201

    # =========================================================
    # 2. ETAPA 3: COMMIT EN INTAKE -> APARECE EN DOCUMENTOS NORMATIVOS
    # =========================================================
    commit_res = client.post(
        f"/api/v1/intake/extractions/{extraction_id}/commit",
        headers=headers,
        json={
            "approved_item_ids": [item1_id, item2_id],
            "target_rule_document_title": "Norma OGUC Título 4 (Incorporado desde Intake)"
        }
    )
    assert commit_res.status_code == 200
    rule_doc_id = commit_res.json()["rule_document_id"]

    # Verificar que el documento aparece en la lista de Documentos Normativos
    docs_res = client.get("/api/v1/rules/documents", headers=headers)
    assert docs_res.status_code == 200
    docs = docs_res.json()
    matched_doc = next((d for d in docs if d["id"] == rule_doc_id), None)
    assert matched_doc is not None
    assert matched_doc["rules_count"] == 2

    # =========================================================
    # 3. ETAPA 4: VENTANA "CONTENIDO" - REVISAR, EDITAR Y CONFIRMAR CONTENIDO
    # =========================================================
    # Obtener items del documento normativo
    items_res = client.get(f"/api/v1/rules/documents/{rule_doc_id}/items", headers=headers)
    assert items_res.status_code == 200
    doc_items = items_res.json()
    assert len(doc_items) == 2

    # Simular edición de una regla en Contenido
    target_item = doc_items[0]
    update_item_res = client.put(
        f"/api/v1/rules/documents/{rule_doc_id}/items/{target_item['id']}",
        headers=headers,
        json={
            "title": "Pasamanos Continuo a 0.90m en Escaleras (Revisado)",
            "description": "Toda escalera de uso público deberá contar con pasamanos continuo entre 0.90 m y 0.95 m.",
            "status": "validada"
        }
    )
    assert update_item_res.status_code == 200
    assert "0.95 m" in update_item_res.json()["description"]

    # Simular clic en "Aceptar y Confirmar Contenido" dentro de la ventana Contenido
    confirm_content_res = client.post(
        f"/api/v1/rules/documents/{rule_doc_id}/confirm-content",
        headers=headers,
        json={"confirmed_item_ids": [it["id"] for it in doc_items]}
    )
    assert confirm_content_res.status_code == 200
    confirm_data = confirm_content_res.json()
    assert confirm_data["status"] == "confirmado"
    assert confirm_data["confirmed_rules_count"] == 2

    # =========================================================
    # 4. ETAPA 5: BOTÓN "ACEPTAR" DEL RENGLÓN -> PROMOVER A BASELINE QA/QC
    # =========================================================
    promote_res = client.post(
        f"/api/v1/rules/documents/{rule_doc_id}/promote-to-baseline",
        headers=headers
    )
    assert promote_res.status_code == 200
    promote_data = promote_res.json()
    assert promote_data["promoted_count"] == 2
    assert len(promote_data["rule_codes"]) == 2

    # Verificar que el documento ahora tiene estado 'promovido_baseline'
    doc_detail_res = client.get(f"/api/v1/rules/documents/{rule_doc_id}", headers=headers)
    assert doc_detail_res.status_code == 200
    assert doc_detail_res.json()["status"] == "promovido_baseline"

    # Verificar que las reglas están en el catálogo Baseline QA/QC global
    baseline_res = client.get("/api/v1/rules", headers=headers)
    assert baseline_res.status_code == 200
    baseline_rules = baseline_res.json()
    
    # Comprobar que las reglas promovidas existen y están activas en Baseline
    promoted_in_baseline = [r for r in baseline_rules if r["code"] in promote_data["rule_codes"]]
    assert len(promoted_in_baseline) == 2
    for br in promoted_in_baseline:
        assert br["is_active"] is True
        assert br["category"] == "normative_compliance"
        assert br["input_requirements"]["source_document_id"] == rule_doc_id
