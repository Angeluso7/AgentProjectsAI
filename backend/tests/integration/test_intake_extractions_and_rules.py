import pytest
import uuid
from fastapi.testclient import TestClient
from app.db.models.core import User, Organization, OrganizationMembership
from app.core.security import hash_password, create_access_token

def test_intake_ai_and_manual_extractions_and_rules_flow(client: TestClient, db_session):
    # 1. Setup Organization and User
    org_id = str(uuid.uuid4())
    org = Organization(id=org_id, name="Intake Extractions Test Org", slug=f"intake-org-{uuid.uuid4().hex[:6]}")
    db_session.add(org)

    user = User(
        id=str(uuid.uuid4()),
        email=f"intake_reviewer_{uuid.uuid4().hex[:6]}@planreview.ai",
        display_name="Auditor Intake & Rules",
        password_hash=hash_password("Password123!"),
        is_active=True,
        is_superuser=False
    )
    db_session.add(user)

    membership = OrganizationMembership(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        user_id=user.id,
        role="reviewer",
        status="active"
    )
    db_session.add(membership)
    db_session.commit()

    token = create_access_token(user.id, email=user.email, extra_claims={"role": "reviewer"})
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

    # 2. Test Process with AI (Opción 1: Documento)
    ai_payload = {
        "title": "Ordenanza General de Urbanismo y Construcciones (OGUC) - Título 4",
        "document_type": "norma",
        "authority": "MINVU",
        "discipline": "architecture",
        "extraction_mode": "ai_document",
        "text_content": "Texto normativo sobre vías de evacuación y puertas de escape."
    }
    ai_res = client.post("/api/v1/intake/extractions/process-with-ai", headers=headers, json=ai_payload)
    assert ai_res.status_code == 201
    ai_data = ai_res.json()
    assert ai_data["title"] == "Ordenanza General de Urbanismo y Construcciones (OGUC) - Título 4"
    assert ai_data["status"] == "extracted"
    assert ai_data["source_origin"] == "document"
    assert len(ai_data["items"]) >= 5
    extraction_id = ai_data["id"]

    # 3. Test List Extractions
    list_res = client.get("/api/v1/intake/extractions", headers=headers)
    assert list_res.status_code == 200
    extractions = list_res.json()
    assert any(e["id"] == extraction_id for e in extractions)

    # 4. Test Update an Extracted Item
    first_item = ai_data["items"][0]
    update_res = client.put(
        f"/api/v1/intake/extractions/{extraction_id}/items/{first_item['id']}",
        headers=headers,
        json={"title": "Capítulo 1 Editado por Auditor", "review_status": "accepted"}
    )
    assert update_res.status_code == 200
    assert update_res.json()["title"] == "Capítulo 1 Editado por Auditor"
    assert update_res.json()["review_status"] == "accepted"

    # 5. Test Add Manual Item to Session
    add_item_payload = {
        "item_type": "rule",
        "title": "Regla Adicional: Puerta batiente 180°",
        "code_or_number": "REG-MANUAL-01",
        "description": "Exigencia de apertura total sin obstrucción",
        "target_destination": "both",
        "review_status": "accepted",
        "source_origin": "document"
    }
    add_item_res = client.post(
        f"/api/v1/intake/extractions/{extraction_id}/items",
        headers=headers,
        json=add_item_payload
    )
    assert add_item_res.status_code == 201
    assert add_item_res.json()["title"] == "Regla Adicional: Puerta batiente 180°"

    # 6. Test Commit Extraction to Rules Engine
    commit_payload = {
        "target_rule_document_title": "Norma OGUC - Título 4 Evacuación (Incorporado)",
        "target_rule_document_description": "Normativa oficial incorporada al Motor de Reglas QA/QC"
    }
    commit_res = client.post(
        f"/api/v1/intake/extractions/{extraction_id}/commit",
        headers=headers,
        json=commit_payload
    )
    assert commit_res.status_code == 200
    commit_data = commit_res.json()
    assert commit_data["rules_incorporated_count"] >= 5
    rule_doc_id = commit_data["rule_document_id"]

    # 7. Test List Rule Documents
    rule_docs_res = client.get("/api/v1/rules/documents", headers=headers)
    assert rule_docs_res.status_code == 200
    docs = rule_docs_res.json()
    assert any(d["id"] == rule_doc_id for d in docs)

    # 8. Test Get Rule Document Items
    items_res = client.get(f"/api/v1/rules/documents/{rule_doc_id}/items", headers=headers)
    assert items_res.status_code == 200
    assert len(items_res.json()) >= 5

    # 9. Test Update Rule Document Metadata
    update_doc_res = client.put(
        f"/api/v1/rules/documents/{rule_doc_id}",
        headers=headers,
        json={"title": "Norma OGUC T4 - Revisada y Activa", "version": "1.1"}
    )
    assert update_doc_res.status_code == 200
    assert update_doc_res.json()["title"] == "Norma OGUC T4 - Revisada y Activa"
    assert update_doc_res.json()["version"] == "1.1"

    # 10. Test Full Document OCR Endpoint
    ocr_res = client.post("/api/v1/intake/extractions/document-ocr", headers=headers, json={})
    assert ocr_res.status_code == 200
    assert ocr_res.json()["total_pages"] >= 1
    assert len(ocr_res.json()["full_text"]) > 20

    # 11. Test Web Research via POST /api/v1/intake/extractions/process-web-research (Opción 2 con IA)
    web_payload = {
        "search_prompt": "Investigar criterios de accesibilidad para edificios residenciales",
        "discipline": "Arquitectura",
        "document_type": "norma",
        "authority": "MINVU / Web Research",
        "focus_areas": ["accesibilidad", "rampas", "ancho_pasillos"],
        "selected_sources": [
            {
                "url": "https://example.com/accesibilidad",
                "title": "Accesibilidad Residencial",
                "snippet": "Criterios de diseño",
                "domain": "example.com"
            }
        ]
    }
    web_res = client.post("/api/v1/intake/extractions/process-web-research", headers=headers, json=web_payload)
    assert web_res.status_code == 201
    web_data = web_res.json()
    assert "Investigación Web" in web_data["title"]
    assert web_data["source_origin"] == "web"
    assert web_data["extraction_mode"] == "ai_web_research"
    assert len(web_data["search_citations"]) >= 1
    assert len(web_data["items"]) >= 5

    # Validar procedencia de items web
    web_items = web_data["items"]
    assert all(it["source_origin"] == "web" for it in web_items)
    proposed_rules = [it for it in web_items if it["item_type"] == "rule"]
    assert len(proposed_rules) >= 2
    assert all(r["item_nature"] == "proposed_rule" for r in proposed_rules)
    assert any("investigación" in (it.get("governance_note") or "").lower() for it in web_items)

    # 12. Test Commit Web Research to Rules Engine
    web_extraction_id = web_data["id"]
    web_commit_res = client.post(
        f"/api/v1/intake/extractions/{web_extraction_id}/commit",
        headers=headers,
        json={
            "target_rule_document_title": "Investigación Accesibilidad Universal (Apoyo Web)",
            "target_rule_document_description": "Reglas propuestas y referencias de apoyo investigadas en Internet"
        }
    )
    assert web_commit_res.status_code == 200
    web_rule_doc_id = web_commit_res.json()["rule_document_id"]

    # Verificar que el RuleDocument guardó source_origin = 'con_ia_web'
    web_doc_detail = client.get(f"/api/v1/rules/documents/{web_rule_doc_id}", headers=headers).json()
    assert web_doc_detail["source_origin"] == "con_ia_web"
    assert web_doc_detail["items_count"] >= 5
