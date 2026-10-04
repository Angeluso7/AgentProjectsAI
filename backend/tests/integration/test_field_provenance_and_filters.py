import os
import io
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import SessionLocal, engine, Base
from app.db.models.intake import SourceAsset
from app.db.models.intake_extractions import (
    SourceExtraction, ExtractedItem, RuleDocument, RuleDocumentItem,
    StructuredTable, StructuredSymbol, StructuredEquipment, StructuredRulePremise
)
from app.db.models.core import Organization

client = TestClient(app)

@pytest.fixture
def db_session():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Asegurar organización de prueba
        org = db.query(Organization).first()
        if not org:
            org = Organization(
                id="test-org-filters-001",
                name="Organización Test Filtros",
                slug="org-test-filtros",
                status="active"
            )
            db.add(org)
            db.commit()
        yield db
    finally:
        db.close()


def test_filters_by_type_and_completeness_orthogonal_model(db_session: Session):
    """
    1. Filtros por tipo de elemento y por completitud en la lista principal.
    2. Valida que completeness_status y review_status sean totalmente independientes.
    """
    # 1. Crear sesión de extracción
    r_sess = client.post("/api/v1/intake/extractions/create-manual", json={
        "title": "Documento Técnico Filtros y Completitud",
        "document_type": "manual",
        "discipline": "Mecánica",
        "authority": "ASME"
    })
    assert r_sess.status_code == 201
    extraction_id = r_sess.json()["id"]

    # 2. Agregar elementos variados con estados ortogonales
    # Item 1: Regla Completa en Borrador (complete + draft)
    r1 = client.post(f"/api/v1/intake/extractions/{extraction_id}/items", json={
        "item_type": "rule",
        "title": "Presión Máxima de Operación en Línea de Impulsión",
        "code_or_number": "REG-MEC-01",
        "description": "La presión manométrica no debe exceder 150 PSI en régimen continuo.",
        "completeness_status": "complete",
        "review_status": "draft",
        "page_number": 1
    })
    assert r1.status_code == 201
    item1_id = r1.json()["id"]

    # Item 2: Símbolo Parcial por Confirmar (partial + to_confirm)
    r2 = client.post(f"/api/v1/intake/extractions/{extraction_id}/items", json={
        "item_type": "symbol",
        "title": "Válvula Reguladora de Flujo FCV-10",
        "code_or_number": "SYM-01",
        "description": "Símbolo de válvula de control.",
        "completeness_status": "partial",
        "review_status": "to_confirm",
        "page_number": 1
    })
    assert r2.status_code == 201
    item2_id = r2.json()["id"]

    # Item 3: Tabla con Datos Faltantes Aceptada (missing_data + accepted)
    r3 = client.post(f"/api/v1/intake/extractions/{extraction_id}/items", json={
        "item_type": "table",
        "title": "Tabla 2.1 - Diámetros Nominales",
        "code_or_number": "TAB-2.1",
        "description": "Cuadro preliminar",
        "completeness_status": "missing_data",
        "review_status": "accepted",
        "page_number": 2
    })
    assert r3.status_code == 201
    item3_id = r3.json()["id"]

    # Item 4: Equipo con Sugerencia Web en Borrador (web_suggested + draft)
    r4 = client.post(f"/api/v1/intake/extractions/{extraction_id}/items", json={
        "item_type": "equipment",
        "title": "Bomba Centrífuga P-101A",
        "code_or_number": "P-101A",
        "description": "Bomba de impulsión de agua tratada",
        "suggested_function": "Impulsión de caudal continuo hacia estanque de almacenamiento.",
        "suggested_source_label": "Catálogo ANSI/HI",
        "completeness_status": "web_suggested",
        "review_status": "draft",
        "page_number": 3
    })
    assert r4.status_code == 201
    item4_id = r4.json()["id"]

    # 3. Validar filtros en endpoint GET /items
    # A) Filtrar por item_type = symbol
    res_sym = client.get(f"/api/v1/intake/extractions/{extraction_id}/items?item_type=symbol")
    assert res_sym.status_code == 200
    sym_items = res_sym.json()
    assert len(sym_items) == 1
    assert sym_items[0]["id"] == item2_id
    assert sym_items[0]["item_type"] == "symbol"

    # B) Filtrar por completeness_status = complete (debe traer solo la regla, independientemente de review_status)
    res_comp = client.get(f"/api/v1/intake/extractions/{extraction_id}/items?completeness_status=complete")
    assert res_comp.status_code == 200
    comp_items = res_comp.json()
    assert len(comp_items) == 1
    assert comp_items[0]["id"] == item1_id
    assert comp_items[0]["review_status"] == "draft" # Ortogonal!

    # C) Filtrar por review_status = accepted (debe traer solo la tabla, independientemente de completeness_status)
    res_acc = client.get(f"/api/v1/intake/extractions/{extraction_id}/items?review_status=accepted")
    assert res_acc.status_code == 200
    acc_items = res_acc.json()
    assert len(acc_items) == 1
    assert acc_items[0]["id"] == item3_id
    assert acc_items[0]["completeness_status"] == "missing_data" # Ortogonal!

    # D) Validar estadísticas agregadas en vivo
    res_stats = client.get(f"/api/v1/intake/extractions/{extraction_id}/stats")
    assert res_stats.status_code == 200
    stats = res_stats.json()
    assert stats["total_items"] == 4
    assert stats["reviewed_count"] == 1
    assert stats["pending_count"] == 3
    assert stats["complete_count"] == 1
    assert stats["partial_count"] == 1
    assert stats["missing_data_count"] == 1
    assert stats["web_suggested_count"] == 1
    assert stats["by_item_type"]["rule"] == 1
    assert stats["by_item_type"]["symbol"] == 1
    assert stats["by_item_type"]["table"] == 1
    assert stats["by_item_type"]["equipment"] == 1


def test_granular_field_acceptance_and_provenance_patch(db_session: Session):
    """
    2. Aceptación parcial por campo y trazabilidad estricta (field_provenance).
    """
    # 1. Crear sesión de extracción
    r_sess = client.post("/api/v1/intake/extractions/create-manual", json={
        "title": "Documento Enriquecimiento Parcial",
        "document_type": "manual",
        "discipline": "Piping"
    })
    extraction_id = r_sess.json()["id"]

    # 2. Agregar ítem con sugerencias de IA
    r_item = client.post(f"/api/v1/intake/extractions/{extraction_id}/items", json={
        "item_type": "symbol",
        "title": "VALVULA RET 2\"",
        "code_or_number": "V-201",
        "description": "Válvula en plano",
        "ocr_text": "VALVULA RETENCION 2 PULGADAS",
        "suggested_title": "Válvula de Retención (Check Valve / Antirretorno) 2\"",
        "suggested_description": "Válvula unidireccional para prevención de golpe de ariete según ASME B16.34.",
        "suggested_function": "Protección de bombas evitando contraflujo en línea de impulsión.",
        "suggested_source_label": "Norma ASME B16.34",
        "suggested_source_url": "https://www.asme.org/codes-standards",
        "completeness_status": "web_suggested",
        "review_status": "draft"
    })
    item_id = r_item.json()["id"]

    # 3. Aplicar únicamente el parche del campo 'function' sin modificar el título original
    res_patch = client.patch(
        f"/api/v1/intake/extractions/{extraction_id}/items/{item_id}/accept-field",
        json={
            "field_name": "function",
            "accepted_value": "Protección de bombas evitando contraflujo en línea de impulsión.",
            "accepted_from": "suggested_value",
            "user_id": "auditor_especialista"
        }
    )
    assert res_patch.status_code == 200
    patched_data = res_patch.json()

    # Verificar que el título siga siendo el original
    assert patched_data["title"] == "VALVULA RET 2\""
    # Verificar que la función técnica fue actualizada
    assert patched_data["technical_parameters"]["function_or_role"] == "Protección de bombas evitando contraflujo en línea de impulsión."
    
    # Verificar trazabilidad en field_provenance
    prov = patched_data["field_provenance"]
    assert "function" in prov
    assert prov["function"]["accepted_value"] == "Protección de bombas evitando contraflujo en línea de impulsión."
    assert prov["function"]["accepted_from"] == "suggested_value"
    assert prov["function"]["updated_by"] == "auditor_especialista"
    assert prov["function"]["suggestion_source"] == "Norma ASME B16.34"

    # Verificar que el review_status no se alteró indeseadamente
    assert patched_data["review_status"] == "draft"


def test_structured_persistence_by_type(db_session: Session):
    """
    3. Persistencia estructurada incremental en tablas tipadas (structured_tables,
       structured_symbols, structured_equipment, structured_rules_premises).
    """
    r_sess = client.post("/api/v1/intake/extractions/create-manual", json={
        "title": "Documento de Persistencia Estructurada",
        "document_type": "norma",
        "discipline": "General"
    })
    extraction_id = r_sess.json()["id"]

    # 1. Crear Tabla
    r_tab = client.post(f"/api/v1/intake/extractions/{extraction_id}/items", json={
        "item_type": "table",
        "title": "Cuadro de Cargas Eléctricas",
        "code_or_number": "TAB-ELEC-01",
        "description": "Distribución de potencia por circuito",
        "structured_matrix": {
            "headers": ["Circuito", "Potencia (W)", "Interruptor (A)"],
            "rows": [
                ["C-1 Alumbrado", 1800, 10],
                ["C-2 Enchufes", 2200, 16],
                ["C-3 Clima", 3500, 20]
            ]
        },
        "review_status": "accepted"
    })
    assert r_tab.status_code == 201
    tab_item_id = r_tab.json()["id"]

    # 2. Crear Símbolo
    r_sym = client.post(f"/api/v1/intake/extractions/{extraction_id}/items", json={
        "item_type": "symbol",
        "title": "Símbolo Pulsador Manual de Alarma",
        "code_or_number": "SYM-ALM-01",
        "technical_parameters": {
            "standard_family": "NFPA-72",
            "category": "Detección de Incendio",
            "primary_discipline": "Seguridad Contra Incendios"
        },
        "review_status": "accepted"
    })
    assert r_sym.status_code == 201
    sym_item_id = r_sym.json()["id"]

    # 3. Crear Equipo
    r_eq = client.post(f"/api/v1/intake/extractions/{extraction_id}/items", json={
        "item_type": "equipment",
        "title": "Transformador Trifásico Seco 500 kVA",
        "code_or_number": "TR-01",
        "technical_parameters": {
            "equipment_type": "Transformador",
            "manufacturer": "Schneider Electric",
            "rated_capacity": "500 kVA",
            "voltage_primary": "12 kV",
            "voltage_secondary": "380 V"
        },
        "review_status": "accepted"
    })
    assert r_eq.status_code == 201
    eq_item_id = r_eq.json()["id"]

    # 4. Crear Regla
    r_rule = client.post(f"/api/v1/intake/extractions/{extraction_id}/items", json={
        "item_type": "rule",
        "title": "Resistencia al Fuego de Muros Medianeros",
        "code_or_number": "REG-OGUC-4.3.3",
        "content_text": "Los muros divisorios entre unidades habitacionales deben cumplir F-120 como mínimo.",
        "technical_parameters": {
            "min_fire_rating": "F-120",
            "zone": "medianero"
        },
        "review_status": "accepted"
    })
    assert r_rule.status_code == 201
    rule_item_id = r_rule.json()["id"]

    # Verificar en PostgreSQL que las 4 tablas hijas estructuradas contengan sus filas tipadas
    st = db_session.query(StructuredTable).filter(StructuredTable.extracted_item_id == tab_item_id).first()
    assert st is not None
    assert st.table_code == "TAB-ELEC-01"
    assert st.num_rows == 3
    assert st.num_cols == 3
    assert len(st.headers) == 3

    ss = db_session.query(StructuredSymbol).filter(StructuredSymbol.extracted_item_id == sym_item_id).first()
    assert ss is not None
    assert ss.symbol_name == "Símbolo Pulsador Manual de Alarma"
    assert ss.standard_family == "NFPA-72"

    seq = db_session.query(StructuredEquipment).filter(StructuredEquipment.extracted_item_id == eq_item_id).first()
    assert seq is not None
    assert seq.tag_code == "TR-01"
    assert seq.manufacturer == "Schneider Electric"
    assert seq.rated_capacity == "500 kVA"

    srp = db_session.query(StructuredRulePremise).filter(StructuredRulePremise.extracted_item_id == rule_item_id).first()
    assert srp is not None
    assert srp.rule_code == "REG-OGUC-4.3.3"
    assert "F-120" in srp.statement


def test_real_document_pdf_workflow_with_filters_and_provenance(db_session: Session):
    """
    4. Prueba de flujo sobre PDF real: Carga, recorte, OCR, filtrado por tipo/completitud y aceptación parcial.
    """
    pdf_bytes = (
        b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
        b"xref\n0 4\n0000000000 65535 f\n0000000010 00000 n\n0000000060 00000 n\n0000000117 00000 n\n"
        b"trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n180\n%%EOF"
    )
    
    files = {
        'file': ('Manual_OGUC_Criterios_Tecnicos.pdf', io.BytesIO(pdf_bytes), 'application/pdf')
    }
    form_data = {
        'title': 'Manual OGUC - Criterios Técnicos y Estándares',
        'source_type': 'normative_document',
        'discipline': 'Arquitectura',
        'document_type': 'norma',
        'authority': 'MINVU'
    }
    
    res_upload = client.post("/api/v1/intake/sources/upload", data=form_data, files=files)
    assert res_upload.status_code == 201
    source_id = res_upload.json()["id"]

    # Crear extracción manual asistida ligada a la fuente
    r_sess = client.post("/api/v1/intake/extractions/create-manual", json={
        "title": "Extracción Asistida OGUC",
        "document_type": "norma",
        "discipline": "Arquitectura",
        "authority": "MINVU",
        "source_asset_id": source_id
    })
    assert r_sess.status_code == 201
    extraction_id = r_sess.json()["id"]

    # Agregar 1 regla y 1 símbolo extraídos de la lámina
    r_item1 = client.post(f"/api/v1/intake/extractions/{extraction_id}/items", json={
        "item_type": "rule",
        "title": "Ancho Mínimo de Pasillo de Circulación",
        "code_or_number": "Art. 4.1.7",
        "description": "El ancho libre de pasillos principales no debe ser inferior a 1.20 metros.",
        "ocr_text": "Art. 4.1.7 Ancho libre pasillos 1.20m",
        "page_number": 1,
        "completeness_status": "complete",
        "review_status": "to_confirm"
    })
    assert r_item1.status_code == 201

    r_item2 = client.post(f"/api/v1/intake/extractions/{extraction_id}/items", json={
        "item_type": "symbol",
        "title": "Símbolo Extintor PQS 10kg",
        "code_or_number": "EXT-10",
        "description": "Ubicación de extintor",
        "crop_image_path": "https://storage.local/crops/extintor_pqs_10kg.png",
        "page_number": 1,
        "completeness_status": "partial",
        "review_status": "to_confirm"
    })
    assert r_item2.status_code == 201
    item2_id = r_item2.json()["id"]

    # Aplicar parche granular por campo en el símbolo
    client.patch(
        f"/api/v1/intake/extractions/{extraction_id}/items/{item2_id}/accept-field",
        json={
            "field_name": "function",
            "accepted_value": "Extinción de fuegos clase ABC en vías de evacuación.",
            "accepted_from": "suggested_value",
            "user_id": "auditor_arquitectura"
        }
    )

    # Validar filtrado cruzado
    res_filt = client.get(f"/api/v1/intake/extractions/{extraction_id}/items?item_type=symbol&completeness_status=complete")
    assert res_filt.status_code == 200
    assert len(res_filt.json()) == 1
    assert res_filt.json()[0]["id"] == item2_id
