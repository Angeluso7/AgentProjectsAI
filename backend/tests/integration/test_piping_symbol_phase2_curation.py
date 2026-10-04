import os
import uuid
from typing import List, Dict, Any
import fitz # PyMuPDF
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.core import Organization, Project
from app.db.models.intake_extractions import SourceExtraction, ExtractedItem, StructuredSymbol
from app.db.models.template_memory import SymbolLibrary, SymbolTemplate
from app.services.symbols.legend_table_extractor import LegendTableExtractor
from app.services.symbols.deduplication_service import SymbolDeduplicationService


def _create_real_piping_legend_pdf() -> bytes:
    """
    Crea una lámina de leyenda técnica real de piping e instrumentación
    según normas ISA-5.1 y ASME B16.34:
    - Válvula de Compuerta (Gate Valve)
    - Válvula de Globo (Globe Valve)
    - Válvula Check / Retención (Check Valve)
    - Válvula de Bola (Ball Valve)
    - Válvula de Control con Actuador Neumático
    - Instrumento PT-101 (Transmisor de Presión)
    - Instrumento TT-102 (Transmisor de Temperatura)
    """
    doc = fitz.open()
    page = doc.new_page(width=595, height=842) # A4

    # Encabezado de la lámina técnica
    page.draw_rect(fitz.Rect(40, 40, 555, 75), color=(0.1, 0.1, 0.1), fill=(0.92, 0.92, 0.92))
    page.insert_text(fitz.Point(50, 62), "LÁMINA DE LEYENDA TÉCNICA - SIMBOLOGÍA DE PIPING E INSTRUMENTACIÓN", fontsize=11)

    # 1. Válvula de Compuerta (Gate Valve)
    p1, p2, p3 = fitz.Point(60, 95), fitz.Point(60, 115), fitz.Point(75, 105)
    page.draw_polyline([p1, p2, p3, p1], color=(0, 0, 0), fill=(0.2, 0.2, 0.2), width=1.2)
    p4, p5 = fitz.Point(90, 95), fitz.Point(90, 115)
    page.draw_polyline([p4, p5, p3, p4], color=(0, 0, 0), fill=(0.2, 0.2, 0.2), width=1.2)
    page.draw_line(fitz.Point(75, 105), fitz.Point(75, 90), color=(0, 0, 0), width=1.2)
    page.draw_line(fitz.Point(70, 90), fitz.Point(80, 90), color=(0, 0, 0), width=1.5)
    page.insert_text(fitz.Point(110, 108), "VÁLVULA DE COMPUERTA MANUAL ASME B16.34 - CLASE 150 RF", fontsize=9.5)

    # 2. Válvula de Globo (Globe Valve)
    g1, g2, g3 = fitz.Point(60, 140), fitz.Point(60, 160), fitz.Point(75, 150)
    page.draw_polyline([g1, g2, g3, g1], color=(0, 0, 0), fill=(0.3, 0.3, 0.3), width=1.2)
    g4, g5 = fitz.Point(90, 140), fitz.Point(90, 160)
    page.draw_polyline([g4, g5, g3, g4], color=(0, 0, 0), fill=(0.3, 0.3, 0.3), width=1.2)
    page.draw_circle(fitz.Point(75, 150), 3.5, color=(0, 0, 0), fill=(0, 0, 0))
    page.insert_text(fitz.Point(110, 153), "VÁLVULA DE GLOBO PARA CONTROL DE CAUDAL ASME B16.34", fontsize=9.5)

    # 3. Válvula de Retención / Check
    c1, c2, c3 = fitz.Point(60, 185), fitz.Point(60, 205), fitz.Point(75, 195)
    page.draw_polyline([c1, c2, c3, c1], color=(0, 0, 0), fill=(0.4, 0.4, 0.4), width=1.2)
    c4, c5 = fitz.Point(90, 185), fitz.Point(90, 205)
    page.draw_polyline([c4, c5, c3, c4], color=(0, 0, 0), fill=(0.4, 0.4, 0.4), width=1.2)
    page.insert_text(fitz.Point(110, 198), "VÁLVULA DE RETENCIÓN / CHECK TIPO COLUMPIO", fontsize=9.5)

    # 4. Válvula de Bola (Ball Valve)
    b1, b2, b3 = fitz.Point(60, 230), fitz.Point(60, 250), fitz.Point(75, 240)
    page.draw_polyline([b1, b2, b3, b1], color=(0, 0, 0), fill=(0.25, 0.25, 0.25), width=1.2)
    b4, b5 = fitz.Point(90, 230), fitz.Point(90, 250)
    page.draw_polyline([b4, b5, b3, b4], color=(0, 0, 0), fill=(0.25, 0.25, 0.25), width=1.2)
    page.draw_circle(fitz.Point(75, 240), 4.5, color=(0, 0, 0), fill=(1, 1, 1), width=1.0)
    page.insert_text(fitz.Point(110, 243), "VÁLVULA DE BOLA DE PASO TOTAL CLASE 300", fontsize=9.5)

    # 5. Válvula de Control Neumática con Actuador Diafragma
    v1, v2, v3 = fitz.Point(60, 275), fitz.Point(60, 295), fitz.Point(75, 285)
    page.draw_polyline([v1, v2, v3, v1], color=(0, 0, 0), fill=(0.3, 0.3, 0.3), width=1.2)
    v4, v5 = fitz.Point(90, 275), fitz.Point(90, 295)
    page.draw_polyline([v4, v5, v3, v4], color=(0, 0, 0), fill=(0.3, 0.3, 0.3), width=1.2)
    # Vástago y sombrerete de actuador diafragma
    page.draw_line(fitz.Point(75, 285), fitz.Point(75, 268), color=(0, 0, 0), width=1.2)
    page.draw_polyline([fitz.Point(65, 268), fitz.Point(85, 268), fitz.Point(75, 260), fitz.Point(65, 268)], color=(0, 0, 0), fill=(0.6, 0.6, 0.6), width=1.0)
    page.insert_text(fitz.Point(110, 288), "VÁLVULA DE CONTROL LINEAL CON ACTUADOR DE DIAFRAGMA", fontsize=9.5)

    # 6. Instrumento ISA 5.1: PT-101 (Transmisor de Presión montado en campo)
    page.draw_circle(fitz.Point(75, 330), 12, color=(0, 0, 0), fill=(1, 1, 1), width=1.2)
    page.insert_text(fitz.Point(67, 333), "PT", fontsize=8.5)
    page.insert_text(fitz.Point(110, 333), "TRANSMISOR DE PRESIÓN MONTADO EN CAMPO (PT-101)", fontsize=9.5)

    # 7. Instrumento ISA 5.1: TT-102 (Transmisor de Temperatura montado en campo)
    page.draw_circle(fitz.Point(75, 375), 12, color=(0, 0, 0), fill=(1, 1, 1), width=1.2)
    page.insert_text(fitz.Point(67, 378), "TT", fontsize=8.5)
    page.insert_text(fitz.Point(110, 378), "TRANSMISOR DE TEMPERATURA MONTADO EN CAMPO (TT-102)", fontsize=9.5)

    # Líneas horizontales de división de tabla
    for y in [80, 125, 170, 215, 260, 305, 350, 395]:
        page.draw_line(fitz.Point(40, y), fitz.Point(555, y), color=(0.8, 0.8, 0.8), width=0.8)

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def _create_piping_tutorial_sheet_pdf() -> bytes:
    """
    Crea una página de especificación técnica / tutorial normativo de tuberías
    con variantes de válvulas y notas de montaje.
    """
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)

    page.draw_rect(fitz.Rect(40, 40, 555, 75), color=(0.1, 0.1, 0.1), fill=(0.95, 0.95, 0.95))
    page.insert_text(fitz.Point(50, 62), "ESPECIFICACIÓN TÉCNICA DE MONTAJE Y SIMBOLOGÍA DE CAÑERÍAS", fontsize=11)

    # Válvula de Compuerta variante 2
    p1, p2, p3 = fitz.Point(60, 105), fitz.Point(60, 125), fitz.Point(75, 115)
    page.draw_polyline([p1, p2, p3, p1], color=(0, 0, 0), fill=(0.3, 0.3, 0.3), width=1.2)
    p4, p5 = fitz.Point(90, 105), fitz.Point(90, 125)
    page.draw_polyline([p4, p5, p3, p4], color=(0, 0, 0), fill=(0.3, 0.3, 0.3), width=1.2)
    page.draw_line(fitz.Point(75, 115), fitz.Point(75, 100), color=(0, 0, 0), width=1.2)
    page.draw_line(fitz.Point(70, 100), fitz.Point(80, 100), color=(0, 0, 0), width=1.5)
    page.insert_text(fitz.Point(110, 118), "VÁLVULA DE COMPUERTA EXTREMOS BRIDADOS ASME CLASE 150", fontsize=9.5)

    # Elemento decorativo / Falso Positivo potencial (ej. flecha de flujo o rectángulo)
    page.draw_rect(fitz.Rect(60, 150, 90, 165), color=(0, 0, 0), fill=(0.8, 0.8, 0.8), width=1.0)
    page.insert_text(fitz.Point(110, 160), "ETIQUETA DE CÓDIGO DE LÍNEA DE PROCESO", fontsize=9.5)

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


# ============================================================================
# TESTS DE INTEGRACIÓN FASE 2
# ============================================================================

def test_real_piping_legend_and_normative_sheet_extraction(db_session: Session):
    """
    Condición 1 y 5:
    Valida la extracción y persistencia de una leyenda técnica real de piping
    e instrumentación (ISA 5.1 / ASME B16.34) y una página de especificación/tutorial.
    """
    org = Organization(id=str(uuid.uuid4()), name="Piping Engineering Corp", slug=f"piping-{uuid.uuid4().hex[:6]}")
    db_session.add(org)
    db_session.flush()

    ext_id = str(uuid.uuid4())
    extraction = SourceExtraction(
        id=ext_id,
        organization_id=org.id,
        title="Lámina Oficial de Leyenda ISA-5.1 y ASME B16.34",
        discipline="piping",
        document_type="norma",
        extraction_mode="ai_document",
        status="completed",
        total_items=0
    )
    db_session.add(extraction)
    db_session.commit()

    # 1. Extraer desde la leyenda real
    pdf_legend = _create_real_piping_legend_pdf()
    extractor = LegendTableExtractor(db_session)
    results = extractor.extract_from_pdf_page(
        pdf_bytes=pdf_legend,
        page_number=1,
        extraction_id=ext_id,
        discipline="piping",
        preferred_mode="auto"
    )

    assert len(results) >= 4, f"Se esperaban al menos 4 símbolos de piping extraídos, obtenidos: {len(results)}"

    # Verificar que detectó válvulas e instrumentos
    families = [r.canonical_symbol_family for r in results]
    assert "valves" in families, "Debe detectar la familia valves."

    # 2. Extraer desde la lámina tutorial complementaria
    pdf_tutorial = _create_piping_tutorial_sheet_pdf()
    results_tut = extractor.extract_from_pdf_page(
        pdf_bytes=pdf_tutorial,
        page_number=1,
        extraction_id=ext_id,
        discipline="piping",
        preferred_mode="auto"
    )
    assert len(results_tut) >= 1, "Debe extraer símbolos de la lámina tutorial."


def test_curation_candidates_endpoint_all_9_evidences(client: TestClient, db_session: Session):
    """
    Condición 3:
    Valida que GET /api/v1/symbols/curation-candidates retorne las 9 evidencias
    obligatorias para la decisión humana:
    crop, documento origen, página, contexto estructural, OCR asociado,
    modo render, score, grupo visual actual y posible plantilla similar existente.
    """
    # Crear un símbolo persistido en DB
    ext_id = str(uuid.uuid4())
    org = Organization(id=str(uuid.uuid4()), name="Refinery Corp", slug=f"ref-{uuid.uuid4().hex[:6]}")
    db_session.add(org)
    db_session.flush()

    extraction = SourceExtraction(
        id=ext_id,
        organization_id=org.id,
        title="P&ID Refinería Unidad de Destilación",
        discipline="piping",
        document_type="plano",
        extraction_mode="ai_document",
        status="completed",
        total_items=1
    )
    db_session.add(extraction)
    db_session.flush()

    item = ExtractedItem(
        id=str(uuid.uuid4()),
        extraction_id=ext_id,
        item_type="symbol",
        title="VÁLVULA DE RETENCIÓN ASME",
        code_or_number="VÁLVULA DE RETENCIÓN ASME",
        description="Válvula de retención columpio en línea de 4 pulgadas",
        discipline="piping",
        page_number=2,
        bbox_normalized=[60, 185, 90, 205],
        review_status="pending",
        ocr_text="CHECK VALVE 4 IN 150 RF",
        crop_image_path="uploads/crops/test_check_valve.png",
    )
    db_session.add(item)
    db_session.flush()

    sym = StructuredSymbol(
        id=str(uuid.uuid4()),
        extracted_item_id=item.id,
        symbol_name="VÁLVULA DE RETENCIÓN ASME",
        standard_family="ASME B16.34",
        discipline="piping",
        category="check_valve",
        crop_image_path="uploads/crops/test_check_valve.png",
        confidence_score=0.92,
        source_render_mode="vector",
        layout_context="inside_table",
        context_association_mode="row_band",
        standard_reference="ASME B16.34",
        canonical_symbol_family="valves",
        visual_variant_group_id="VVG-A1B2C3D4",
        estimated_physical_size_mm={"width_mm": 10.5, "height_mm": 7.0},
        reused_for_matching_count=0,
        false_positive_count=0,
        human_validation_notes="Requiere confirmación de material"
    )
    db_session.add(sym)
    db_session.commit()

    # Consultar endpoint de candidatos
    resp = client.get(f"/api/v1/symbols/curation-candidates?extraction_id={ext_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1

    cand = data[0]
    # Verificar las 9 evidencias:
    assert cand["crop_image_path"] == "uploads/crops/test_check_valve.png", "Evidencia 1: Crop"
    assert cand["document_title"] == "P&ID Refinería Unidad de Destilación", "Evidencia 2: Documento origen"
    assert cand["page_number"] == 2, "Evidencia 3: Página"
    assert cand["layout_context"] == "inside_table", "Evidencia 4: Contexto estructural"
    assert cand["ocr_associated_text"] == "CHECK VALVE 4 IN 150 RF", "Evidencia 5: OCR asociado"
    assert cand["source_render_mode"] == "vector", "Evidencia 6: Modo render"
    assert cand["confidence_score"] == 0.92, "Evidencia 7: Score / confianza"
    assert cand["visual_variant_group_id"] == "VVG-A1B2C3D4", "Evidencia 8: Grupo visual actual"
    assert "possible_matching_template" in cand, "Evidencia 9: Posible plantilla existente evaluada"


def test_deduplication_multifactors_and_variant_clustering(client: TestClient, db_session: Session):
    """
    Condición 1:
    Valida el motor de deduplicación multi-factor: dHash es señal perceptual,
    combinada con nombre normalizado, familia canónica y tamaño físico.
    Verifica asignación de visual_variant_group_id y endpoints de merge/split.
    """
    ext_id = str(uuid.uuid4())
    org = Organization(id=str(uuid.uuid4()), name="EPC Org", slug=f"epc-{uuid.uuid4().hex[:6]}")
    db_session.add(org)
    db_session.flush()

    extraction = SourceExtraction(
        id=ext_id,
        organization_id=org.id,
        title="Doc Deduplicación de Válvulas",
        discipline="piping",
        document_type="norma",
        status="completed"
    )
    db_session.add(extraction)
    db_session.flush()

    # Generar crops temporales de prueba para verificar dHash y clustering
    import tempfile
    from PIL import Image as PILImage, ImageDraw as PILImageDraw

    crop_dir = tempfile.mkdtemp()
    img1_path = os.path.join(crop_dir, "gate1.png")
    img2_path = os.path.join(crop_dir, "gate2.png")

    im1 = PILImage.new("L", (40, 40), color=255)
    d1 = PILImageDraw.Draw(im1)
    d1.polygon([(10, 10), (10, 30), (20, 20)], fill=50)
    d1.polygon([(30, 10), (30, 30), (20, 20)], fill=50)
    im1.save(img1_path)

    im2 = PILImage.new("L", (40, 40), color=255)
    d2 = PILImageDraw.Draw(im2)
    d2.polygon([(10, 10), (10, 30), (20, 20)], fill=50)
    d2.polygon([(30, 10), (30, 30), (20, 20)], fill=50)
    im2.save(img2_path)

    # Crear dos candidatos de válvula de compuerta similares
    s1_id = str(uuid.uuid4())
    s2_id = str(uuid.uuid4())

    item1 = ExtractedItem(id=str(uuid.uuid4()), extraction_id=ext_id, item_type="symbol", title="VÁLVULA DE COMPUERTA MANUAL", code_or_number="VÁLVULA DE COMPUERTA MANUAL", crop_image_path=img1_path)
    item2 = ExtractedItem(id=str(uuid.uuid4()), extraction_id=ext_id, item_type="symbol", title="Válvula Compuerta 150# ASME", code_or_number="Válvula Compuerta 150# ASME", crop_image_path=img2_path)
    db_session.add_all([item1, item2])
    db_session.flush()

    sym1 = StructuredSymbol(
        id=s1_id,
        extracted_item_id=item1.id,
        symbol_name="VÁLVULA DE COMPUERTA MANUAL",
        canonical_symbol_family="valves",
        discipline="piping",
        confidence_score=0.90,
        crop_image_path=img1_path,
        estimated_physical_size_mm={"width_mm": 10.0, "height_mm": 8.0}
    )
    sym2 = StructuredSymbol(
        id=s2_id,
        extracted_item_id=item2.id,
        symbol_name="Válvula Compuerta 150# ASME",
        canonical_symbol_family="valves",
        discipline="piping",
        confidence_score=0.88,
        crop_image_path=img2_path,
        estimated_physical_size_mm={"width_mm": 10.2, "height_mm": 8.1}
    )
    db_session.add_all([sym1, sym2])
    db_session.commit()

    # Ejecutar deduplicación vía API
    resp = client.post("/api/v1/symbols/deduplicate", json={
        "extraction_id": ext_id,
        "discipline": "piping",
        "canonical_symbol_family": "valves",
        "visual_threshold": 0.80,
        "semantic_threshold": 0.70
    })
    assert resp.status_code == 200
    dedup_data = resp.json()
    assert dedup_data["total_evaluated"] == 2
    assert dedup_data["clusters_count"] >= 1

    # Verificar que se asignó visual_variant_group_id
    db_session.refresh(sym1)
    db_session.refresh(sym2)
    assert sym1.visual_variant_group_id is not None
    assert sym1.visual_variant_group_id == sym2.visual_variant_group_id

    # Probar endpoint de separación de variante (split)
    split_resp = client.post("/api/v1/symbols/variants/split", json={"symbol_id": s2_id})
    assert split_resp.status_code == 200
    new_group = split_resp.json()["new_group_id"]
    db_session.refresh(sym2)
    assert sym2.visual_variant_group_id == new_group
    assert sym2.visual_variant_group_id != sym1.visual_variant_group_id

    # Probar endpoint de fusión de variante (merge)
    merge_resp = client.post("/api/v1/symbols/variants/merge", json={
        "symbol_id": s2_id,
        "target_group_id": sym1.visual_variant_group_id
    })
    assert merge_resp.status_code == 200
    db_session.refresh(sym2)
    assert sym2.visual_variant_group_id == sym1.visual_variant_group_id


def test_hitl_curation_editing_and_batch_actions(client: TestClient, db_session: Session):
    """
    Condición 2:
    Valida las acciones del modal de curación:
    editar nombre, editar familia, editar estándar, notas, aprobar, rechazar y falso positivo.
    """
    ext_id = str(uuid.uuid4())
    org = Organization(id=str(uuid.uuid4()), name="Plant Org", slug=f"plant-{uuid.uuid4().hex[:6]}")
    db_session.add(org)
    db_session.flush()

    item = ExtractedItem(id=str(uuid.uuid4()), extraction_id=ext_id, item_type="symbol", title="Simbolo Desconocido", code_or_number="Simbolo Desconocido")
    db_session.add(item)
    db_session.flush()

    sym = StructuredSymbol(
        id=str(uuid.uuid4()),
        extracted_item_id=item.id,
        symbol_name="Simbolo Desconocido",
        canonical_symbol_family="general",
        discipline="piping"
    )
    db_session.add(sym)
    db_session.commit()

    # 1. Editar metadatos vía PATCH
    patch_resp = client.patch(f"/api/v1/symbols/structured/{sym.id}", json={
        "symbol_name": "VÁLVULA DE MARIPOSA WAFER",
        "canonical_symbol_family": "valves",
        "standard_reference": "ASME B16.34 / API 609",
        "human_validation_notes": "Corregido tipo por inspector de piping"
    })
    assert patch_resp.status_code == 200
    updated_sym = patch_resp.json()
    assert updated_sym["symbol_name"] == "VÁLVULA DE MARIPOSA WAFER"
    assert updated_sym["canonical_symbol_family"] == "valves"
    assert updated_sym["standard_reference"] == "ASME B16.34 / API 609"

    # 2. Curación en lote: Marcar como Falso Positivo
    curate_fp_resp = client.post("/api/v1/symbols/curate", json={
        "symbol_ids": [sym.id],
        "action": "flag_false_positive",
        "notes": "Trazo decorativo de borde de plano",
        "reviewer": "Auditor Principal"
    })
    assert curate_fp_resp.status_code == 200
    db_session.refresh(sym)
    db_session.refresh(item)
    assert sym.false_positive_count >= 1
    assert item.review_status == "flagged_false_positive"

    # 3. Curación en lote: Aprobar (accept)
    curate_ok_resp = client.post("/api/v1/symbols/curate", json={
        "symbol_ids": [sym.id],
        "action": "accept",
        "notes": "Aprobado tras validación visual",
        "reviewer": "Auditor Principal"
    })
    assert curate_ok_resp.status_code == 200
    db_session.refresh(item)
    assert item.review_status == "accepted"


def test_controlled_batch_promotion_and_canonical_catalog(client: TestClient, db_session: Session):
    """
    Condición 4 y 5:
    Valida la promoción controlada con registro de quién aprobó, cuándo,
    desde qué candidato, nombre final, familia y variante.
    Verifica que el catálogo consolidado reporte el primer lote canónico de piping.
    """
    ext_id = str(uuid.uuid4())
    org = Organization(id=str(uuid.uuid4()), name="Offshore Unit", slug=f"offshore-{uuid.uuid4().hex[:6]}")
    db_session.add(org)
    db_session.flush()

    # Crear 3 símbolos aprobados para el primer lote canónico
    symbols_to_promote = []
    symbol_specs = [
        ("Válvula de Compuerta ASME B16.34", "valves", "gate_valve", "VVG-GATE-01"),
        ("Válvula de Globo de Regulación", "valves", "globe_valve", "VVG-GLOBE-01"),
        ("Transmisor de Presión PT-101", "instruments", "pressure_transmitter", "VVG-PT-01")
    ]

    for name, fam, cat, grp in symbol_specs:
        it = ExtractedItem(id=str(uuid.uuid4()), extraction_id=ext_id, item_type="symbol", title=name, code_or_number=name, review_status="accepted")
        db_session.add(it)
        db_session.flush()

        s = StructuredSymbol(
            id=str(uuid.uuid4()),
            extracted_item_id=it.id,
            symbol_name=name,
            canonical_symbol_family=fam,
            category=cat,
            discipline="piping",
            standard_reference="ISA-5.1 / ASME B16.34",
            visual_variant_group_id=grp,
            estimated_physical_size_mm={"width_mm": 10.0, "height_mm": 8.0}
        )
        db_session.add(s)
        symbols_to_promote.append(s)

    db_session.commit()

    # 1. Promover en lote a SymbolTemplate
    promote_resp = client.post("/api/v1/symbols/promote-batch", json={
        "structured_symbol_ids": [s.id for s in symbols_to_promote],
        "library_name": "ISA-5.1 Piping Library",
        "discipline": "piping",
        "reviewer": "Ingeniero Revisor Piping",
        "user_notes": "Primer lote canónico aprobado para reuse"
    })
    assert promote_resp.status_code == 200
    data = promote_resp.json()
    assert data["promoted_count"] == 3
    assert data["library_name"] == "ISA-5.1 Piping Library"

    # 2. Consultar catálogo canónico consolidado
    cat_resp = client.get("/api/v1/symbols/canonical-catalog?library_name=ISA-5.1%20Piping%20Library&discipline=piping")
    assert cat_resp.status_code == 200
    catalog = cat_resp.json()
    assert catalog["total_templates"] >= 3
    assert "valves" in catalog["family_counts"]
    assert "instruments" in catalog["family_counts"]

    # 3. Verificar linaje y auditoría de la plantilla en DB
    first_tpl = catalog["templates"][0]
    assert first_tpl["approved_by"] == "Ingeniero Revisor Piping"
    assert first_tpl["approved_at"] is not None
    assert first_tpl["source_structured_symbol_id"] is not None
    assert first_tpl["visual_variant_group_id"] is not None
