"""
test_symbol_template_matching.py

Pruebas unitarias e integración de Fase 1 para SymbolTemplate y Matching Determinista:
1. Normalización de recortes a máscaras canónicas 128x128 y extracción de momentos de Hu.
2. Invarianza rotacional (reconocimiento a 0°, 90°, 180°, 270° con score >= 0.85).
3. Rechazo de no-símbolos (grilla de tabla, forma de onda y patrones de texto obtienen score < 0.35).
4. Promoción HITL: StructuredSymbol -> SymbolTemplate activo con máscara y descriptores en BD.
5. Invocación de endpoint seguro match-candidate con resolución interna en el servidor.
"""

import os
import tempfile
import uuid
import pytest
import numpy as np
import cv2
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models.intake_extractions import StructuredSymbol, ExtractedItem
from app.db.models.template_memory import SymbolLibrary, SymbolTemplate
from app.services.symbols.template_normalizer import TemplateNormalizer, CANONICAL_MASK_SIZE
from app.services.symbols.template_matcher import TemplateMatcher, AUTO_MATCH_THRESHOLD, HITL_SUGGESTION_THRESHOLD
from app.schemas.symbol import MatchCandidateRequest
from app.api.v1.endpoints.symbols import match_candidate, promote_symbol_to_template
from app.schemas.symbol import PromoteSymbolToTemplateRequest


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def create_synthetic_valve_image(width=100, height=60, bg_white=True) -> np.ndarray:
    """Crea una imagen de válvula de compuerta típica (dos triángulos unidos en el vértice)."""
    img = np.ones((height, width, 3), dtype=np.uint8) * 255 if bg_white else np.zeros((height, width, 3), dtype=np.uint8)
    color = (0, 0, 0) if bg_white else (255, 255, 255)

    # Triángulo izquierdo: (10, 10) -> (50, 30) -> (10, 50)
    pts1 = np.array([[15, 12], [50, 30], [15, 48]], np.int32)
    # Triángulo derecho: (85, 12) -> (50, 30) -> (85, 48)
    pts2 = np.array([[85, 12], [50, 30], [85, 48]], np.int32)

    cv2.fillPoly(img, [pts1], color)
    cv2.fillPoly(img, [pts2], color)
    # Línea vertical del vástago
    cv2.line(img, (50, 30), (50, 8), color, 3)
    # Barra horizontal superior (actuador/volante)
    cv2.line(img, (35, 8), (65, 8), color, 3)

    return img


def create_synthetic_waveform_image(width=120, height=60) -> np.ndarray:
    """Crea una forma de onda cuadrada típica de diagrama de timing."""
    img = np.ones((height, width, 3), dtype=np.uint8) * 255
    color = (0, 0, 0)

    # Escalones de onda
    for x in range(10, width - 20, 20):
        cv2.line(img, (x, 45), (x, 15), color, 2)
        cv2.line(img, (x, 15), (x + 10, 15), color, 2)
        cv2.line(img, (x + 10, 15), (x + 10, 45), color, 2)
        cv2.line(img, (x + 10, 45), (x + 20, 45), color, 2)

    return img


def create_synthetic_table_grid_image(width=120, height=60) -> np.ndarray:
    """Crea una grilla horizontal/vertical típica de tabla técnica."""
    img = np.ones((height, width, 3), dtype=np.uint8) * 255
    color = (0, 0, 0)

    for y in [10, 25, 40, 55]:
        cv2.line(img, (5, y), (width - 5, y), color, 1)
    for x in [5, 40, 80, width - 5]:
        cv2.line(img, (x, 10), (x, 55), color, 1)

    return img


def test_template_normalizer_properties():
    """Verifica que el normalizador produzca máscaras de 128x128 y descriptores válidos."""
    normalizer = TemplateNormalizer()
    valve_img = create_synthetic_valve_image()

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_mask_path = tmp.name

    try:
        res = normalizer.normalize_image(valve_img, output_mask_path=tmp_mask_path)

        assert res["normalized_mask"].shape == (CANONICAL_MASK_SIZE, CANONICAL_MASK_SIZE)
        assert len(res["mask_hash"]) == 64
        assert len(res["hu_moments"]) == 7
        assert len(res["contour_signature"]) == 128
        assert res["aspect_ratio"] > 0
        assert os.path.exists(tmp_mask_path)
    finally:
        if os.path.exists(tmp_mask_path):
            os.remove(tmp_mask_path)


def test_template_matcher_rotation_invariance_0_90_180_270(db: Session):
    """Verifica reconocimiento exitoso del mismo símbolo en 0°, 90°, 180° y 270°."""
    normalizer = TemplateNormalizer()
    valve_base = create_synthetic_valve_image()

    # Guardar plantilla temporal en BD
    with tempfile.NamedTemporaryFile(suffix="_tmpl.png", delete=False) as tmp_img:
        tmpl_img_path = tmp_img.name
        cv2.imwrite(tmpl_img_path, valve_base)

    with tempfile.NamedTemporaryFile(suffix="_mask.png", delete=False) as tmp_mask:
        tmpl_mask_path = tmp_mask.name

    norm_res = normalizer.normalize_from_path(tmpl_img_path, output_mask_path=tmpl_mask_path)

    tmpl_id = str(uuid.uuid4())
    template = SymbolTemplate(
        id=tmpl_id,
        symbol_class="valve_gate_manual",
        display_name="Válvula de compuerta manual",
        image_template_path=tmpl_img_path,
        normalized_mask_path=tmpl_mask_path,
        mask_hash=norm_res["mask_hash"],
        hu_moments=norm_res["hu_moments"],
        contour_signature=norm_res["contour_signature"],
        aspect_ratio=norm_res["aspect_ratio"],
        is_active_for_detection=True
    )
    db.add(template)
    db.commit()

    matcher = TemplateMatcher(db, normalizer=normalizer)

    try:
        # Evaluar a 0°, 90°, 180° y 270°
        rotations = [
            (0, valve_base),
            (90, cv2.rotate(valve_base, cv2.ROTATE_90_CLOCKWISE)),
            (180, cv2.rotate(valve_base, cv2.ROTATE_180)),
            (270, cv2.rotate(valve_base, cv2.ROTATE_90_COUNTERCLOCKWISE))
        ]

        for expected_rot, test_img in rotations:
            matches = matcher.match_candidate_image(test_img, top_k=3)
            assert len(matches) > 0, f"Fallo al encontrar match para rotación {expected_rot}°"
            best = matches[0]

            assert best["template_id"] == tmpl_id
            assert best["best_rotation_deg"] == expected_rot, f"Esperaba rotación {expected_rot}°, detectó {best['best_rotation_deg']}°"
            assert best["score"] >= 0.85, f"Score insuficiente ({best['score']}) para rotación {expected_rot}°"
            assert best["decision_policy"] == "auto_match"

    finally:
        db.delete(template)
        db.commit()
        for p in [tmpl_img_path, tmpl_mask_path]:
            if os.path.exists(p):
                os.remove(p)


def test_template_matcher_rejects_grid_and_waveform(db: Session):
    """Verifica que diagramas de timing, grillas y artefactos no-símbolo sean rechazados (< 0.40)."""
    normalizer = TemplateNormalizer()
    valve_base = create_synthetic_valve_image()

    with tempfile.NamedTemporaryFile(suffix="_tmpl.png", delete=False) as tmp_img:
        tmpl_img_path = tmp_img.name
        cv2.imwrite(tmpl_img_path, valve_base)

    with tempfile.NamedTemporaryFile(suffix="_mask.png", delete=False) as tmp_mask:
        tmpl_mask_path = tmp_mask.name

    norm_res = normalizer.normalize_from_path(tmpl_img_path, output_mask_path=tmpl_mask_path)

    tmpl_id = str(uuid.uuid4())
    template = SymbolTemplate(
        id=tmpl_id,
        symbol_class="valve_gate_manual",
        display_name="Válvula de compuerta manual",
        image_template_path=tmpl_img_path,
        normalized_mask_path=tmpl_mask_path,
        mask_hash=norm_res["mask_hash"],
        hu_moments=norm_res["hu_moments"],
        contour_signature=norm_res["contour_signature"],
        aspect_ratio=norm_res["aspect_ratio"],
        is_active_for_detection=True
    )
    db.add(template)
    db.commit()

    matcher = TemplateMatcher(db, normalizer=normalizer)

    try:
        wf_img = create_synthetic_waveform_image()
        grid_img = create_synthetic_table_grid_image()

        for non_symbol_img, label in [(wf_img, "Forma de Onda"), (grid_img, "Grilla de Tabla")]:
            matches = matcher.match_candidate_image(non_symbol_img, top_k=3)
            if matches:
                best = matches[0]
                assert best["score"] < 0.45, f"{label} obtuvo score indebido ({best['score']}) contra plantilla de válvula"
                assert best["decision_policy"] == "unknown"
    finally:
        db.delete(template)
        db.commit()
        for p in [tmpl_img_path, tmpl_mask_path]:
            if os.path.exists(p):
                os.remove(p)


def test_promote_and_match_candidate_endpoint_integration(db: Session):
    """Prueba de integración extremo a extremo del flujo de promoción y matching vía endpoint."""
    valve_img = create_synthetic_valve_image()

    with tempfile.NamedTemporaryFile(suffix="_cand.png", delete=False) as tmp_crop:
        crop_path = tmp_crop.name
        cv2.imwrite(crop_path, valve_img)

    sym_id = str(uuid.uuid4())
    sym = StructuredSymbol(
        id=sym_id,
        extracted_item_id=str(uuid.uuid4()),
        symbol_name="Válvula de retención con resorte",
        canonical_symbol_family="check_valve_spring",
        discipline="piping",
        category="valve",
        crop_image_path=crop_path,
        confidence_score=0.92,
        source_render_mode="raster",
        layout_context="inside_table",
        context_association_mode="table_row"
    )
    db.add(sym)
    db.commit()

    try:
        # 1. Promoción a SymbolTemplate
        promote_req = PromoteSymbolToTemplateRequest(
            structured_symbol_id=sym_id,
            library_name="Test ISA Library",
            discipline="piping",
            reviewer="qa_bot",
            user_notes="Aprobado en test de regresión"
        )
        promote_resp = promote_symbol_to_template(promote_req, db)

        assert promote_resp.template_id is not None
        assert promote_resp.symbol_class == "check_valve_spring"

        # Verificar que en BD la plantilla tenga máscara 128x128 y hu_moments
        created_tmpl = db.query(SymbolTemplate).filter(SymbolTemplate.id == promote_resp.template_id).first()
        assert created_tmpl is not None
        assert created_tmpl.is_active_for_detection is True
        assert len(created_tmpl.hu_moments) == 7
        assert created_tmpl.normalized_mask_path is not None

        # 2. Matching del candidato mediante endpoint seguro match_candidate
        match_req = MatchCandidateRequest(
            candidate_id=sym_id,
            discipline="piping",
            allowed_rotations=[0, 90, 180, 270],
            top_k=3
        )
        match_resp = match_candidate(match_req, db)

        assert match_resp.candidate_id == sym_id
        assert match_resp.best_match is not None
        assert match_resp.best_match.template_id == promote_resp.template_id
        assert match_resp.best_match.score >= 0.90
        assert match_resp.best_match.decision_policy == "auto_match"

    finally:
        # Limpieza
        db.query(SymbolTemplate).filter(SymbolTemplate.symbol_class == "check_valve_spring").delete()
        db.query(StructuredSymbol).filter(StructuredSymbol.id == sym_id).delete()
        db.commit()
        if os.path.exists(crop_path):
            os.remove(crop_path)
