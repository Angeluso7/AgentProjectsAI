import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import get_db
from app.db.models.intake_extractions import SourceExtraction, ExtractedItem
from app.db.repositories.intake_extraction_repository import IntakeExtractionRepository
from app.services.intake.ai_extractor import AiDocumentExtractorService


@pytest.fixture
def client(db_session: Session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_visual_split_creates_new_item_and_preserves_parent(db_session: Session):
    """
    Verifica que 'Separar elemento':
    1. Crea un nuevo elemento derivado con parent_item_id, is_derived=True y split_mode='visual_split'.
    2. Preserva la regla original (madre) 100% intacta sin modificaciones destructivas.
    """
    repo = IntakeExtractionRepository(db_session)
    org = repo.get_or_create_default_org()
    
    extraction = repo.create_extraction_session(
        title="Lámina de Instrumentación y Control",
        document_type="plano",
        authority="SEC / ISA",
        discipline="mecánica",
        extraction_mode="ai_document"
    )

    parent_item = repo.add_extracted_item(
        extraction_id=extraction.id,
        item_type="symbol",
        title="Tabla de Válvulas y Lazos Compuestos",
        code_or_number="SYM-PID-100",
        description="Lámina con múltiples instrumentos y lazos de control de nivel.",
        bbox_normalized=[0.05, 0.05, 0.95, 0.95],
        page_number=1,
        technical_parameters={"category": "Instrumentation"}
    )
    db_session.flush()

    service = AiDocumentExtractorService(db_session)
    derived_item = service.split_extracted_item(
        extraction_id=extraction.id,
        item_id=parent_item.id,
        bbox=[0.10, 0.20, 0.35, 0.45],
        title_hint="Válvula de Control Separada FCV-101",
        discipline="mecánica"
    )

    # 1. Validar nuevo elemento derivado
    assert derived_item is not None
    assert derived_item.id != parent_item.id
    assert derived_item.parent_item_id == parent_item.id
    assert derived_item.is_derived is True
    assert derived_item.split_mode == "visual_split"
    assert derived_item.title == "Válvula de Control Separada FCV-101"
    assert derived_item.bbox_normalized == [0.10, 0.20, 0.35, 0.45]
    assert derived_item.crop_image_path is not None
    assert derived_item.review_status == "to_confirm"
    assert derived_item.metadata_payload["derivation_type"] == "visual_split"
    assert derived_item.metadata_payload["parent_item_id"] == parent_item.id

    # 2. Validar que la regla madre (parent) permanece 100% intacta
    reloaded_parent = repo.get_extracted_item_by_id(parent_item.id)
    assert reloaded_parent is not None
    assert reloaded_parent.title == "Tabla de Válvulas y Lazos Compuestos"
    assert reloaded_parent.code_or_number == "SYM-PID-100"
    assert reloaded_parent.bbox_normalized == [0.05, 0.05, 0.95, 0.95]
    assert reloaded_parent.is_derived is False
    assert reloaded_parent.parent_item_id is None


def test_crop_current_item_updates_in_place_and_keeps_audit_history(db_session: Session):
    """
    Verifica que 'Recortar':
    1. Actualiza la imagen y bbox de la regla actual sin crear una nueva regla.
    2. Registra el historial de recortes previos en previous_crop_history para auditoría.
    """
    repo = IntakeExtractionRepository(db_session)
    org = repo.get_or_create_default_org()
    
    extraction = repo.create_extraction_session(
        title="Especificación de Bombas Centrífugas",
        document_type="ficha_tecnica",
        authority="ASME",
        discipline="mecánica",
        extraction_mode="ai_document"
    )

    item = repo.add_extracted_item(
        extraction_id=extraction.id,
        item_type="equipment",
        title="Bomba Centrífuga Multietapa P-201",
        code_or_number="EQ-P-201",
        description="Bomba centrífuga de alta presión con marco amplio.",
        crop_image_path="/data/crops/extractions/initial_pump.png",
        bbox_normalized=[0.0, 0.0, 1.0, 1.0],
        page_number=2
    )
    db_session.flush()

    service = AiDocumentExtractorService(db_session)
    updated_item = service.crop_extracted_item(
        extraction_id=extraction.id,
        item_id=item.id,
        bbox=[0.25, 0.25, 0.75, 0.75],
        user_id="lead_reviewer"
    )

    # 1. Validar que no se creó un nuevo item
    items = repo.list_extracted_items(extraction.id)
    assert len(items) == 1
    assert items[0].id == item.id

    # 2. Validar que el item actual fue actualizado
    assert updated_item.id == item.id
    assert updated_item.bbox_normalized == [0.25, 0.25, 0.75, 0.75]
    assert updated_item.split_mode == "crop_current_item"
    assert updated_item.crop_image_path != "/data/crops/extractions/initial_pump.png"
    assert "crop" in updated_item.crop_image_path

    # 3. Validar historial de auditoría
    history = updated_item.metadata_payload.get("previous_crop_history", [])
    assert len(history) == 1
    assert history[0]["previous_crop_image_path"] == "/data/crops/extractions/initial_pump.png"
    assert history[0]["previous_bbox"] == [0.0, 0.0, 1.0, 1.0]
    assert history[0]["user_id"] == "lead_reviewer"


def test_extract_free_text_paragraph_rules_structural_filtering(db_session: Session):
    """
    Verifica que el extractor de párrafos de texto libre:
    1. Descarta tablas, figuras/diagramas, headers/footers y etiquetas aisladas.
    2. Identifica párrafos normativos y de especificación relevantes.
    3. Formula candidatos estructurados con resumen técnico en español, keywords y review_status='to_confirm'.
    """
    service = AiDocumentExtractorService(db_session)

    mixed_document_text = """
    Página 12 de 45

    | ID | Diámetro | Presión Nominal | Material |
    |---|---|---|---|
    | V-01 | 2" | Class 150 | Acero Carbono |
    | V-02 | 4" | Class 300 | Acero Inox 316 |

    FIGURA 3.2: Detalle de montaje de válvula de retención y filtro Y en succión de bombas.

    TAG: P-101

    Todas las tuberías de impulsión de agua potable deben contar con válvula de retención antes del medidor general para evitar reflujo hacia la red pública de distribución.

    Los alimentadores eléctricos de fuerza motriz deben canalizarse en tubería metálica galvanizada con índice de protección mínimo IP65 cuando se instalen a la intemperie o en ambientes húmedos.
    """

    candidates = service.extract_free_text_paragraph_rules(
        text_content=mixed_document_text,
        discipline="instalaciones",
        document_type="norma",
        page_number=12,
        source_reference="NCh 2485 / SEC"
    )

    # Debe haber exactamente 2 candidatos de regla extraídos (la tabla, la figura y el header fueron descartados)
    assert len(candidates) == 2

    # Validar candidato 1 (Tuberías de impulsión)
    c1 = candidates[0]
    assert "tuberías de impulsión" in c1["summary"].lower() or "tuberías de impulsión" in c1["title"].lower()
    assert "válvula de retención" in c1["rule_statement"].lower()
    assert c1["discipline"] == "instalaciones"
    assert c1["confidence"] >= 0.90
    assert c1["review_status"] == "to_confirm"
    assert len(c1["keywords"]) > 0

    # Validar candidato 2 (Alimentadores eléctricos)
    c2 = candidates[1]
    assert "alimentadores eléctricos" in c2["summary"].lower() or "alimentadores eléctricos" in c2["title"].lower()
    assert "ip65" in c2["rule_statement"].lower()
    assert c2["page_reference"] == "Pág. 12"


def test_api_endpoints_split_crop_and_free_text_paragraphs(client: TestClient, db_session: Session):
    """
    Prueba de integración de los 3 endpoints API creados:
    1. POST /api/v1/intake/extractions/{ext_id}/items/{item_id}/split
    2. PATCH /api/v1/intake/extractions/{ext_id}/items/{item_id}/crop
    3. POST /api/v1/intake/extractions/extract-paragraph-rules
    """
    repo = IntakeExtractionRepository(db_session)
    org = repo.get_or_create_default_org()

    extraction = repo.create_extraction_session(
        title="Prueba de Endpoints Split Crop",
        document_type="manual",
        authority="ISA",
        discipline="eléctrica",
        extraction_mode="ai_document"
    )

    item = repo.add_extracted_item(
        extraction_id=extraction.id,
        item_type="rule",
        title="Regla de Tableros Principales",
        code_or_number="REG-ELEC-01",
        description="Dimensionamiento de barras de cobre y canalizaciones.",
        bbox_normalized=[0.1, 0.1, 0.9, 0.9],
        page_number=1
    )
    db_session.flush()

    # 1. Endpoint Split
    split_payload = {
        "bbox": [0.15, 0.15, 0.45, 0.45],
        "title_hint": "Subregla de Interruptores Termomagnéticos",
        "discipline": "eléctrica",
        "user_id": "reviewer_01"
    }
    split_res = client.post(f"/api/v1/intake/extractions/{extraction.id}/items/{item.id}/split", json=split_payload)
    assert split_res.status_code == 201
    split_data = split_res.json()
    assert split_data["parent_item_id"] == item.id
    assert split_data["is_derived"] is True
    assert split_data["split_mode"] == "visual_split"
    assert split_data["title"] == "Subregla de Interruptores Termomagnéticos"

    # 2. Endpoint Crop
    crop_payload = {
        "bbox": [0.2, 0.2, 0.8, 0.8],
        "user_id": "reviewer_01"
    }
    crop_res = client.patch(f"/api/v1/intake/extractions/{extraction.id}/items/{item.id}/crop", json=crop_payload)
    assert crop_res.status_code == 200
    crop_data = crop_res.json()
    assert crop_data["id"] == item.id
    assert crop_data["bbox_normalized"] == [0.2, 0.2, 0.8, 0.8]
    assert crop_data["split_mode"] == "crop_current_item"

    # 3. Endpoint Extract Paragraph Rules
    para_payload = {
        "text_content": "Los conductores de puesta a tierra de protección deben ser continuos y de color verde o verde con franja amarilla en toda su extensión.",
        "discipline": "eléctrica",
        "document_type": "norma",
        "page_number": 3,
        "source_reference": "Pliego Técnico RIC N° 06"
    }
    para_res = client.post("/api/v1/intake/extractions/extract-paragraph-rules", json=para_payload)
    assert para_res.status_code == 200
    para_data = para_res.json()
    assert para_data["total_paragraphs_detected"] == 1
    candidate = para_data["rules_candidates"][0]
    assert "puesta a tierra" in candidate["rule_statement"].lower()
    assert candidate["discipline"] == "eléctrica"
    assert candidate["review_status"] == "to_confirm"
