import pytest
from app.db.models.normative_memory import NormativeDocument
from app.db.models.intake import SourceAsset

def test_source_registration_and_automatic_routing(client):
    """Verifica el registro y la asignación determinística de memoria destino."""
    # 1. Registrar documento de análisis
    res1 = client.post("/api/v1/intake/sources", json={
        "source_type": "analysis_document",
        "title": "Plano Estructuras E-01.pdf",
        "discipline": "structural"
    })
    assert res1.status_code == 201
    s1 = res1.json()
    assert s1["linked_memory_target"] == "document_memory"
    assert s1["approval_status"] == "not_required"

    # 2. Registrar fuente normativa web (debe quedar en pending_review)
    res2 = client.post("/api/v1/intake/sources", json={
        "source_type": "web_normative_source",
        "source_origin": "web_scrape",
        "title": "Actualización NCh 433 Diseño Sísmico",
        "source_url": "https://inn.cl/nch433-2024",
        "discipline": "structural",
        "metadata_payload": {
            "authority": "INN",
            "code": "NCH-433-2024-TEST",
            "clauses": [
                {"clause_number": "Art. 5.1", "title": "Zonificación sísmica", "content_text": "Chile se divide en zonas 1, 2 y 3."}
            ]
        }
    })
    assert res2.status_code == 201
    s2 = res2.json()
    assert s2["linked_memory_target"] == "normative_memory"
    assert s2["approval_status"] == "pending_review"

def test_unapproved_web_source_cannot_feed_normative_memory(client):
    """CANDADO DE GOBIERNO: Una fuente web sin aprobar NO debe poder ingresar a normative_memory."""
    # 1. Registrar fuente web
    res = client.post("/api/v1/intake/sources", json={
        "source_type": "web_normative_source",
        "source_origin": "web_scrape",
        "title": "Borrador No Oficial Norma Eléctrica",
        "source_url": "https://ejemplo.com/borrador-sec",
        "discipline": "electrical"
    })
    assert res.status_code == 201
    source_id = res.json()["id"]

    # 2. Intentar ingestar a normative_memory (debe ser bloqueado con 403 Forbidden)
    ingest_res = client.post(f"/api/v1/intake/sources/{source_id}/ingest")
    assert ingest_res.status_code == 403
    assert "Debe ser revisada y aprobada" in ingest_res.json()["detail"]

def test_approval_flow_and_subsequent_ingest(client, db_session):
    """Verifica que una fuente web aprobada por un revisor pueda alimentar formalmente normative_memory."""
    # 1. Registrar fuente web
    res = client.post("/api/v1/intake/sources", json={
        "source_type": "web_normative_source",
        "source_origin": "web_scrape",
        "title": "Decreto Supremo 47 MINVU",
        "source_url": "https://bcn.cl/ds47",
        "discipline": "architecture",
        "metadata_payload": {
            "authority": "MINVU",
            "code": "DS-47-MINVU-TEST",
            "clauses": [
                {"clause_number": "Art. 1.1.2", "title": "Definición de Vano", "content_text": "Abertura en muro."}
            ]
        }
    })
    source_id = res.json()["id"]

    # 2. Aprobar fuente mediante revisión técnica
    app_res = client.post(f"/api/v1/intake/sources/{source_id}/approval", json={
        "approved": True,
        "notes": "Fuente oficial validada en Biblioteca del Congreso Nacional.",
        "reviewer": "ing_auditor_qa"
    })
    assert app_res.status_code == 200
    assert app_res.json()["approval_status"] == "approved"
    assert app_res.json()["reviewed_by"] == "ing_auditor_qa"

    # 3. Disparar ingestión hacia normative_memory (ahora debe ser exitosa)
    ingest_res = client.post(f"/api/v1/intake/sources/{source_id}/ingest")
    assert ingest_res.status_code == 200
    ingest_data = ingest_res.json()
    assert ingest_data["status"] == "ingested"
    assert ingest_data["target_memory"] == "normative_memory"

    # 4. Verificar que se creó el registro en NormativeDocument
    norm_in_db = db_session.query(NormativeDocument).filter(NormativeDocument.code == "DS-47-MINVU-TEST").first()
    assert norm_in_db is not None
    assert norm_in_db.title == "Decreto Supremo 47 MINVU"

def test_source_rejection(client):
    """Verifica el flujo de rechazo explícito de una fuente."""
    res = client.post("/api/v1/intake/sources", json={
        "source_type": "symbol_reference",
        "title": "Símbolos Obsoletos 1980",
        "discipline": "electrical"
    })
    source_id = res.json()["id"]

    rej_res = client.post(f"/api/v1/intake/sources/{source_id}/approval", json={
        "approved": False,
        "notes": "Estándar desactualizado. No usar en nuevos proyectos.",
        "reviewer": "lead_engineer"
    })
    assert rej_res.status_code == 200
    assert rej_res.json()["approval_status"] == "rejected"
    assert rej_res.json()["status"] == "rejected"

def test_filter_sources_endpoint(client):
    """Verifica el filtrado de fuentes por tipo y estado de aprobación."""
    res = client.get("/api/v1/intake/sources?source_type=analysis_document")
    assert res.status_code == 200
    sources = res.json()
    assert isinstance(sources, list)
    assert all(s["source_type"] == "analysis_document" for s in sources)
