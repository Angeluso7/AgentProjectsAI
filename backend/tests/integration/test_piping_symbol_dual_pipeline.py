import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import io
import uuid
import pytest
import fitz # PyMuPDF
from PIL import Image, ImageDraw
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.core import Organization, User, OrganizationMembership, Project
from app.db.models.intake_extractions import SourceExtraction, ExtractedItem, StructuredSymbol
from app.db.models.template_memory import SymbolLibrary, SymbolTemplate
from app.services.symbols.legend_table_extractor import LegendTableExtractor
from app.services.symbols.vector_extractor import VectorSymbolExtractor
from app.services.symbols.raster_extractor import RasterSymbolExtractor


def _create_synthetic_vector_pdf() -> bytes:
    """
    Crea un PDF vectorial en memoria simulando una tabla de leyenda de piping (ISA 5.1 / ASME B16.34).
    Contiene trazado de líneas vectoriales para válvulas de compuerta y retención, con franjas de texto.
    """
    doc = fitz.open()
    page = doc.new_page(width=595, height=842) # A4

    # 1. Trazar tabla (líneas vectoriales)
    # Encabezado
    page.draw_rect(fitz.Rect(50, 50, 545, 80), color=(0.2, 0.2, 0.2), fill=(0.9, 0.9, 0.9))
    page.insert_text(fitz.Point(60, 70), "LEYENDA DE SIMBOLOGÍA DE PIPING E INSTRUMENTACIÓN - ISA 5.1", fontsize=11)

    # Fila 1: Válvula de Compuerta
    # Dibujar polígonos de válvula de compuerta (dos triángulos opuestos de ~8x6 mm => ~23x17 pt)
    # Triángulo izquierdo: (70, 100) -> (70, 120) -> (85, 110)
    p1 = fitz.Point(70, 100)
    p2 = fitz.Point(70, 120)
    p3 = fitz.Point(85, 110)
    page.draw_polyline([p1, p2, p3, p1], color=(0, 0, 0), fill=(0.3, 0.3, 0.3), width=1.2)

    # Triángulo derecho: (100, 100) -> (100, 120) -> (85, 110)
    p4 = fitz.Point(100, 100)
    p5 = fitz.Point(100, 120)
    page.draw_polyline([p4, p5, p3, p4], color=(0, 0, 0), fill=(0.3, 0.3, 0.3), width=1.2)

    # Vástago y volante: línea vertical + barra
    page.draw_line(fitz.Point(85, 110), fitz.Point(85, 95), color=(0, 0, 0), width=1.2)
    page.draw_line(fitz.Point(80, 95), fitz.Point(90, 95), color=(0, 0, 0), width=1.5)

    # Texto asociado en franja de fila
    page.insert_text(fitz.Point(120, 112), "VÁLVULA DE COMPUERTA MANUAL ASME B16.34 - CLASE 150 RF", fontsize=10)

    # Fila 2: Válvula Check / Retención
    # Triángulos opuestos + círculo
    c1 = fitz.Point(70, 150)
    c2 = fitz.Point(70, 170)
    c3 = fitz.Point(85, 160)
    page.draw_polyline([c1, c2, c3, c1], color=(0, 0, 0), fill=(0.4, 0.4, 0.4), width=1.2)

    c4 = fitz.Point(100, 150)
    c5 = fitz.Point(100, 170)
    page.draw_polyline([c4, c5, c3, c4], color=(0, 0, 0), fill=(0.4, 0.4, 0.4), width=1.2)

    page.insert_text(fitz.Point(120, 162), "VÁLVULA DE RETENCIÓN / CHECK TIPO COLUMPIO ASME B16.34", fontsize=10)

    # Fila 3: Válvula de Globo
    g1 = fitz.Point(70, 200)
    g2 = fitz.Point(70, 220)
    g3 = fitz.Point(85, 210)
    page.draw_polyline([g1, g2, g3, g1], color=(0, 0, 0), fill=(0.2, 0.2, 0.2), width=1.2)
    g4 = fitz.Point(100, 200)
    g5 = fitz.Point(100, 220)
    page.draw_polyline([g4, g5, g3, g4], color=(0, 0, 0), fill=(0.2, 0.2, 0.2), width=1.2)
    page.draw_circle(fitz.Point(85, 210), 3, color=(0, 0, 0), fill=(0, 0, 0))
    page.insert_text(fitz.Point(120, 212), "VÁLVULA DE GLOBO PARA CONTROL DE FLUJO", fontsize=10)

    # Líneas separadoras de filas
    page.draw_line(fitz.Point(50, 85), fitz.Point(545, 85), color=(0.7, 0.7, 0.7), width=0.8)
    page.draw_line(fitz.Point(50, 135), fitz.Point(545, 135), color=(0.7, 0.7, 0.7), width=0.8)
    page.draw_line(fitz.Point(50, 185), fitz.Point(545, 185), color=(0.7, 0.7, 0.7), width=0.8)
    page.draw_line(fitz.Point(50, 235), fitz.Point(545, 235), color=(0.7, 0.7, 0.7), width=0.8)

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def _create_synthetic_raster_pdf() -> bytes:
    """
    Crea un PDF rasterizado (simulación de escaneado a 300 DPI) sin trazos vectoriales,
    con símbolos de piping dibujados a escala física técnica estándar (~8x6 mm).
    """
    # 2479 x 3508 es el estándar para A4 a 300 DPI (1 mm = 11.81 px)
    img = Image.new("RGB", (2479, 3508), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Cuadrícula / bordes de tabla
    draw.rectangle([200, 200, 2200, 2000], outline=(180, 180, 180), width=3)
    draw.line([200, 450, 2200, 450], fill=(180, 180, 180), width=3)
    draw.line([200, 850, 2200, 850], fill=(180, 180, 180), width=3)
    draw.line([200, 1250, 2200, 1250], fill=(180, 180, 180), width=3)

    # Símbolo 1: Válvula de compuerta en fila 1 (~100 px ancho x 70 px alto => ~8.5 x 5.9 mm)
    # Triángulo izquierdo: (320, 580) -> (320, 680) -> (380, 630)
    draw.polygon([(320, 580), (320, 680), (380, 630)], outline=(20, 20, 20), width=5)
    # Triángulo derecho: (440, 580) -> (440, 680) -> (380, 630)
    draw.polygon([(440, 580), (440, 680), (380, 630)], outline=(20, 20, 20), width=5)
    # Vástago y volante
    draw.line([(380, 630), (380, 540)], fill=(20, 20, 20), width=4)
    draw.line([(360, 540), (400, 540)], fill=(20, 20, 20), width=5)

    # Símbolo 2: Válvula check en fila 2
    draw.polygon([(320, 980), (320, 1080), (380, 1030)], outline=(20, 20, 20), width=5)
    draw.polygon([(440, 980), (440, 1080), (380, 1030)], outline=(20, 20, 20), width=5)
    draw.ellipse([(370, 1020), (390, 1040)], outline=(20, 20, 20), width=4)

    img_buf = io.BytesIO()
    img.save(img_buf, format="PNG")
    img_bytes = img_buf.getvalue()

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_image(page.rect, stream=img_bytes)

    # Texto en las franjas de fila (coordenadas pt)
    page.insert_text(fitz.Point(130, 150), "VÁLVULA DE COMPUERTA MANUAL ASME B16.34 FLANGED", fontsize=10)
    page.insert_text(fitz.Point(130, 250), "VÁLVULA DE RETENCIÓN CHECK ASME B16.34", fontsize=10)

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes



def test_vector_legend_extraction_and_persistence(db_session: Session):
    """
    Condición 1, 2 y 5:
    Valida la extracción vectorial vía PyMuPDF get_drawings(), agrupación de paths,
    cálculo de bbox agrupada, contexto estructural inside_table, asociación row_band,
    y persistencia real de todos los nuevos campos de la migración 0019 en PostgreSQL / DB.
    """
    # 1. Crear contexto de extracción
    ext_id = str(uuid.uuid4())
    org = Organization(id=str(uuid.uuid4()), name="Piping Unit", slug=f"piping-{uuid.uuid4().hex[:6]}")
    db_session.add(org)
    db_session.flush()

    extraction = SourceExtraction(
        id=ext_id,
        organization_id=org.id,
        title="Norma ISA 5.1 - Leyenda de Piping",
        discipline="piping",
        document_type="norma",
        extraction_mode="ai_document",
        status="completed",
        total_items=0
    )
    db_session.add(extraction)
    db_session.commit()

    # 2. Generar PDF vectorial y extraer
    pdf_bytes = _create_synthetic_vector_pdf()
    extractor = LegendTableExtractor(db_session)

    results = extractor.extract_from_pdf_page(
        pdf_bytes=pdf_bytes,
        page_number=1,
        extraction_id=ext_id,
        discipline="piping",
        preferred_mode="auto"
    )

    # 3. Verificaciones de candidatos detectados
    assert len(results) >= 1, "Debe detectar al menos un candidato de válvula vectorial."
    first = results[0]

    # Verificar metadatos obligatorios de Fase 1
    assert first.source_render_mode == "vector", f"Modo esperado 'vector', obtenido '{first.source_render_mode}'"
    assert first.layout_context in ["inside_table", "semi_structured_legend"]
    assert first.context_association_mode in ["row_band", "lateral_band"]
    assert first.canonical_symbol_family == "valves"
    assert "width_mm" in first.estimated_physical_size_mm
    assert "height_mm" in first.estimated_physical_size_mm
    assert first.confidence_score > 0.50

    # 4. Verificar persistencia real en la Base de Datos (ExtractedItem + StructuredSymbol)
    persisted_items = db_session.query(ExtractedItem).filter(ExtractedItem.extraction_id == ext_id).all()
    assert len(persisted_items) == len(results)

    persisted_syms = db_session.query(StructuredSymbol).join(
        ExtractedItem, StructuredSymbol.extracted_item_id == ExtractedItem.id
    ).filter(ExtractedItem.extraction_id == ext_id).all()
    assert len(persisted_syms) == len(results)

    sym = persisted_syms[0]
    assert sym.source_render_mode == "vector"
    assert sym.layout_context in ["inside_table", "semi_structured_legend"]
    assert sym.context_association_mode in ["row_band", "lateral_band"]
    assert sym.canonical_symbol_family == "valves"
    assert sym.reused_for_matching_count == 0
    assert sym.false_positive_count == 0
    assert sym.estimated_physical_size_mm is not None
    assert sym.human_validation_notes is not None


def test_raster_legend_extraction_and_persistence(db_session: Session):
    """
    Condición 3 y 5:
    Valida el pipeline raster con componentes conexos y morfología para documentos escaneados.
    Verifica source_render_mode = 'raster' y persistencia en DB.
    """
    ext_id = str(uuid.uuid4())
    org = Organization(id=str(uuid.uuid4()), name="Refinery Org", slug=f"refinery-{uuid.uuid4().hex[:6]}")
    db_session.add(org)
    db_session.flush()

    extraction = SourceExtraction(
        id=ext_id,
        organization_id=org.id,
        title="Plano Escaneado P&ID Isométrico",
        discipline="piping",
        document_type="plano",
        extraction_mode="ai_document",
        status="completed",
        total_items=0
    )
    db_session.add(extraction)
    db_session.commit()

    pdf_bytes = _create_synthetic_raster_pdf()
    extractor = LegendTableExtractor(db_session)

    # Forzar raster_only para validar el motor OpenCV
    results = extractor.extract_from_pdf_page(
        pdf_bytes=pdf_bytes,
        page_number=1,
        extraction_id=ext_id,
        discipline="piping",
        preferred_mode="raster_only"
    )

    assert len(results) >= 1, "Debe detectar candidatos morfológicos en el documento raster."
    cand = results[0]
    assert cand.source_render_mode == "raster"
    assert "width_mm" in cand.estimated_physical_size_mm
    assert cand.estimated_physical_size_mm["width_mm"] > 0

    # Verificar persistencia en DB
    db_sym = db_session.query(StructuredSymbol).filter(StructuredSymbol.id == cand.id).first()
    assert db_sym is not None
    assert db_sym.source_render_mode == "raster"


def test_promote_symbol_to_template_and_matching_prep(client: TestClient, db_session: Session):
    """
    Condición 4:
    Valida la promoción de un candidato estructurado a SymbolTemplate reutilizable en BD
    (preparando la base para futuro matching en fases posteriores sin afirmar detección aún).
    """
    # 1. Crear un símbolo estructurado en DB
    ext_id = str(uuid.uuid4())
    org = Organization(id=str(uuid.uuid4()), name="EPC Org", slug=f"epc-{uuid.uuid4().hex[:6]}")
    db_session.add(org)
    db_session.flush()

    item = ExtractedItem(
        id=str(uuid.uuid4()),
        extraction_id=ext_id,
        item_type="symbol",
        title="Válvula de Retención (Check)",
        review_status="to_confirm",
        discipline="piping"
    )
    db_session.add(item)
    db_session.flush()

    sym = StructuredSymbol(
        id=str(uuid.uuid4()),
        extracted_item_id=item.id,
        symbol_name="Válvula de Retención (Check) Tipo Columpio",
        canonical_symbol_family="valves",
        source_render_mode="vector",
        layout_context="inside_table",
        context_association_mode="row_band",
        standard_reference="Norma ASME B16.34",
        discipline="piping",
        estimated_physical_size_mm={"width_mm": 8.5, "height_mm": 6.2},
        reused_for_matching_count=0
    )
    db_session.add(sym)
    db_session.commit()

    # 2. Llamar al endpoint de promoción
    payload = {
        "structured_symbol_id": sym.id,
        "library_name": "Catálogo Maestro Piping ISA-5.1",
        "discipline": "piping",
        "user_notes": "Aprobado por Ingeniero de Procesos para matching"
    }

    response = client.post("/api/v1/symbols/promote-to-template", json=payload)
    assert response.status_code == 200, f"Error: {response.text}"
    data = response.json()

    assert data["symbol_class"] == "valves"
    assert data["display_name"] == sym.symbol_name
    assert data["reused_for_matching_count"] == 1

    # 3. Verificar que se creó el registro en symbol_templates y se actualizó StructuredSymbol
    db_session.refresh(sym)
    assert sym.reused_for_matching_count == 1
    assert "Aprobado por Ingeniero de Procesos" in sym.human_validation_notes

    db_template = db_session.query(SymbolTemplate).filter(SymbolTemplate.id == data["template_id"]).first()
    assert db_template is not None
    assert db_template.symbol_class == "valves"
    assert db_template.feature_descriptors["source_render_mode"] == "vector"

    # Verificar que el item asociado cambió de estado a accepted
    db_session.refresh(item)
    assert item.review_status == "accepted"



def test_list_structured_symbols_endpoint(client: TestClient, db_session: Session):
    """
    Valida el endpoint GET /api/v1/symbols/structured con filtros de familia y modo de renderizado.
    """
    # Consultar endpoint
    resp = client.get("/api/v1/symbols/structured?family=valves&limit=10")
    assert resp.status_code == 200
    items = resp.json()
    assert isinstance(items, list)
    for it in items:
        assert it["canonical_symbol_family"] == "valves"
        assert "source_render_mode" in it
        assert "layout_context" in it
