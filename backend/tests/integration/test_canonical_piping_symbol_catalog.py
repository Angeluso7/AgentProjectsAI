import os
import uuid
import hashlib
import tempfile
import numpy as np
import cv2
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.core import Organization, Project
from app.db.models.document_memory import Document, DocumentSheet, DetectedSymbol
from app.db.models.intake_extractions import SourceExtraction, ExtractedItem, StructuredSymbol
from app.db.models.template_memory import SymbolTemplate
from app.db.models.symbol_catalog import (
    SymbolTemplateVersion,
    SymbolGeometricFeature,
    SymbolFeatureRelation,
    SymbolSourceEvidence,
    SymbolReviewDecision,
    SymbolUnknownResearchCase,
)
from app.services.symbols.canonical_catalog_service import CanonicalPipingCatalogService


def _draw_synthetic_gate_valve_image(angle: int = 0) -> np.ndarray:
    """
    Genera un recorte de imagen sintético etiquetado explícitamente como 'synthetic'
    para la familia PIP-VALVE-GATE (Válvula de compuerta manual).
    Geometría: Dos triángulos concurrentes en vértice central + vástago + volante superior.
    """
    img = np.ones((80, 80, 3), dtype=np.uint8) * 255

    # Dos triángulos concurrentes en vértice central (40, 45)
    pts_left = np.array([[15, 30], [15, 60], [40, 45]], np.int32)
    pts_right = np.array([[65, 30], [65, 60], [40, 45]], np.int32)
    cv2.fillPoly(img, [pts_left], (30, 30, 30))
    cv2.fillPoly(img, [pts_right], (30, 30, 30))

    # Vástago perpendicular desde vértice (40, 45) hasta (40, 20)
    cv2.line(img, (40, 45), (40, 20), (20, 20, 20), 2)

    # Volante superior (28, 20) a (52, 20)
    cv2.line(img, (28, 20), (52, 20), (20, 20, 20), 3)

    if angle != 0:
        center = (40, 40)
        rot_mat = cv2.getRotationMatrix2D(center, angle, 1.0)
        img = cv2.warpAffine(img, rot_mat, (80, 80), borderValue=(255, 255, 255))

    return img


def _draw_synthetic_check_valve_image() -> np.ndarray:
    """
    Genera un recorte sintético de Válvula Check (Retención),
    que difiere topológica y geométricamente de la válvula de compuerta.
    """
    img = np.ones((80, 80, 3), dtype=np.uint8) * 255
    pts = np.array([[20, 25], [20, 55], [55, 40]], np.int32)
    cv2.fillPoly(img, [pts], (40, 40, 40))
    cv2.line(img, (55, 20), (55, 60), (30, 30, 30), 2)
    return img


@pytest.fixture
def synthetic_temp_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


def _create_test_document_and_sheet(db_session: Session):
    """Crea documento y lámina padre requeridos por foreign keys de DetectedSymbol."""
    org = Organization(id=str(uuid.uuid4()), name="Test Org", slug=f"org-{uuid.uuid4().hex[:6]}")
    proj = Project(id=str(uuid.uuid4()), organization_id=org.id, name="Test Project", code="PRJ-TEST")
    doc = Document(
        id=str(uuid.uuid4()),
        organization_id=org.id,
        project_id=proj.id,
        filename="test_p_and_id.pdf",
        file_path="/tmp/test.pdf",
        file_hash_sha256=f"hash_{uuid.uuid4().hex}",
        file_size_bytes=1024,
        status="uploaded"
    )
    sheet = DocumentSheet(
        id=str(uuid.uuid4()),
        document_id=doc.id,
        sheet_number=1,
        title="P&ID Sheet 01",
        width_px=1000,
        height_px=1000
    )
    db_session.add_all([org, proj, doc, sheet])
    db_session.flush()
    return doc, sheet


def _create_detected_symbol(
    db_session: Session,
    crop_path: str,
    geometric_evidence: bool = True,
    geometric_confidence: float = 0.90,
    classification: str = "symbol",
    inner_drawing_bbox: list = None,
    symbol_crop_bbox: list = None,
    context_text: str = None
) -> DetectedSymbol:
    doc, sheet = _create_test_document_and_sheet(db_session)
    sym = DetectedSymbol(
        id=str(uuid.uuid4()),
        document_id=doc.id,
        sheet_id=sheet.id,
        symbol_type="valve",
        bbox=[200, 200, 280, 280],
        bbox_normalized=[0.2, 0.2, 0.28, 0.28],
        confidence=0.95,
        geometric_evidence=geometric_evidence,
        geometric_confidence=geometric_confidence,
        classification=classification,
        inner_drawing_bbox=inner_drawing_bbox or [215, 220, 265, 260],
        symbol_crop_bbox=symbol_crop_bbox or [200, 200, 280, 280],
        crop_image_path=crop_path,
        context_text=context_text,
        matching_status="unconfirmed"
    )
    db_session.add(sym)
    db_session.flush()
    return sym


def test_promote_candidate_to_canonical_with_explicit_evidence(client: TestClient, db_session: Session, synthetic_temp_dir):
    """
    Verifica la promoción HITL de un StructuredSymbol validado con evidencia geométrica física
    hacia SymbolTemplate canónico versionado, con rasgos geométricos y evidencia de origen tipificada 'synthetic'.
    """
    crop_img = _draw_synthetic_gate_valve_image(0)
    crop_path = os.path.join(synthetic_temp_dir, "synthetic_gate_valve_orig.png")
    cv2.imwrite(crop_path, crop_img)
    with open(crop_path, "rb") as f:
        crop_hash = hashlib.sha256(f.read()).hexdigest()

    org = Organization(id=str(uuid.uuid4()), name="Test Org", slug=f"org-{uuid.uuid4().hex[:6]}")
    db_session.add(org)
    db_session.flush()

    extraction = SourceExtraction(
        id=str(uuid.uuid4()),
        organization_id=org.id,
        title="Norma Piping Fixture",
        status="extracted",
        discipline="piping"
    )
    db_session.add(extraction)
    db_session.flush()

    item = ExtractedItem(
        id=str(uuid.uuid4()),
        extraction_id=extraction.id,
        title="Gate Valve Symbol",
        page_number=1,
        item_type="symbol",
        candidate_type="symbol_candidate",
        bbox_normalized=[0.1, 0.1, 0.2, 0.2]
    )
    db_session.add(item)
    db_session.flush()

    candidate = StructuredSymbol(
        id=str(uuid.uuid4()),
        extracted_item_id=item.id,
        symbol_name="Válvula de Compuerta Manual",
        canonical_symbol_family="valves",
        discipline="piping",
        source_render_mode="vector",
        layout_context="inside_table",
        crop_image_path=crop_path,
        confidence_score=0.96
    )
    db_session.add(candidate)
    db_session.commit()

    payload = {
        "candidate_id": candidate.id,
        "canonical_code": "PIP-VALVE-GATE",
        "canonical_name": "Manual Gate Valve",
        "category": "valve",
        "subcategory": "gate_valve",
        "discipline": "piping",
        "technical_function": "Block or isolate line fluid flow with wedge gate mechanism",
        "standard_reference": "PIP PNC00001 / ISA-5.1 Section 5.4",
        "evidence_kind": "synthetic",
        "orientation_policy": "rotation_equivalent_180",
        "reviewer_id": "piping_lead_engineer",
        "notes": "Aprobado para catálogo canónico inicial con evidencia sintética trazable."
    }

    resp = client.post("/api/v1/symbol-catalog/promote-candidate", json=payload)
    assert resp.status_code == 200, f"Error en promoción: {resp.text}"
    data = resp.json()

    assert data["canonical_code"] == "PIP-VALVE-GATE"
    assert data["template_id"] is not None
    assert data["version_id"] is not None
    assert data["version_number"] >= 1
    assert data["features_extracted"] >= 3

    # Verificar en BD
    tmpl = db_session.query(SymbolTemplate).filter(SymbolTemplate.id == data["template_id"]).first()
    assert tmpl is not None
    assert tmpl.canonical_code == "PIP-VALVE-GATE"
    assert tmpl.is_active_for_detection is True
    assert tmpl.status == "sandbox"

    version = db_session.query(SymbolTemplateVersion).filter(SymbolTemplateVersion.id == data["version_id"]).first()
    assert version is not None
    assert version.orientation_policy == "rotation_equivalent_180"
    assert version.approval_status == "sandbox_approved"
    assert len(version.geometric_features) >= 3
    assert version.source_evidence is not None
    assert version.source_evidence.evidence_kind == "synthetic"
    assert version.source_evidence.crop_image_hash == crop_hash


def test_matching_preconditions_strictly_enforced(client: TestClient, db_session: Session, synthetic_temp_dir):
    """
    Verifica que la precondición única de entrada a matching:
    geometric_evidence == true
    AND geometric_confidence >= configured threshold (0.70)
    AND classification == 'symbol'
    AND valid inner_drawing_bbox
    AND valid symbol_crop_bbox
    AND existing crop image
    sea estrictamente obligatoria, y que texto/OCR/tags no puedan bypassarla ni crear candidatos.
    """
    service = CanonicalPipingCatalogService(db_session)
    valid_crop = os.path.join(synthetic_temp_dir, "dummy_valid_crop.png")
    cv2.imwrite(valid_crop, _draw_synthetic_gate_valve_image(0))

    # 1. Fallo por geometric_evidence == False
    occ_no_geom = _create_detected_symbol(
        db_session, crop_path=valid_crop, geometric_evidence=False, geometric_confidence=0.90
    )
    valid, reason = service.validate_matching_preconditions(occ_no_geom)
    assert not valid
    assert "geometric_evidence=True" in reason

    # 2. Fallo por baja confianza geométrica (< 0.70)
    occ_low_conf = _create_detected_symbol(
        db_session, crop_path=valid_crop, geometric_evidence=True, geometric_confidence=0.55
    )
    valid, reason = service.validate_matching_preconditions(occ_low_conf)
    assert not valid
    assert "geometric_confidence" in reason

    # 3. Fallo por clasificación != 'symbol' (e.g. 'table_graphic', 'figure')
    occ_not_symbol = _create_detected_symbol(
        db_session, crop_path=valid_crop, classification="table_graphic"
    )
    valid, reason = service.validate_matching_preconditions(occ_not_symbol)
    assert not valid
    assert "classification == 'symbol'" in reason

    # 4. Fallo por ruta de crop inexistente
    occ_missing_crop = _create_detected_symbol(
        db_session, crop_path="/non_existent_crop_path_9999.png"
    )
    valid, reason = service.validate_matching_preconditions(occ_missing_crop)
    assert not valid
    assert "archivo de recorte no existe" in reason


def test_positive_progressive_matching_gate_valve_with_orientation_policy(client: TestClient, db_session: Session, synthetic_temp_dir):
    """
    Valida el matching progresivo multi-etapa para PIP-VALVE-GATE:
    - Etapa 1: Geometría (peso 0.35, umbral 0.60)
    - Etapa 2: Topología (peso 0.20, umbral 0.50)
    - Etapa 3: Similitud Visual (peso 0.35, umbral 0.50)
    - Etapa 4: Contexto semántico limitado (peso 0.10)
    Verifica rotación 180° soportada por la política rotation_equivalent_180.
    """
    # 1. Crear plantilla canónica de Gate Valve en BD
    tmpl = SymbolTemplate(
        id=str(uuid.uuid4()),
        symbol_class="gate_valve",
        display_name="Gate Valve",
        canonical_code="PIP-VALVE-GATE",
        canonical_name="Gate Valve",
        discipline="piping",
        category="valve",
        subcategory="gate_valve",
        is_active_for_detection=True,
        status="active"
    )
    db_session.add(tmpl)

    template_img = _draw_synthetic_gate_valve_image(0)
    tmpl_crop_path = os.path.join(synthetic_temp_dir, "template_gate_valve.png")
    cv2.imwrite(tmpl_crop_path, template_img)
    with open(tmpl_crop_path, "rb") as f:
        tmpl_hash = hashlib.sha256(f.read()).hexdigest()

    version = SymbolTemplateVersion(
        id=str(uuid.uuid4()),
        symbol_template_id=tmpl.id,
        version_number=1,
        approval_status="approved",
        canonical_crop_path=tmpl_crop_path,
        canonical_crop_hash=tmpl_hash,
        orientation_policy="rotation_equivalent_180",
        scale_policy="isotropic_bounded",
        geometric_signature={"aspect_ratio": 1.0, "density": 0.22},
        perceptual_signature={"hu_moments": [0.0] * 7, "mask_hash": tmpl_hash}
    )
    db_session.add(version)
    tmpl.current_version_id = version.id

    evidence = SymbolSourceEvidence(
        symbol_template_version_id=version.id,
        evidence_kind="real_authorized",
        source_standard_or_project="PIP PNC00001",
        crop_image_path=tmpl_crop_path,
        crop_image_hash=tmpl_hash,
        page_number=1,
        bbox_normalized=[0.1, 0.1, 0.9, 0.9]
    )
    db_session.add(evidence)
    db_session.commit()

    # 2. Ocurrencia rotada 180°
    cand_img_180 = _draw_synthetic_gate_valve_image(180)
    cand_path_180 = os.path.join(synthetic_temp_dir, "occurrence_gate_valve_180.png")
    cv2.imwrite(cand_path_180, cand_img_180)

    occ = _create_detected_symbol(
        db_session,
        crop_path=cand_path_180,
        geometric_evidence=True,
        geometric_confidence=0.88,
        classification="symbol",
        context_text="GATE VALVE 150# RF"
    )
    db_session.commit()

    match_req = {
        "occurrence_id": str(occ.id),
        "discipline": "piping"
    }
    resp = client.post("/api/v1/symbol-catalog/match-occurrence", json=match_req)
    assert resp.status_code == 200, f"Matching falló: {resp.text}"
    data = resp.json()

    assert data["matching_status"] == "matched"
    assert data["best_match"] is not None
    assert data["best_match"]["canonical_code"] == "PIP-VALVE-GATE"
    assert data["best_match"]["template_id"] == tmpl.id
    assert data["best_match"]["total_score"] >= 0.70
    assert data["best_match"]["geometric_score"] >= 0.60
    assert data["best_match"]["context_score"] <= 0.10

    # Verificar actualización de DetectedSymbol
    updated_occ = db_session.query(DetectedSymbol).filter(DetectedSymbol.id == occ.id).first()
    assert updated_occ.matching_status == "matched"
    assert updated_occ.matched_template_id == tmpl.id
    assert updated_occ.detected_tag_or_code == "PIP-VALVE-GATE"


def test_negative_matching_and_unknown_symbol_research_case(client: TestClient, db_session: Session, synthetic_temp_dir):
    """
    Verifica que una ocurrencia con geometría real válida pero distinta (Check Valve):
    1. No haga match con PIP-VALVE-GATE.
    2. Sea catalogada como 'unknown_symbol' sin inventar match forzado.
    3. Registre un SymbolUnknownResearchCase para investigación posterior.
    """
    tmpl = SymbolTemplate(
        id=str(uuid.uuid4()),
        symbol_class="gate_valve",
        display_name="Gate Valve",
        canonical_code="PIP-VALVE-GATE",
        canonical_name="Gate Valve",
        discipline="piping",
        category="valve",
        subcategory="gate_valve",
        is_active_for_detection=True,
        status="active"
    )
    db_session.add(tmpl)

    template_img = _draw_synthetic_gate_valve_image(0)
    tmpl_crop_path = os.path.join(synthetic_temp_dir, "template_gate_valve_neg.png")
    cv2.imwrite(tmpl_crop_path, template_img)

    version = SymbolTemplateVersion(
        id=str(uuid.uuid4()),
        symbol_template_id=tmpl.id,
        version_number=1,
        approval_status="approved",
        canonical_crop_path=tmpl_crop_path,
        orientation_policy="rotation_equivalent_180"
    )
    db_session.add(version)
    tmpl.current_version_id = version.id

    evidence = SymbolSourceEvidence(
        symbol_template_version_id=version.id,
        evidence_kind="real_authorized",
        source_standard_or_project="PIP PNC00001",
        crop_image_path=tmpl_crop_path,
        crop_image_hash="dummy_hash_neg",
        page_number=1,
        bbox_normalized=[0.1, 0.1, 0.9, 0.9]
    )
    db_session.add(evidence)
    db_session.commit()

    check_img = _draw_synthetic_check_valve_image()
    check_path = os.path.join(synthetic_temp_dir, "occurrence_check_valve.png")
    cv2.imwrite(check_path, check_img)

    occ = _create_detected_symbol(
        db_session,
        crop_path=check_path,
        geometric_evidence=True,
        geometric_confidence=0.85,
        classification="symbol",
        context_text="CHECK VALVE CV-201"
    )
    db_session.commit()

    match_req = {
        "occurrence_id": str(occ.id),
        "discipline": "piping"
    }
    resp = client.post("/api/v1/symbol-catalog/match-occurrence", json=match_req)
    assert resp.status_code == 200
    data = resp.json()

    assert data["matching_status"] == "unknown_symbol"

    # Verificar caso de investigación registrado
    research_case = db_session.query(SymbolUnknownResearchCase).filter(
        SymbolUnknownResearchCase.symbol_occurrence_id == str(occ.id)
    ).first()
    assert research_case is not None
    assert research_case.status == "unknown"


def test_context_never_rescues_insufficient_geometry(client: TestClient, db_session: Session, synthetic_temp_dir):
    """
    Regla 10 y 12: El contexto semántico (OCR/tags) tiene peso máximo 0.10 y NUNCA
    rescata un candidato con geometría insuficiente (geometric_score < 0.60).
    """
    tmpl = SymbolTemplate(
        id=str(uuid.uuid4()),
        symbol_class="gate_valve",
        display_name="Gate Valve",
        canonical_code="PIP-VALVE-GATE",
        canonical_name="Gate Valve",
        discipline="piping",
        category="valve",
        subcategory="gate_valve",
        is_active_for_detection=True,
        status="active"
    )
    db_session.add(tmpl)

    template_img = _draw_synthetic_gate_valve_image(0)
    tmpl_crop_path = os.path.join(synthetic_temp_dir, "template_gate_valve_resc.png")
    cv2.imwrite(tmpl_crop_path, template_img)

    version = SymbolTemplateVersion(
        id=str(uuid.uuid4()),
        symbol_template_id=tmpl.id,
        version_number=1,
        approval_status="approved",
        canonical_crop_path=tmpl_crop_path,
        orientation_policy="rotation_equivalent_180"
    )
    db_session.add(version)
    tmpl.current_version_id = version.id

    evidence = SymbolSourceEvidence(
        symbol_template_version_id=version.id,
        evidence_kind="real_authorized",
        source_standard_or_project="PIP PNC00001",
        crop_image_path=tmpl_crop_path,
        crop_image_hash="dummy_hash_resc",
        page_number=1,
        bbox_normalized=[0.1, 0.1, 0.9, 0.9]
    )
    db_session.add(evidence)
    db_session.commit()

    # Imagen incompatible (Check) con texto perfecto de Gate Valve
    check_img = _draw_synthetic_check_valve_image()
    check_path = os.path.join(synthetic_temp_dir, "occurrence_fake_context.png")
    cv2.imwrite(check_path, check_img)

    occ = _create_detected_symbol(
        db_session,
        crop_path=check_path,
        geometric_evidence=True,
        geometric_confidence=0.82,
        classification="symbol",
        context_text="PIP-VALVE-GATE GATE VALVE MANUAL ASME B16.34"
    )
    db_session.commit()

    match_req = {
        "occurrence_id": str(occ.id),
        "discipline": "piping"
    }
    resp = client.post("/api/v1/symbol-catalog/match-occurrence", json=match_req)
    assert resp.status_code == 200
    data = resp.json()

    # NO DEBE ser 'matched', a pesar de coincidencia textual
    assert data["matching_status"] != "matched"


def test_human_review_decision_non_destructive(client: TestClient, db_session: Session, synthetic_temp_dir):
    """
    Verifica que la decisión de revisión humana HITL registre un SymbolReviewDecision
    con trazabilidad sin sobreescrituras destructivas del linaje histórico.
    """
    valid_crop = os.path.join(synthetic_temp_dir, "dummy_crop.png")
    cv2.imwrite(valid_crop, _draw_synthetic_gate_valve_image(0))

    occ = _create_detected_symbol(
        db_session,
        crop_path=valid_crop,
        geometric_evidence=True,
        geometric_confidence=0.85,
        classification="symbol"
    )
    occ.matching_status = "unknown_symbol"
    occ.review_status = "unreviewed"
    db_session.commit()

    decision_req = {
        "subject_type": "occurrence",
        "subject_id": str(occ.id),
        "decision": "approve",
        "reviewer_id": "piping_supervisor",
        "rationale": "Confirmado visualmente por supervisor de piping."
    }

    resp = client.post("/api/v1/symbol-catalog/decisions", json=decision_req)
    assert resp.status_code == 200, f"Error en decision: {resp.text}"
    data = resp.json()

    assert data["decision"] == "approve"
    assert data["reviewer_id"] == "piping_supervisor"

    # Verificar registro en BD
    decision_rec = db_session.query(SymbolReviewDecision).filter(
        SymbolReviewDecision.id == data["decision_id"]
    ).first()
    assert decision_rec is not None
    assert decision_rec.reviewer_id == "piping_supervisor"
    assert decision_rec.previous_state.get("matching_status") == "unknown_symbol"

    # Verificar actualización en ocurrencia
    updated_occ = db_session.query(DetectedSymbol).filter(DetectedSymbol.id == occ.id).first()
    assert updated_occ.review_status == "accepted"


def test_query_canonical_templates_and_occurrences_endpoints(client: TestClient, db_session: Session, synthetic_temp_dir):
    """
    Verifica endpoints GET /templates, GET /templates/{id}, GET /occurrences y GET /research-cases.
    """
    tmpl = SymbolTemplate(
        id=str(uuid.uuid4()),
        symbol_class="gate_valve",
        display_name="Gate Valve",
        canonical_code="PIP-VALVE-GATE",
        canonical_name="Gate Valve",
        discipline="piping",
        category="valve",
        subcategory="gate_valve",
        is_active_for_detection=True,
        status="active"
    )
    db_session.add(tmpl)

    template_img = _draw_synthetic_gate_valve_image(0)
    tmpl_crop_path = os.path.join(synthetic_temp_dir, "template_query.png")
    cv2.imwrite(tmpl_crop_path, template_img)

    version = SymbolTemplateVersion(
        id=str(uuid.uuid4()),
        symbol_template_id=tmpl.id,
        version_number=1,
        approval_status="approved",
        canonical_crop_path=tmpl_crop_path,
        orientation_policy="rotation_equivalent_180"
    )
    db_session.add(version)
    tmpl.current_version_id = version.id
    db_session.commit()

    # 1. GET /templates
    resp = client.get("/api/v1/symbol-catalog/templates")
    assert resp.status_code == 200
    templates_list = resp.json()
    assert len(templates_list) >= 1
    assert any(t["canonical_code"] == "PIP-VALVE-GATE" for t in templates_list)

    # 2. GET /templates/{id}
    resp = client.get(f"/api/v1/symbol-catalog/templates/{tmpl.id}")
    assert resp.status_code == 200
    tmpl_detail = resp.json()
    assert tmpl_detail["id"] == tmpl.id
    assert tmpl_detail["canonical_code"] == "PIP-VALVE-GATE"
    assert len(tmpl_detail["versions"]) == 1

    # 3. GET /occurrences
    occ = _create_detected_symbol(db_session, crop_path=tmpl_crop_path)
    occ.record_kind = "occurrence"
    occ.matching_status = "matched"
    occ.detected_tag_or_code = "PIP-VALVE-GATE"
    db_session.commit()

    resp = client.get("/api/v1/symbol-catalog/occurrences?matching_status=matched")
    assert resp.status_code == 200
    occ_data = resp.json()
    assert occ_data["total"] >= 1
    assert any(item["id"] == str(occ.id) for item in occ_data["items"])
    # Verificar que entrega metadatos de navegación contextual
    first_item = next(item for item in occ_data["items"] if item["id"] == str(occ.id))
    assert "context_navigation" in first_item
    assert first_item["context_navigation"]["document_id"] is not None
    assert first_item["page_number"] >= 1

    # 4. GET /research-cases
    rc = SymbolUnknownResearchCase(
        id=str(uuid.uuid4()),
        symbol_occurrence_id=str(occ.id),
        status="unknown",
        research_notes="Investigando símbolo piping sin normalizar."
    )
    db_session.add(rc)
    db_session.commit()

    resp = client.get("/api/v1/symbol-catalog/research-cases")
    assert resp.status_code == 200
    rc_list = resp.json()
    assert len(rc_list) >= 1
    assert any(c["id"] == rc.id for c in rc_list)


def test_symbol_template_not_promoted_to_rule_definition(db_session: Session):
    """
    Regla 12 de Gobernanza:
    SymbolTemplate nunca se promueve ni se transforma en RuleDefinition.
    Los símbolos pertenecen al catálogo canónico visual/topológico de componentes físicos;
    las reglas normativas (RuleDefinition) codifican cláusulas y criterios de auditoría textuales.
    """
    from app.db.models.decision_memory import RuleDefinition

    tmpl = SymbolTemplate(
        id=str(uuid.uuid4()),
        symbol_class="gate_valve",
        display_name="Gate Valve",
        canonical_code="PIP-VALVE-GATE",
        status="active"
    )
    db_session.add(tmpl)
    db_session.commit()

    # Verificar que el catálogo de plantillas está completamente disjunto de las reglas normativas
    rule = db_session.query(RuleDefinition).filter(RuleDefinition.code == tmpl.canonical_code).first()
    assert rule is None, "Violación: Un SymbolTemplate fue catalogado erróneamente como RuleDefinition."


# ====================================================================
# NUEVAS PRUEBAS: GOBERNANZA, CANDIDATO VS OCURRENCIA, Y MATCHING
# ====================================================================

def test_governance_synthetic_fixture_cannot_activate_production_template(client: TestClient, db_session: Session, synthetic_temp_dir):
    """
    Política de Gobernanza (Sección A):
    Si toda la evidencia de una plantilla es 'synthetic':
    - NO puede quedar 'active' ni su versión como 'approved' para producción.
    - Debe quedar 'sandbox' / 'sandbox_approved' o 'test_only'.
    - Intentar aprobarla como productiva debe lanzar violación de gobernanza.
    """
    service = CanonicalPipingCatalogService(db_session)
    tmpl = SymbolTemplate(
        id=str(uuid.uuid4()),
        canonical_code="PIP-VALVE-GATE-TEST",
        canonical_name="Gate Valve Synthetic Test",
        display_name="Gate Valve Synthetic Test",
        symbol_class="gate_valve",
        status="sandbox"
    )
    db_session.add(tmpl)

    crop_img = _draw_synthetic_gate_valve_image(0)
    crop_path = os.path.join(synthetic_temp_dir, "synthetic_only.png")
    cv2.imwrite(crop_path, crop_img)

    version = SymbolTemplateVersion(
        id=str(uuid.uuid4()),
        symbol_template_id=tmpl.id,
        version_number=1,
        approval_status="sandbox_approved",
        canonical_crop_path=crop_path
    )
    db_session.add(version)

    evidence = SymbolSourceEvidence(
        symbol_template_version_id=version.id,
        evidence_kind="synthetic",
        crop_image_path=crop_path,
        crop_image_hash="hash_synth_123",
        page_number=1,
        bbox_normalized=[0.1, 0.1, 0.9, 0.9]
    )
    db_session.add(evidence)
    db_session.commit()

    # Intentar forzar aprobación productiva debe ser bloqueado
    with pytest.raises(ValueError, match="Governance Violation: Cannot approve a template version backed solely by synthetic evidence"):
        service.approve_template_version_for_production(
            version_id=version.id,
            reviewer_id="auditor_lead",
            rationale="Intento no permitido de activar sintético en producción"
        )


def test_governance_real_authorized_evidence_with_hitl_approves_production(db_session: Session, synthetic_temp_dir):
    """
    Política de Gobernanza (Sección A):
    Una plantilla solo puede ser aprobada y activada como productiva si posee evidencia
    'real_authorized' o 'redacted_real' con hash, página, bbox, crop físico y decisión HITL.
    """
    service = CanonicalPipingCatalogService(db_session)
    tmpl = SymbolTemplate(
        id=str(uuid.uuid4()),
        canonical_code="PIP-VALVE-GATE-REAL",
        canonical_name="Gate Valve Real Standard",
        display_name="Gate Valve Real Standard",
        symbol_class="gate_valve",
        status="sandbox"
    )
    db_session.add(tmpl)

    crop_img = _draw_synthetic_gate_valve_image(0)
    crop_path = os.path.join(synthetic_temp_dir, "real_authorized_crop.png")
    cv2.imwrite(crop_path, crop_img)
    crop_hash = hashlib.sha256(open(crop_path, "rb").read()).hexdigest()

    version = SymbolTemplateVersion(
        id=str(uuid.uuid4()),
        symbol_template_id=tmpl.id,
        version_number=1,
        approval_status="pending_review",
        canonical_crop_path=crop_path
    )
    db_session.add(version)

    evidence = SymbolSourceEvidence(
        symbol_template_version_id=version.id,
        evidence_kind="real_authorized",
        source_standard_or_project="PIP PNC00001 Rev 2024",
        source_document_hash="sha256_standard_pdf_doc_hash_valid",
        crop_image_path=crop_path,
        crop_image_hash=crop_hash,
        page_number=12,
        bbox_normalized=[0.15, 0.25, 0.85, 0.85]
    )
    db_session.add(evidence)
    db_session.commit()

    # Aprobación formal HITL
    approved_ver = service.approve_template_version_for_production(
        version_id=version.id,
        reviewer_id="lead_hitl_engineer",
        rationale="Evidencia documental autorizada PIP PNC00001 verificada conforme a especificación técnica."
    )

    assert approved_ver.approval_status == "approved"
    assert approved_ver.approved_by == "lead_hitl_engineer"
    assert tmpl.status == "active"

    # Verificar registro inmutable en SymbolReviewDecision
    decision = db_session.query(SymbolReviewDecision).filter(
        SymbolReviewDecision.subject_id == version.id,
        SymbolReviewDecision.decision == "approve"
    ).first()
    assert decision is not None
    assert decision.reviewer_id == "lead_hitl_engineer"


def test_governance_incomplete_evidence_blocks_approval(db_session: Session, synthetic_temp_dir):
    """
    Política de Gobernanza (Sección A):
    Evidencia incompleta (ej. sin hash, página inválida, o sin bbox) rechaza la aprobación.
    """
    service = CanonicalPipingCatalogService(db_session)
    tmpl = SymbolTemplate(
        id=str(uuid.uuid4()),
        canonical_code="PIP-VALVE-GATE-INCOMPLETE",
        canonical_name="Gate Valve Incomplete",
        display_name="Gate Valve Incomplete",
        symbol_class="gate_valve",
        status="draft"
    )
    db_session.add(tmpl)

    crop_path = os.path.join(synthetic_temp_dir, "crop_incomplete.png")
    cv2.imwrite(crop_path, _draw_synthetic_gate_valve_image(0))

    version = SymbolTemplateVersion(id=str(uuid.uuid4()), symbol_template_id=tmpl.id, approval_status="pending_review")
    db_session.add(version)

    # Evidencia sin hashes ni bbox
    evidence = SymbolSourceEvidence(
        symbol_template_version_id=version.id,
        evidence_kind="real_authorized",
        page_number=0, # Inválido
        bbox_normalized=[], # Inválido
        crop_image_path=crop_path
    )
    db_session.add(evidence)
    db_session.commit()

    with pytest.raises(ValueError, match="Governance Violation: Incomplete evidence"):
        service.approve_template_version_for_production(
            version_id=version.id,
            reviewer_id="auditor",
            rationale="Debe fallar por evidencia incompleta"
        )


def test_candidate_vs_occurrence_differentiation(db_session: Session, synthetic_temp_dir):
    """
    Candidato vs Ocurrencia (Sección B):
    - Elemento sin precondiciones geométricas (ej. texto OCR o clasificación != 'symbol')
      se mantiene estrictamente como 'candidate' con matching_status='not_applicable'.
    - Elemento con precondiciones satisfechas transiciona a 'occurrence'.
    """
    service = CanonicalPipingCatalogService(db_session)
    valid_crop = os.path.join(synthetic_temp_dir, "cand_vs_occ_crop.png")
    cv2.imwrite(valid_crop, _draw_synthetic_gate_valve_image(0))

    # 1. Candidato clasificado como figura
    cand_fig = _create_detected_symbol(
        db_session,
        crop_path=valid_crop,
        classification="figure"
    )
    cand_fig.record_kind = "candidate"
    db_session.commit()

    resp_fig = service.match_occurrence(occurrence_id=str(cand_fig.id), discipline="piping")
    assert resp_fig.matching_status == "not_applicable"
    assert resp_fig.record_kind == "candidate"

    # Verificar que en BD sigue como candidate
    db_session.refresh(cand_fig)
    assert cand_fig.record_kind == "candidate"
    assert not cand_fig.is_occurrence

    # 2. Ocurrencia válida
    occ_valid = _create_detected_symbol(
        db_session,
        crop_path=valid_crop,
        geometric_evidence=True,
        geometric_confidence=0.92,
        classification="symbol"
    )
    db_session.commit()

    resp_valid = service.match_occurrence(
        occurrence_id=str(occ_valid.id),
        discipline="piping",
        execution_mode="sandbox"
    )
    assert resp_valid.record_kind == "occurrence"
    db_session.refresh(occ_valid)
    assert occ_valid.record_kind == "occurrence"
    assert occ_valid.is_occurrence


def test_ocr_text_without_geometry_generates_zero_occurrences(db_session: Session, synthetic_temp_dir):
    """
    Prueba Obligatoria (Sección B):
    Texto OCR 'gate valve' sin geometría visual válida no genera candidato válido ni ocurrencia.
    """
    service = CanonicalPipingCatalogService(db_session)
    dummy_crop = os.path.join(synthetic_temp_dir, "ocr_no_geom.png")
    cv2.imwrite(dummy_crop, np.ones((60, 60, 3), dtype=np.uint8) * 255)

    doc, sheet = _create_test_document_and_sheet(db_session)
    ocr_element = DetectedSymbol(
        id=str(uuid.uuid4()),
        document_id=doc.id,
        sheet_id=sheet.id,
        symbol_type="valve",
        bbox=[100, 100, 160, 160],
        bbox_normalized=[0.1, 0.1, 0.16, 0.16],
        confidence=0.99,
        geometric_evidence=False, # Sin geometría
        geometric_confidence=0.10,
        classification="not_symbol",
        inner_drawing_bbox=None,
        symbol_crop_bbox=None,
        crop_image_path=dummy_crop,
        context_text="gate valve high pressure shutoff",
        record_kind="candidate",
        matching_status="unconfirmed"
    )
    db_session.add(ocr_element)
    db_session.commit()

    res = service.match_occurrence(occurrence_id=str(ocr_element.id), discipline="piping")
    assert res.matching_status == "not_applicable"
    assert res.best_match is None
    db_session.refresh(ocr_element)
    assert ocr_element.record_kind == "candidate"
    assert not ocr_element.is_occurrence


def test_production_matching_against_test_only_template_yields_not_applicable(db_session: Session, synthetic_temp_dir):
    """
    Prueba Obligatoria (Sección B y E):
    Matching en modo 'production' contra una plantilla en 'sandbox' o 'test_only'
    devuelve 'not_applicable' o 'unknown_symbol', NUNCA 'matched'.
    """
    service = CanonicalPipingCatalogService(db_session)
    tmpl_crop = os.path.join(synthetic_temp_dir, "tmpl_sandbox_only.png")
    cv2.imwrite(tmpl_crop, _draw_synthetic_gate_valve_image(0))

    tmpl = SymbolTemplate(
        id=str(uuid.uuid4()),
        canonical_code="PIP-VALVE-GATE-SANDBOX",
        canonical_name="Gate Valve Sandbox",
        display_name="Gate Valve Sandbox",
        symbol_class="gate_valve",
        discipline="piping",
        status="sandbox" # No productiva
    )
    db_session.add(tmpl)

    version = SymbolTemplateVersion(
        id=str(uuid.uuid4()),
        symbol_template_id=tmpl.id,
        version_number=1,
        approval_status="sandbox_approved",
        canonical_crop_path=tmpl_crop,
        orientation_policy="rotation_equivalent_180"
    )
    db_session.add(version)

    evidence = SymbolSourceEvidence(
        symbol_template_version_id=version.id,
        evidence_kind="synthetic", # Sintética
        crop_image_path=tmpl_crop,
        crop_image_hash="hash_synth_test",
        page_number=1,
        bbox_normalized=[0.1, 0.1, 0.9, 0.9]
    )
    db_session.add(evidence)
    db_session.commit()

    # Ocurrencia con geometría idéntica
    cand_path = os.path.join(synthetic_temp_dir, "cand_for_sandbox.png")
    cv2.imwrite(cand_path, _draw_synthetic_gate_valve_image(0))
    occ = _create_detected_symbol(db_session, crop_path=cand_path, geometric_evidence=True, geometric_confidence=0.95)
    db_session.commit()

    # 1. Matching en MODO PRODUCCIÓN: Debe ser denegado / unknown
    resp_prod = service.match_occurrence(
        occurrence_id=str(occ.id),
        discipline="piping",
        execution_mode="production"
    )
    assert resp_prod.matching_status != "matched", "Violación: Se produjo match productivo contra plantilla sandbox."
    assert resp_prod.matching_status in ("not_applicable", "unknown_symbol")

    # 2. Matching en MODO SANDBOX: Permitido con aviso
    resp_sandbox = service.match_occurrence(
        occurrence_id=str(occ.id),
        discipline="piping",
        execution_mode="sandbox"
    )
    assert resp_sandbox.matching_status == "matched"
    assert resp_sandbox.is_sandbox_or_test_only is True
    assert resp_sandbox.warning is not None


def test_false_positive_disconnected_triangles_rejected(db_session: Session, synthetic_temp_dir):
    """
    Falsos Positivos (Sección E):
    Dos triángulos que no forman la topología de válvula (sin vértice central común)
    son penalizados fuertemente y rechazados.
    """
    service = CanonicalPipingCatalogService(db_session)
    # Crear dos triángulos separados por un espacio vacío central
    img_false = np.ones((80, 80, 3), dtype=np.uint8) * 255
    pts_left = np.array([[10, 30], [10, 60], [25, 45]], np.int32)
    pts_right = np.array([[70, 30], [70, 60], [55, 45]], np.int32)
    cv2.fillPoly(img_false, [pts_left], (30, 30, 30))
    cv2.fillPoly(img_false, [pts_right], (30, 30, 30))

    false_path = os.path.join(synthetic_temp_dir, "disconnected_triangles.png")
    cv2.imwrite(false_path, img_false)

    # Crear plantilla Gate Valve
    tmpl_crop = os.path.join(synthetic_temp_dir, "tmpl_gate_valve_fp.png")
    cv2.imwrite(tmpl_crop, _draw_synthetic_gate_valve_image(0))
    tmpl = SymbolTemplate(
        id=str(uuid.uuid4()),
        canonical_code="PIP-VALVE-GATE",
        canonical_name="Gate Valve",
        display_name="Gate Valve",
        status="active",
        symbol_class="gate_valve",
        discipline="piping"
    )
    db_session.add(tmpl)
    ver = SymbolTemplateVersion(id=str(uuid.uuid4()), symbol_template_id=tmpl.id, approval_status="approved", canonical_crop_path=tmpl_crop)
    db_session.add(ver)
    ev = SymbolSourceEvidence(symbol_template_version_id=ver.id, evidence_kind="real_authorized", crop_image_path=tmpl_crop, crop_image_hash="h1", page_number=1, bbox_normalized=[0,0,1,1])
    db_session.add(ev)
    db_session.commit()

    occ = _create_detected_symbol(db_session, crop_path=false_path, geometric_evidence=True, geometric_confidence=0.85)
    db_session.commit()

    res = service.match_occurrence(occurrence_id=str(occ.id), discipline="piping", execution_mode="production")
    assert res.matching_status != "matched"
    assert res.matching_status in ("unknown_symbol", "not_applicable")


def test_false_positive_table_border_contamination_rejected(db_session: Session, synthetic_temp_dir):
    """
    Falsos Positivos (Sección E):
    Crop con bordes densos de grilla/tabla es detectado como contaminado y penalizado.
    """
    service = CanonicalPipingCatalogService(db_session)
    img_contaminated = _draw_synthetic_gate_valve_image(0)
    # Contaminar los bordes superior e izquierdo con línea continua de tabla
    img_contaminated[0:3, :] = 0
    img_contaminated[:, 0:3] = 0

    contam_path = os.path.join(synthetic_temp_dir, "contaminated_crop.png")
    cv2.imwrite(contam_path, img_contaminated)

    tmpl_crop = os.path.join(synthetic_temp_dir, "tmpl_clean.png")
    cv2.imwrite(tmpl_crop, _draw_synthetic_gate_valve_image(0))
    tmpl = SymbolTemplate(
        id=str(uuid.uuid4()),
        canonical_code="PIP-VALVE-GATE",
        canonical_name="Gate Valve",
        display_name="Gate Valve",
        status="active",
        symbol_class="gate_valve",
        discipline="piping"
    )
    db_session.add(tmpl)
    ver = SymbolTemplateVersion(id=str(uuid.uuid4()), symbol_template_id=tmpl.id, approval_status="approved", canonical_crop_path=tmpl_crop)
    db_session.add(ver)
    ev = SymbolSourceEvidence(symbol_template_version_id=ver.id, evidence_kind="real_authorized", crop_image_path=tmpl_crop, crop_image_hash="h_clean", page_number=1, bbox_normalized=[0,0,1,1])
    db_session.add(ev)
    db_session.commit()

    occ = _create_detected_symbol(db_session, crop_path=contam_path, geometric_evidence=True, geometric_confidence=0.90)
    db_session.commit()

    res = service.match_occurrence(occurrence_id=str(occ.id), discipline="piping", execution_mode="production")
    assert res.matching_status != "matched"


def test_unknown_symbol_with_valid_geometry_creates_finding_and_research_case(db_session: Session, synthetic_temp_dir):
    """
    Símbolo Desconocido (Sección E):
    Símbolo con evidencia geométrica válida sin match canónico crea SymbolUnknownResearchCase
    con referencia a SYM-UNKNOWN-001 y NUNCA se auto-promueve automáticamente a plantilla.
    """
    service = CanonicalPipingCatalogService(db_session)
    # Forma poligonal geométrica desconocida
    img_unk = np.ones((80, 80, 3), dtype=np.uint8) * 255
    cv2.circle(img_unk, (40, 40), 20, (30, 30, 30), 2)
    cv2.line(img_unk, (20, 20), (60, 60), (30, 30, 30), 2)
    unk_path = os.path.join(synthetic_temp_dir, "unknown_valid_geom.png")
    cv2.imwrite(unk_path, img_unk)

    occ = _create_detected_symbol(
        db_session,
        crop_path=unk_path,
        geometric_evidence=True,
        geometric_confidence=0.94,
        classification="symbol"
    )
    db_session.commit()

    res = service.match_occurrence(occurrence_id=str(occ.id), discipline="piping", execution_mode="production")
    assert res.matching_status == "unknown_symbol"
    assert res.research_case_id is not None

    rc = db_session.query(SymbolUnknownResearchCase).filter(
        SymbolUnknownResearchCase.id == res.research_case_id
    ).first()
    assert rc is not None
    assert rc.status == "unknown"
    assert "SYM-UNKNOWN-001" in rc.research_notes

    # Verificar que NO se creó automáticamente una plantilla
    templates_count = db_session.query(SymbolTemplate).filter(
        SymbolTemplate.canonical_name == "SYM-UNKNOWN-001"
    ).count()
    assert templates_count == 0, "Violación: Un símbolo desconocido fue auto-promovido a plantilla sin decisión HITL."


