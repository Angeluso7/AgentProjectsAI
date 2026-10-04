import pytest
import uuid
from fastapi.testclient import TestClient
from app.db.models.core import User, Organization, OrganizationMembership
from app.core.security import hash_password, create_access_token

def test_multimodal_assisted_review_and_enrichment_flow(client: TestClient, db_session):
    """
    Test integral de revisión asistida para elementos multimodales:
    1. Creación de sesión y elemento con datos faltantes.
    2. Consulta de contexto en página exacta con bbox resaltado.
    3. Enriquecimiento asistido con alta evidencia (válvula de control) -> suggestion_found.
    4. Enriquecimiento asistido con evidencia insuficiente -> reporte honesto missing_data.
    5. Ejecución de OCR en sub-región para volcar texto a campo.
    6. Aplicación de sugerencia web y transición a complete.
    7. Modificación manual y verificación de persistencia y trazabilidad.
    """
    # 1. Setup Organization and User
    org_id = str(uuid.uuid4())
    org = Organization(id=org_id, name="Multimodal Review Org", slug=f"multi-org-{uuid.uuid4().hex[:6]}")
    db_session.add(org)

    user = User(
        id=str(uuid.uuid4()),
        email=f"reviewer_multi_{uuid.uuid4().hex[:6]}@planreview.ai",
        display_name="Auditor Multimodal",
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

    # 2. Crear Sesión de Extracción
    session_payload = {
        "title": "Plano P&ID - Sistema de Tratamiento de Aguas y Válvulas",
        "document_type": "plano_tecnico",
        "authority": "Ingeniería de Procesos",
        "discipline": "piping",
        "extraction_mode": "ai_document",
        "summary": "Extracción multimodal de símbolos y equipos en P&ID."
    }
    create_res = client.post("/api/v1/intake/extractions/process-with-ai", headers=headers, json=session_payload)
    assert create_res.status_code == 201
    session_data = create_res.json()
    extraction_id = session_data["id"]

    # 3. Agregar Elemento Multimodal (Símbolo de Válvula de Control con datos iniciales incompletos)
    item_payload = {
        "item_type": "symbol",
        "candidate_type": "symbol_candidate",
        "title": "Símbolo Técnico Desconocido",
        "code_or_number": "SYM-01",
        "description": None,
        "caption_or_context": "Válvula de control modulante con actuador neumático FCV en línea de recirculación p&id",
        "ocr_text": "FCV-101 4 INCH ANSI 300",
        "page_number": 3,
        "bbox_normalized": [0.25, 0.35, 0.45, 0.55],
        "crop_image_path": "/data/crops/extractions/sample_valve.png",
        "target_destination": "rules_engine"
    }
    item_res = client.post(f"/api/v1/intake/extractions/{extraction_id}/items", headers=headers, json=item_payload)
    assert item_res.status_code == 201
    item_data = item_res.json()
    item_id = item_data["id"]

    # Verificar estado de completitud inicial
    assert item_data["completeness_status"] == "missing_data"
    assert item_data["enrichment_status"] == "not_enriched"
    assert item_data["requires_validation"] is True

    # 4. Obtener Contexto de Página Exacta (GET /context)
    ctx_res = client.get(f"/api/v1/intake/extractions/{extraction_id}/items/{item_id}/context", headers=headers)
    assert ctx_res.status_code == 200
    ctx_data = ctx_res.json()
    assert ctx_data["item_id"] == item_id
    assert ctx_data["page_number"] == 3
    assert ctx_data["bbox_normalized"] == [0.25, 0.35, 0.45, 0.55]
    assert ctx_data["completeness_status"] == "missing_data"
    assert ctx_data["discipline"] == "piping"

    # 5. Ejecutar Enriquecimiento Asistido con Alta Evidencia (POST /enrich)
    enrich_res = client.post(
        f"/api/v1/intake/extractions/{extraction_id}/items/{item_id}/enrich",
        headers=headers,
        json={"force_web_search": True}
    )
    assert enrich_res.status_code == 200
    enrich_data = enrich_res.json()
    assert enrich_data["enrichment_status"] == "suggestion_found"
    assert enrich_data["completeness_status"] == "web_suggested"
    assert enrich_data["match_confidence"] >= 0.70
    assert "Válvula de Control" in enrich_data["suggested_title"]
    assert "ISA 5.1" in enrich_data["suggested_source_label"]
    assert enrich_data["suggested_source_url"] is not None
    assert enrich_data["requires_validation"] is True
    assert enrich_data["enriched_from_web"] is True

    # 6. Probar Enriquecimiento con Evidencia Insuficiente (Elemento ambiguo sin keywords)
    ambiguous_payload = {
        "item_type": "symbol",
        "candidate_type": "symbol_candidate",
        "title": "Bloque CAD Desconocido",
        "caption_or_context": "Figura geométrica circular sin texto cercano",
        "ocr_text": "---",
        "page_number": 1,
        "bbox_normalized": [0.1, 0.1, 0.2, 0.2]
    }
    amb_res = client.post(f"/api/v1/intake/extractions/{extraction_id}/items", headers=headers, json=ambiguous_payload)
    assert amb_res.status_code == 201
    amb_id = amb_res.json()["id"]

    amb_enrich_res = client.post(
        f"/api/v1/intake/extractions/{extraction_id}/items/{amb_id}/enrich",
        headers=headers,
        json={"force_web_search": True}
    )
    assert amb_enrich_res.status_code == 200
    amb_enrich_data = amb_enrich_res.json()
    assert amb_enrich_data["enrichment_status"] == "not_enriched"
    assert amb_enrich_data["completeness_status"] == "missing_data"
    assert amb_enrich_data["match_confidence"] < 0.65
    assert amb_enrich_data["suggested_title"] is None
    assert "evidencia concluyente" in amb_enrich_data["message"]

    # 7. Ejecutar OCR en Sub-Región (POST /region-ocr)
    ocr_payload = {
        "page_number": 3,
        "bbox": [0.20, 0.30, 0.50, 0.60],
        "target_field": "title"
    }
    ocr_res = client.post(f"/api/v1/intake/extractions/{extraction_id}/items/{item_id}/region-ocr", headers=headers, json=ocr_payload)
    assert ocr_res.status_code == 200
    ocr_data = ocr_res.json()
    assert ocr_data["page_number"] == 3
    assert ocr_data["target_field"] == "title"
    assert len(ocr_data["extracted_text"]) > 0

    # 8. Aplicar Sugerencia Web al Elemento Activo (POST /apply-suggestion)
    apply_res = client.post(f"/api/v1/intake/extractions/{extraction_id}/items/{item_id}/apply-suggestion", headers=headers)
    assert apply_res.status_code == 200
    applied_data = apply_res.json()
    assert "Válvula de Control" in applied_data["title"]
    assert len(applied_data["description"]) > 20
    assert applied_data["completeness_status"] == "complete"
    assert applied_data["enrichment_status"] == "manual_completed"
    assert applied_data["requires_validation"] is False
    assert "ISA 5.1" in (applied_data["source_reference"] or "")

    # 9. Verificación de Actualización Manual Directa (PUT /items/{id})
    update_res = client.put(
        f"/api/v1/intake/extractions/{extraction_id}/items/{item_id}",
        headers=headers,
        json={
            "title": "Válvula de Control Automática FCV-101 Validada",
            "review_status": "accepted"
        }
    )
    assert update_res.status_code == 200
    updated_data = update_res.json()
    assert updated_data["title"] == "Válvula de Control Automática FCV-101 Validada"
    assert updated_data["review_status"] == "accepted"
    assert updated_data["completeness_status"] == "complete"
