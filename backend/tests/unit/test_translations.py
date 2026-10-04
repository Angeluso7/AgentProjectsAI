import pytest
import uuid
from app.db.models.core import Organization
from app.db.models.translations import Translation
from app.schemas.translations import TranslationRequest, LanguageDetectionRequest
from app.services.translation.translation_service import (
    TranslationService,
    compute_canonical_text_hash,
    PROTECTED_TECHNICAL_TERMS
)


def test_compute_canonical_text_hash():
    """Verifica que el hash canónico sea invariante al orden de las claves e ignore espacios superfluos."""
    dict1 = {"title": "Gate Valve", "description": "Valvula principal"}
    dict2 = {"description": "Valvula principal", "title": "Gate Valve"}
    
    hash1 = compute_canonical_text_hash(dict1)
    hash2 = compute_canonical_text_hash(dict2)
    assert hash1 == hash2, "El hash canónico debe ser independiente del orden de las claves"
    
    # Cambio en un valor debe cambiar el hash
    dict3 = {"title": "Gate Valve Modified", "description": "Valvula principal"}
    assert compute_canonical_text_hash(dict3) != hash1


def test_detect_language(db_session):
    """Verifica la detección de idioma en textos técnicos."""
    svc = TranslationService(db_session)
    
    res_en = svc.detect_language("Output true only if all inputs are true. Qualified OR gate.")
    assert res_en.detected_language == "en"
    assert res_en.confidence >= 0.70
    
    res_es = svc.detect_language("Salida verdadera solo si todas las entradas son verdaderas. Compuerta OR.")
    assert res_es.detected_language == "es"
    assert res_es.confidence >= 0.70


def test_translation_caching_and_stale_marking(db_session):
    """Verifica el almacenamiento, caché O(1) y marcado de 'stale' cuando cambia la fuente."""
    # Crear organización de prueba
    org = Organization(id=str(uuid.uuid4()), name="Org Test Translations", slug=f"org-{uuid.uuid4().hex[:6]}")
    db_session.add(org)
    db_session.commit()
    
    svc = TranslationService(db_session)
    entity_id = str(uuid.uuid4())
    
    # 1. Primera traducción
    req1 = TranslationRequest(
        source_entity_type="extracted_item",
        source_entity_id=entity_id,
        target_language="es",
        source_language="en",
        fields_to_translate={
            "title": "Gate valve with pneumatic actuator",
            "description": "Process piping isolation per ANSI/ISA-5.1-2009",
            "technical_function": "Isolation valve in P&ID"
        },
        organization_id=org.id
    )
    
    res1 = svc.translate_entity_fields(req1, organization_id=org.id)
    assert res1.cached is False
    assert res1.translation_status == "completed"
    assert "Válvula de compuerta" in res1.translated_title or "válvula" in res1.translated_title.lower()
    assert "ANSI/ISA-5.1-2009" in res1.translated_fields.get("description", "")
    assert "P&ID" in res1.translated_fields.get("technical_function", "")
    
    # 2. Segunda petición idéntica: debe ser servida de CACHÉ
    res2 = svc.translate_entity_fields(req1, organization_id=org.id)
    assert res2.cached is True
    assert res2.id == res1.id
    assert res2.source_text_hash == res1.source_text_hash
    
    # 3. Modificación del texto fuente: el hash cambia y la versión anterior debe pasar a 'stale'
    req_modified = TranslationRequest(
        source_entity_type="extracted_item",
        source_entity_id=entity_id,
        target_language="es",
        source_language="en",
        fields_to_translate={
            "title": "Gate valve with electrical actuator",
            "description": "Updated process piping isolation per ANSI/ISA-5.1-2009",
            "technical_function": "Emergency shutdown valve in P&ID"
        },
        organization_id=org.id
    )
    
    res3 = svc.translate_entity_fields(req_modified, organization_id=org.id)
    assert res3.cached is False
    assert res3.id != res1.id
    assert res3.source_text_hash != res1.source_text_hash
    
    # Verificar que el registro original res1 quedó marcado como 'stale'
    old_trans = db_session.query(Translation).filter(Translation.id == res1.id).first()
    assert old_trans.translation_status == "stale", "La versión previa debe marcarse como stale al modificarse el texto fuente"


def test_tenancy_isolation(db_session):
    """Verifica que una organización no pueda acceder a las traducciones de otra organización."""
    org1 = Organization(id=str(uuid.uuid4()), name="Org 1", slug=f"org1-{uuid.uuid4().hex[:4]}")
    org2 = Organization(id=str(uuid.uuid4()), name="Org 2", slug=f"org2-{uuid.uuid4().hex[:4]}")
    db_session.add_all([org1, org2])
    db_session.commit()
    
    svc = TranslationService(db_session)
    entity_id = str(uuid.uuid4())
    
    req = TranslationRequest(
        source_entity_type="extracted_item",
        source_entity_id=entity_id,
        target_language="es",
        source_language="en",
        fields_to_translate={"title": "Check valve"},
        organization_id=org1.id
    )
    res = svc.translate_entity_fields(req, organization_id=org1.id)
    assert res.organization_id == org1.id
    
    # Intentar leer desde Org 2 debe retornar None
    forbidden = svc.get_entity_translation(
        source_entity_type="extracted_item",
        source_entity_id=entity_id,
        target_language="es",
        organization_id=org2.id
    )
    assert forbidden is None, "La consulta desde org2 no debe exponer traducciones pertenecientes a org1"


def test_preservation_of_protected_terms(db_session):
    """Verifica que acrónimos técnicos y normas no sean alterados en la traducción."""
    svc = TranslationService(db_session)
    
    text_with_standards = "Control system per ANSI/ISA-5.1-2009 with P&ID tag SYM-INS-01 connected to PLC, DCS and SIS."
    translated = svc._translate_text_segment(text_with_standards, "en", "es")
    
    for term in ["ANSI/ISA-5.1-2009", "P&ID", "PLC", "DCS", "SIS", "SYM-INS-01"]:
        assert term in translated, f"El término protegido '{term}' debe preservarse exactamente"
