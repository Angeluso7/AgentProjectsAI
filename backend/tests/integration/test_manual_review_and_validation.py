import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import get_db
from app.db.models.intake_extractions import SourceExtraction, ExtractedItem, RuleDocument, RuleDocumentItem, SupportingKnowledgeItem
from app.db.models.intake import SourceAsset
from app.db.models.core import Organization

client = TestClient(app)

def test_manual_review_and_validation_flow():
    """
    Test completo del flujo de revisión y validación manual asistida:
    1. Crear sesión manual sin IA
    2. Agregar elementos gráficos (símbolo, tabla, figura) y reglas de texto
    3. Manejar estados individuales: draft, editado, por_confirmar, validada, eliminado
    4. Commit selectivo de solo elementos en 'validada'
    5. Verificación de persistencia en RuleDocument, RuleDocumentItem y SupportingKnowledgeItem
    """
    # 1. Crear sesión manual
    session_res = client.post("/api/v1/intake/extractions/create-manual", json={
        "title": "Manual de Seguridad y Accesibilidad 2026",
        "document_type": "manual",
        "authority": "MINVU",
        "discipline": "Arquitectura",
        "source_file_path": "/data/test_manual.pdf"
    })
    assert session_res.status_code == 201
    session_data = session_res.json()
    extraction_id = session_data["id"]

    # 2. Agregar elemento 1: Símbolo Gráfico (Base de Conocimiento)
    item1_res = client.post(f"/api/v1/intake/extractions/{extraction_id}/items", json={
        "item_type": "simbolo",
        "title": "Símbolo Internacional de Accesibilidad (SIA)",
        "description": "Pictograma azul y blanco normativo para puertas y rampas.",
        "page_number": 1,
        "bbox_normalized": [0.1, 0.1, 0.3, 0.3],
        "target_destination": "knowledge_base",
        "review_status": "draft"
    })
    assert item1_res.status_code == 201
    item1_id = item1_res.json()["id"]

    # 3. Agregar elemento 2: Tabla Técnica (con matriz estructurada)
    item2_res = client.post(f"/api/v1/intake/extractions/{extraction_id}/items", json={
        "item_type": "tabla",
        "title": "Tabla 2.1 - Pendientes Máximas de Rampas",
        "description": "Cuadro de pendientes longitudinales según longitud del tramo.",
        "page_number": 2,
        "bbox_normalized": [0.2, 0.4, 0.8, 0.7],
        "target_destination": "knowledge_base",
        "review_status": "draft",
        "structured_matrix": {
            "columns": ["Tramo (m)", "Pendiente Máx (%)"],
            "rows": [["Hasta 1.5m", "12%"], ["Hasta 3.0m", "10%"], ["Más de 3.0m", "8%"]]
        }
    })
    assert item2_res.status_code == 201
    item2_id = item2_res.json()["id"]

    # 4. Agregar elemento 3: Regla Técnica QA/QC
    item3_res = client.post(f"/api/v1/intake/extractions/{extraction_id}/items", json={
        "item_type": "rule",
        "code_or_number": "REG-ARQ-P1",
        "title": "REG-ARQ-P1: Ancho Libre en Pasillos de Evacuación",
        "description": "El ancho mínimo libre de pasillos en áreas de acceso público será de 1.40 m.",
        "content_text": "El ancho mínimo libre de pasillos en áreas de acceso público será de 1.40 m.",
        "ocr_text": "Art. 4.1.7 Pasillos de evacuación...",
        "page_number": 1,
        "bbox_normalized": [0.1, 0.7, 0.9, 0.9],
        "target_destination": "rules_engine",
        "review_status": "draft"
    })
    assert item3_res.status_code == 201
    item3_id = item3_res.json()["id"]

    # 5. Agregar elemento 4: Elemento a descartar/eliminar
    item4_res = client.post(f"/api/v1/intake/extractions/{extraction_id}/items", json={
        "item_type": "foto",
        "title": "Foto Borrosa a Descartar",
        "page_number": 3,
        "review_status": "draft"
    })
    assert item4_res.status_code == 201
    item4_id = item4_res.json()["id"]

    # 6. Actualizar Estados Individuales:
    # - Item 1 (Símbolo): Validada
    up1 = client.put(f"/api/v1/intake/extractions/{extraction_id}/items/{item1_id}", json={
        "review_status": "validada"
    })
    assert up1.status_code == 200
    assert up1.json()["review_status"] == "validada"

    # - Item 2 (Tabla): Por Confirmar (debe quedar pendiente para más adelante)
    up2 = client.put(f"/api/v1/intake/extractions/{extraction_id}/items/{item2_id}", json={
        "review_status": "por_confirmar"
    })
    assert up2.status_code == 200
    assert up2.json()["review_status"] == "por_confirmar"

    # - Item 3 (Regla): Validada
    up3 = client.put(f"/api/v1/intake/extractions/{extraction_id}/items/{item3_id}", json={
        "review_status": "validada"
    })
    assert up3.status_code == 200
    assert up3.json()["review_status"] == "validada"

    # - Item 4: Eliminar
    del_res = client.delete(f"/api/v1/intake/extractions/{extraction_id}/items/{item4_id}")
    assert del_res.status_code == 200

    # 7. Ejecutar Commit Final de solo elementos validados (Item 1 e Item 3)
    commit_res = client.post(f"/api/v1/intake/extractions/{extraction_id}/commit", json={
        "approved_item_ids": [item1_id, item3_id],
        "target_rule_document_title": "Manual de Seguridad Validado 2026"
    })
    assert commit_res.status_code == 200
    commit_data = commit_res.json()
    assert commit_data["rules_incorporated_count"] == 2
    assert commit_data["knowledge_entries_created_count"] == 1 # 1 elemento gráfico en SupportingKnowledgeItem (el Símbolo)

    # 8. Verificar que la sesión quedó con estado 'reviewed' porque el Item 2 quedó en 'por_confirmar'
    detail_res = client.get(f"/api/v1/intake/extractions/{extraction_id}")
    assert detail_res.status_code == 200
    detail_data = detail_res.json()
    assert detail_data["status"] == "reviewed"
    
    # Comprobar que el Item 2 sigue en la sesión en estado 'por_confirmar'
    item2_in_db = next((i for i in detail_data["items"] if i["id"] == item2_id), None)
    assert item2_in_db is not None
    assert item2_in_db["review_status"] == "por_confirmar"
