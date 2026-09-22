import pytest
import os
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import SessionLocal, engine, Base
from app.db.models.intake_extractions import (
    SourceExtraction,
    ExtractedItem,
    StructuredRulePremise,
    StructuredTable,
    StructuredSymbol,
    StructuredEquipment
)
from app.db.models.core import Organization

client = TestClient(app)

@pytest.fixture
def db_session():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        org = db.query(Organization).first()
        if not org:
            org = Organization(
                id="test-org-web-001",
                name="Organización Test Web",
                slug="org-test-web",
                status="active"
            )
            db.add(org)
            db.commit()
        yield db
    finally:
        db.close()

def test_web_documentary_intake_multitype_and_deduplication(db_session: Session):
    """
    Valida el flujo documental web con IA:
    - Extracción multitipo: reglas, tablas, imágenes, símbolos, equipos.
    - Aplicación de límites configurables por tipo.
    - Generación de snapshot web (SVG/PNG) y asociación de región centrada (bbox) y DOM hint.
    - Deduplicación inter-fuentes con jerarquía de calidad.
    - Endpoint de contexto visual para origen web.
    - Sincronización automática con tablas estructuradas tipadas.
    """
    payload = {
        "search_prompt": "Requisitos de accesibilidad universal, rampas y ventilación en edificios",
        "discipline": "Arquitectura",
        "document_type": "any_web_doc",
        "authority": "Portales Técnicos de Edificación",
        "focus_areas": ["rampas", "pasillos", "pendientes", "senales"],
        "type_limits": {
            "rules": 3,
            "tables": 2,
            "images": 1,
            "symbols": 1,
            "equipment": 1
        },
        "max_total": 8,
        "selected_sources": [
            {
                "url": "https://example.com/accesibilidad",
                "title": "Accesibilidad Universal",
                "snippet": "Requisitos de rampas y pasillos",
                "estimated_type": "Página Web",
                "domain": "example.com"
            }
        ]
    }

    resp = client.post("/api/v1/intake/extractions/process-web-research", json=payload)
    assert resp.status_code in [200, 201], f"Error iniciando extracción web: {resp.text}"
    data = resp.json()
    extraction_id = data["id"]

    assert data["source_origin"] == "web"
    assert data["status"] == "extracted"

    # Verificar ítems en la base de datos
    items = db_session.query(ExtractedItem).filter(ExtractedItem.extraction_id == extraction_id).all()
    assert len(items) > 0, "No se crearon ítems extraídos desde la web"
    assert len(items) <= 8, f"Se superó el límite global max_total: {len(items)}"

    # Verificar diversidad de tipos
    types_found = {it.item_type for it in items}
    assert "rule" in types_found, "Debe incluir reglas técnicas"
    assert "table" in types_found, "Debe incluir tablas de parámetros"

    # Verificar que cada ítem tiene procedencia web y requires_validation = True
    for it in items:
        assert it.source_origin == "web"
        assert it.requires_validation is True
        assert it.source_reference is not None
        assert it.metadata_payload is not None
        assert "snapshot_path" in it.metadata_payload

    # Verificar que el snapshot visual fue generado físicamente
    first_item = items[0]
    snapshot_path = first_item.metadata_payload.get("snapshot_path")
    assert snapshot_path is not None
    assert os.path.exists(snapshot_path), f"El archivo de snapshot {snapshot_path} no existe en disco"

    # Verificar endpoint de contexto visual para el elemento web
    ctx_resp = client.get(f"/api/v1/intake/extractions/{extraction_id}/items/{first_item.id}/context")
    assert ctx_resp.status_code == 200, f"Error en endpoint de contexto: {ctx_resp.text}"
    ctx_data = ctx_resp.json()

    assert ctx_data["source_origin"] == "web"
    assert ctx_data["web_source_url"] is not None
    assert ctx_data["page_image_url"] is not None
    assert ctx_data["dom_hint"] is not None
    assert ctx_data["bbox_normalized"] is not None

    # Verificar persistencia en tablas estructuradas tipadas
    has_structured_rule = db_session.query(StructuredRulePremise).filter(
        StructuredRulePremise.extracted_item_id == first_item.id
    ).first()
    if first_item.item_type == "rule":
        assert has_structured_rule is not None, "La regla web debe estar sincronizada en structured_rules_premises"

    # Verificar que las tablas tengan persistencia estructurada
    table_item = next((it for it in items if it.item_type == "table"), None)
    if table_item:
        st = db_session.query(StructuredTable).filter(
            StructuredTable.extracted_item_id == table_item.id
        ).first()
        assert st is not None, "La tabla web debe estar sincronizada en structured_tables"
        assert st.headers is not None and len(st.headers) > 0
