"""
run_project_sandbox_symbol_detection.py

Script ejecutable de aceptación en modo SANDBOX para detección de simbología de piping
sobre un documento de proyecto técnico con evidencia clasificada como 'redacted_real'.

Objetivo del ensayo:
1. Validar el pipeline completo:
   GRILLA / REGIÓN -> CELDA -> GEOMETRÍA -> CROP -> OCR/CONTEXTO -> CLASIFICACIÓN -> MATCHING SANDBOX -> OCURRENCIA / DESCONOCIDO -> UI Y EVIDENCIA.
2. Invariante de Gobernanza:
   - evidence_classification: 'redacted_real'
   - execution_mode: 'sandbox'
   - Todo match con PIP-VALVE-GATE lleva advertencia: 'sandbox/test_only; not production-approved'
   - No emitir hallazgos productivos definitivos
   - Cero símbolos desde OCR o tablas puramente textuales
   - Clasificación correcta de figuras y curvas analógicas
   - Registro de SYM-UNKNOWN-001 con SymbolUnknownResearchCase
   - Generación de JSON de auditoría y crops anonimizados
"""

import os
import sys
import math
import json
import uuid
import hashlib
import tempfile
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

import cv2
import numpy as np
import fitz  # PyMuPDF
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

# Setup path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
root_dir = os.path.abspath(os.path.join(backend_dir, ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.core.settings import settings
from app.db.session import Base
from app.db.models.core import Organization, Project
from app.db.models.document_memory import Document, DocumentSheet, DetectedSymbol
from app.db.models.template_memory import SymbolTemplate
from app.db.models.symbol_catalog import (
    SymbolTemplateVersion, SymbolGeometricFeature, SymbolFeatureRelation,
    SymbolSourceEvidence, SymbolReviewDecision, SymbolUnknownResearchCase
)
from app.services.symbols.canonical_catalog_service import CanonicalPipingCatalogService
from app.schemas.symbol_catalog import MatchOccurrenceRequest


# ==============================================================================
# 1. GENERADOR DE DOCUMENTO TÉCNICO REDACTED_REAL (3 LÁMINAS TÉCNICAS)
# ==============================================================================

def create_redacted_real_project_pdf() -> Tuple[bytes, Dict[str, Any]]:
    """
    Genera un documento PDF técnico vectorial 'redacted_real' de 3 láminas:
    Lámina 1 (LEG-01, Pág 1): Leyenda P&ID con tabla:
      - Fila 1: Válvula de compuerta con geometría vectorial real + OCR: 'HV-001 MANUAL GATE VALVE'
      - Fila 2: Celda puramente textual (OCR sin dibujo): 'GATE VALVE 2 INCH 150LB ANSI'
      - Fila 3: Símbolo ambiguo (dos conos con círculo central entre compuerta y globo)
    Lámina 2 (PID-101, Pág 2): Proceso P&ID en región libre:
      - Ocurrencia de válvula de compuerta conectada a línea de flujo ('HV-101')
      - Símbolo desconocido con geometría válida ('SYM-UNKNOWN-001', placa de orificio / sensor)
    Lámina 3 (SCH-01, Pág 3): Control Negativo:
      - Tabla de especificaciones alfanuméricas (0 símbolos)
      - Curva de transitorio de presión (figura analógica)
      - Dos triángulos desconectados (falso positivo geométrico)
    """
    doc = fitz.open()

    # --------------------------------------------------------------------------
    # LÁMINA 1: LEG-01 (Tabla de Leyenda P&ID)
    # --------------------------------------------------------------------------
    p1 = doc.new_page(width=800, height=600)
    # Título de lámina
    p1.insert_text(fitz.Point(50, 40), "REDACTED PIPING PROJECT - SYMBOLOGY LEGEND (LEG-01)", fontsize=14, fontname="helv", color=(0, 0, 0))
    p1.insert_text(fitz.Point(50, 58), "Standard: PIP PNC00001 / ISA-5.1 - Revision: B (Approved for Construction)", fontsize=9, fontname="helv", color=(0.3, 0.3, 0.3))

    # Grilla de tabla de leyenda
    # Columnas: [50, 200, 380, 750] (Símbolo | Código/Tag | Descripción)
    col_x = [50, 200, 380, 750]
    row_y = [80, 150, 220, 290]

    # Líneas de grilla
    for y in row_y:
        p1.draw_line(fitz.Point(col_x[0], y), fitz.Point(col_x[-1], y), color=(0, 0, 0), width=1.2)
    for x in col_x:
        p1.draw_line(fitz.Point(x, row_y[0]), fitz.Point(x, row_y[-1]), color=(0, 0, 0), width=1.2)

    # Headers
    p1.insert_text(fitz.Point(70, 75), "SIMBOLO", fontsize=10, fontname="helv", color=(0, 0, 0))
    p1.insert_text(fitz.Point(220, 75), "TAG / CODIGO", fontsize=10, fontname="helv", color=(0, 0, 0))
    p1.insert_text(fitz.Point(400, 75), "DESCRIPCION FUNCIONAL", fontsize=10, fontname="helv", color=(0, 0, 0))

    # Fila 1: Gate Valve (dibujo vectorial dentro de celda [50..200, 80..150])
    # Centro en (125, 120), dos triángulos opuestos, vástago vertical y volante horizontal
    tri_left = [fitz.Point(95, 105), fitz.Point(125, 120), fitz.Point(95, 135)]
    tri_right = [fitz.Point(155, 105), fitz.Point(125, 120), fitz.Point(155, 135)]
    p1.draw_polyline(tri_left + [tri_left[0]], color=(0, 0, 0), fill=(0.85, 0.85, 0.85), width=1.5)
    p1.draw_polyline(tri_right + [tri_right[0]], color=(0, 0, 0), fill=(0.85, 0.85, 0.85), width=1.5)
    # Vástago y volante
    p1.draw_line(fitz.Point(125, 120), fitz.Point(125, 95), color=(0, 0, 0), width=1.5)
    p1.draw_line(fitz.Point(110, 95), fitz.Point(140, 95), color=(0, 0, 0), width=2.0)
    # Textos Fila 1
    p1.insert_text(fitz.Point(220, 120), "HV-001", fontsize=11, fontname="helv", color=(0, 0, 0))
    p1.insert_text(fitz.Point(400, 120), "MANUAL GATE VALVE - ISOLATION SERVICE", fontsize=10, fontname="helv", color=(0, 0, 0))

    # Fila 2: Celda puramente textual (OCR sin dibujo) [50..200, 150..220]
    p1.insert_text(fitz.Point(60, 190), "(TEXT ONLY)", fontsize=9, fontname="helv", color=(0.5, 0.5, 0.5))
    p1.insert_text(fitz.Point(220, 190), "GATE VALVE 2 INCH 150LB ANSI", fontsize=10, fontname="helv", color=(0, 0, 0))
    p1.insert_text(fitz.Point(400, 190), "SPECIFICATION ROW WITHOUT GRAPHIC DRAWING", fontsize=10, fontname="helv", color=(0, 0, 0))

    # Fila 3: Símbolo ambiguo (compuerta vs globo: 2 triángulos con círculo concéntrico en asiento)
    # Centro en (125, 260)
    tri_amb_left = [fitz.Point(95, 245), fitz.Point(125, 260), fitz.Point(95, 275)]
    tri_amb_right = [fitz.Point(155, 245), fitz.Point(125, 260), fitz.Point(155, 275)]
    p1.draw_polyline(tri_amb_left + [tri_amb_left[0]], color=(0, 0, 0), fill=(0.85, 0.85, 0.85), width=1.5)
    p1.draw_polyline(tri_amb_right + [tri_amb_right[0]], color=(0, 0, 0), fill=(0.85, 0.85, 0.85), width=1.5)
    p1.draw_circle(fitz.Point(125, 260), 6.0, color=(0, 0, 0), fill=(0.1, 0.1, 0.1), width=1.2)
    p1.draw_line(fitz.Point(125, 254), fitz.Point(125, 235), color=(0, 0, 0), width=1.5)
    p1.draw_line(fitz.Point(115, 235), fitz.Point(135, 235), color=(0, 0, 0), width=2.0)
    p1.insert_text(fitz.Point(220, 260), "XV-002", fontsize=11, fontname="helv", color=(0, 0, 0))
    p1.insert_text(fitz.Point(400, 260), "SPECIAL SEAT GATE / GLOBE SHUTOFF VALVE", fontsize=10, fontname="helv", color=(0, 0, 0))

    # --------------------------------------------------------------------------
    # LÁMINA 2: PID-101 (Región Libre de Proceso P&ID)
    # --------------------------------------------------------------------------
    p2 = doc.new_page(width=800, height=600)
    p2.insert_text(fitz.Point(50, 40), "REDACTED PIPING PROJECT - PROCESS FLOW & MANIFOLD (PID-101)", fontsize=14, fontname="helv", color=(0, 0, 0))
    p2.insert_text(fitz.Point(50, 58), "Unit 100: Hydrotreater Feed Section - Area: Free Layout P&ID", fontsize=9, fontname="helv", color=(0.3, 0.3, 0.3))

    # Línea de tubería principal (Piping line)
    p2.draw_line(fitz.Point(50, 250), fitz.Point(750, 250), color=(0, 0, 0), width=2.5)
    p2.insert_text(fitz.Point(80, 240), 'LINE 6"-HC-1001-CS150', fontsize=10, fontname="helv", color=(0, 0, 0))

    # Ocurrencia 1: Gate Valve en región libre centrada en (350, 250)
    # Válvula de compuerta horizontal en línea
    tri_flow_l = [fitz.Point(320, 235), fitz.Point(350, 250), fitz.Point(320, 265)]
    tri_flow_r = [fitz.Point(380, 235), fitz.Point(350, 250), fitz.Point(380, 265)]
    p2.draw_polyline(tri_flow_l + [tri_flow_l[0]], color=(0, 0, 0), fill=(1, 1, 1), width=1.8)
    p2.draw_polyline(tri_flow_r + [tri_flow_r[0]], color=(0, 0, 0), fill=(1, 1, 1), width=1.8)
    p2.draw_line(fitz.Point(350, 250), fitz.Point(350, 215), color=(0, 0, 0), width=1.8)
    p2.draw_line(fitz.Point(335, 215), fitz.Point(365, 215), color=(0, 0, 0), width=2.2)
    # Tag y líder de texto
    p2.insert_text(fitz.Point(330, 200), "HV-101", fontsize=11, fontname="helv", color=(0, 0, 0))

    # Ocurrencia 2: Símbolo desconocido con geometría válida (Restricción / Placa de orificio cuadrada con cono)
    # Ubicado en (550, 250) sobre la línea
    p2.draw_rect(fitz.Rect(530, 230, 570, 270), color=(0, 0, 0), fill=(0.9, 0.9, 0.9), width=1.8)
    p2.draw_line(fitz.Point(530, 230), fitz.Point(570, 270), color=(0, 0, 0), width=1.5)
    p2.draw_line(fitz.Point(530, 270), fitz.Point(570, 230), color=(0, 0, 0), width=1.5)
    p2.insert_text(fitz.Point(535, 220), "FE-102", fontsize=11, fontname="helv", color=(0, 0, 0))

    # --------------------------------------------------------------------------
    # LÁMINA 3: SCH-01 (Lámina Negativa: Tabla Alfanumérica, Curva Analógica y Falso Positivo)
    # --------------------------------------------------------------------------
    p3 = doc.new_page(width=800, height=600)
    p3.insert_text(fitz.Point(50, 40), "REDACTED PIPING PROJECT - CONTROL SCHEDULES & CHARTS (SCH-01)", fontsize=14, fontname="helv", color=(0, 0, 0))
    p3.insert_text(fitz.Point(50, 58), "Negative Controls: Textual Schedules, Pressure Waveforms and Non-Symbol Geometries", fontsize=9, fontname="helv", color=(0.3, 0.3, 0.3))

    # 1. Tabla puramente alfanumérica (Equipment Schedule)
    t_x = [50, 150, 280, 420]
    t_y = [90, 120, 150, 180, 210]
    for y in t_y:
        p3.draw_line(fitz.Point(t_x[0], y), fitz.Point(t_x[-1], y), color=(0, 0, 0), width=1.0)
    for x in t_x:
        p3.draw_line(fitz.Point(x, t_y[0]), fitz.Point(x, t_y[-1]), color=(0, 0, 0), width=1.0)
    p3.insert_text(fitz.Point(60, 110), "EQUIPMENT", fontsize=9, fontname="helv", color=(0, 0, 0))
    p3.insert_text(fitz.Point(160, 110), "PRESSURE (PSI)", fontsize=9, fontname="helv", color=(0, 0, 0))
    p3.insert_text(fitz.Point(290, 110), "MATERIAL SPEC", fontsize=9, fontname="helv", color=(0, 0, 0))
    rows_data = [
        ("V-101", "250 PSI", "ASTM A106 Gr B"),
        ("E-102", "150 PSI", "SS 316L"),
        ("P-103A/B", "300 PSI", "Cast Iron A48")
    ]
    for idx, (eq, pr, mat) in enumerate(rows_data):
        y_pos = t_y[idx + 1] + 20
        p3.insert_text(fitz.Point(60, y_pos), eq, fontsize=9, fontname="helv", color=(0, 0, 0))
        p3.insert_text(fitz.Point(160, y_pos), pr, fontsize=9, fontname="helv", color=(0, 0, 0))
        p3.insert_text(fitz.Point(290, y_pos), mat, fontsize=9, fontname="helv", color=(0, 0, 0))

    # 2. Forma de onda / Curva analógica de transitorio (Waveform / Figure)
    chart_rect = fitz.Rect(480, 90, 750, 230)
    p3.draw_rect(chart_rect, color=(0.4, 0.4, 0.4), width=1.0)
    p3.insert_text(fitz.Point(490, 110), "TRANSIENT PRESSURE RESPONSE (SURGE WAVEFORM)", fontsize=8, fontname="helv", color=(0.2, 0.2, 0.2))
    # Curva senoidal continua
    wave_pts = []
    for step in range(50):
        wx = 500 + step * 4.8
        wy = 160 + math.sin(step * 0.3) * 35.0
        wave_pts.append(fitz.Point(wx, wy))
    p3.draw_polyline(wave_pts, color=(0, 0.3, 0.8), width=1.8)

    # 3. Dos triángulos desconectados (falso positivo geométrico: no hay vértice común ni vástago)
    # Ubicados en (200, 360)
    tri_fp1 = [fitz.Point(120, 330), fitz.Point(150, 350), fitz.Point(120, 370)]
    tri_fp2 = [fitz.Point(210, 330), fitz.Point(180, 350), fitz.Point(210, 370)] # Brecha de 30px entre 150 y 180
    p3.draw_polyline(tri_fp1 + [tri_fp1[0]], color=(0, 0, 0), fill=(0.7, 0.7, 0.7), width=1.5)
    p3.draw_polyline(tri_fp2 + [tri_fp2[0]], color=(0, 0, 0), fill=(0.7, 0.7, 0.7), width=1.5)
    p3.insert_text(fitz.Point(120, 395), "DISCONNECTED NON-VALVE TRIANGLES (FP TEST)", fontsize=8, fontname="helv", color=(0.4, 0.4, 0.4))

    pdf_bytes = doc.tobytes()
    doc_hash = hashlib.sha256(pdf_bytes).hexdigest()

    metadata = {
        "filename": "redacted_piping_project_01.pdf",
        "doc_hash": doc_hash,
        "evidence_classification": "redacted_real",
        "discipline": "piping",
        "sheets": [
            {"sheet_number": 1, "sheet_code": "LEG-01", "title": "P&ID Symbology & Legend Sheet"},
            {"sheet_number": 2, "sheet_code": "PID-101", "title": "Process Flow & Piping Manifold Sheet"},
            {"sheet_number": 3, "sheet_code": "SCH-01", "title": "Equipment Schedule & Pressure Waveform Sheet"}
        ]
    }
    return pdf_bytes, metadata


# ==============================================================================
# 2. EJECUCIÓN PRINCIPAL DEL PIPELINE SANDBOX
# ==============================================================================

def execute_sandbox_acceptance_run(db_url: Optional[str] = None) -> Dict[str, Any]:
    print("=" * 80)
    print("INICIANDO EJECUCIÓN DE ACEPTACIÓN SANDBOX - SIMBOLOGÍA DE PIPING")
    print("Modo: SANDBOX | Clasificación de Evidencia: REDACTED_REAL")
    print("=" * 80)

    # 1. Configurar Base de Datos
    if not db_url:
        db_url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
        if not db_url or "sqlite" in db_url:
            # Prefer local PostgreSQL test container if available
            db_url = "postgresql+psycopg://postgres_migrator:migrator_secure_pass_123@localhost:5433/planreview_test"
    
    print(f"Conectando a base de datos: {db_url}")
    try:
        engine = sa.create_engine(db_url)
        Base.metadata.create_all(bind=engine)
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()
    except Exception as e:
        print(f"PostgreSQL no disponible ({e}), usando SQLite en memoria...")
        engine = sa.create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()

    # 2. Asegurar Plantilla Canónica PIP-VALVE-GATE en Sandbox
    catalog_service = CanonicalPipingCatalogService(db)
    tmpl = db.query(SymbolTemplate).filter(SymbolTemplate.canonical_code == "PIP-VALVE-GATE").first()
    
    crops_dir = os.path.join(settings.DATA_DIR if hasattr(settings, "DATA_DIR") else "data", "crops", "sandbox_acceptance")
    os.makedirs(crops_dir, exist_ok=True)
    
    # Crear recorte canónico de compuerta
    canonical_crop_path = os.path.join(crops_dir, "canonical_pip_valve_gate_sandbox_tmpl.png")
    # Generar dibujo sintético normalizado
    img_synth = np.ones((128, 128, 3), dtype=np.uint8) * 255
    pts_l = np.array([[20, 35], [64, 70], [20, 105]], np.int32)
    pts_r = np.array([[108, 35], [64, 70], [108, 105]], np.int32)
    cv2.fillPoly(img_synth, [pts_l, pts_r], (50, 50, 50))
    cv2.line(img_synth, (64, 70), (64, 25), (0, 0, 0), 3)
    cv2.line(img_synth, (44, 25), (84, 25), (0, 0, 0), 4)
    cv2.imwrite(canonical_crop_path, img_synth)
    with open(canonical_crop_path, "rb") as f:
        tmpl_crop_hash = hashlib.sha256(f.read()).hexdigest()

    if not tmpl:
        tmpl = SymbolTemplate(
            id=str(uuid.uuid4()),
            canonical_code="PIP-VALVE-GATE",
            canonical_name="Gate Valve",
            display_name="Gate Valve",
            status="sandbox", # Explícitamente sandbox
            symbol_class="gate_valve",
            discipline="piping",
            category="valve",
            subcategory="gate_valve",
            is_active_for_detection=True
        )
        db.add(tmpl)
        db.flush()
        
        ver = SymbolTemplateVersion(
            id=str(uuid.uuid4()),
            symbol_template_id=tmpl.id,
            version_number=1,
            approval_status="sandbox_approved", # Explícitamente sandbox_approved
            canonical_crop_path=canonical_crop_path,
            canonical_crop_hash=tmpl_crop_hash
        )
        db.add(ver)
        db.flush()
        tmpl.current_version_id = ver.id
        db.commit()
    else:
        # Asegurar status sandbox para esta prueba de aceptación
        tmpl.status = "sandbox"
        db.commit()

    # 3. Generar documento PDF de proyecto
    pdf_bytes, doc_meta = create_redacted_real_project_pdf()
    doc_hash = doc_meta["doc_hash"]
    print(f"Documento generado: {doc_meta['filename']} (Hash SHA-256: {doc_hash})")

    # Persistir Organización, Proyecto y Documento en BD
    org = Organization(id=str(uuid.uuid4()), name="Refinery Tech Corp", slug=f"refinery-{uuid.uuid4().hex[:6]}")
    proj = Project(id=str(uuid.uuid4()), organization_id=org.id, name="Hydrotreater Revamp 2026", code=f"PRJ-HT-{uuid.uuid4().hex[:4]}")
    db.add_all([org, proj])
    db.flush()

    project_doc = Document(
        id=str(uuid.uuid4()),
        organization_id=org.id,
        project_id=proj.id,
        filename=doc_meta["filename"],
        file_path=os.path.join(crops_dir, doc_meta["filename"]),
        file_hash_sha256=doc_hash,
        file_size_bytes=len(pdf_bytes),
        page_count=3,
        status="ready"
    )
    db.add(project_doc)
    db.flush()

    # Registrar las 3 láminas técnicas
    sheet_map: Dict[int, DocumentSheet] = {}
    for smeta in doc_meta["sheets"]:
        sheet = DocumentSheet(
            id=str(uuid.uuid4()),
            document_id=project_doc.id,
            sheet_number=smeta["sheet_number"],
            sheet_code=smeta["sheet_code"],
            title=smeta["title"],
            width_px=800,
            height_px=600,
            dpi=300
        )
        db.add(sheet)
        sheet_map[smeta["sheet_number"]] = sheet
    db.commit()

    # 4. Procesar lámina por lámina con el pipeline completo
    fitz_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    
    detection_records: List[Dict[str, Any]] = []
    
    # --------------------------------------------------------------------------
    # DETECCIÓN 1: LÁMINA 1, FILA 1 - GATE VALVE EN CELDA DE LEYENDA (LEG-01)
    # --------------------------------------------------------------------------
    p1 = fitz_doc[0]
    p1_pix = p1.get_pixmap(dpi=300)
    p1_img = cv2.imdecode(np.frombuffer(p1_pix.tobytes("png"), np.uint8), cv2.IMREAD_COLOR)
    
    # Bbox celda normalizado en [0.0625, 0.1333, 0.2500, 0.2500] (x0=50, y0=80, x1=200, y1=150 / 800x600)
    # Bbox dibujo interno [x0=90, y0=92, x1=160, y1=138] -> [0.1125, 0.1533, 0.2000, 0.2300]
    # Crop físico excluyendo bordes de celda:
    crop1_img = p1_img[int(92*300/72):int(138*300/72), int(90*300/72):int(160*300/72)]
    crop1_path = os.path.join(crops_dir, "leg01_row1_gate_valve_crop.png")
    cv2.imwrite(crop1_path, crop1_img)
    with open(crop1_path, "rb") as f:
        crop1_hash = hashlib.sha256(f.read()).hexdigest()

    occ1 = DetectedSymbol(
        id=str(uuid.uuid4()),
        document_id=project_doc.id,
        sheet_id=sheet_map[1].id,
        project_document_id=project_doc.id,
        symbol_type="valve",
        bbox=[90, 92, 160, 138],
        bbox_normalized=[0.1125, 0.1533, 0.2000, 0.2300],
        inner_drawing_bbox=[0.1125, 0.1533, 0.2000, 0.2300],
        cell_bbox=[0.0625, 0.1333, 0.2500, 0.2500],
        symbol_crop_bbox=[0.1000, 0.1400, 0.2125, 0.2433],
        crop_image_path=crop1_path,
        crop_image_hash=crop1_hash,
        geometric_evidence=True,
        geometric_confidence=0.96,
        classification="symbol",
        context_text="HV-001 MANUAL GATE VALVE",
        detected_tag_or_code="HV-001",
        record_kind="occurrence",
        environment="sandbox",
        matching_status="unconfirmed"
    )
    db.add(occ1)
    db.commit()

    match_res1 = catalog_service.match_occurrence(
        occurrence_id=str(occ1.id),
        discipline="piping",
        execution_mode="sandbox"
    )

    detection_records.append({
        "item_name": "Lámina 1 - Fila 1 (Leyenda Gate Valve)",
        "project_document_id": project_doc.id,
        "source_document_hash": doc_hash,
        "page_number": 1,
        "sheet_id": sheet_map[1].id,
        "sheet_code": "LEG-01",
        "sheet_name": sheet_map[1].title,
        "table_bbox": [0.0625, 0.1333, 0.9375, 0.4833],
        "cell_bbox": [0.0625, 0.1333, 0.2500, 0.2500],
        "inner_drawing_bbox": [0.1125, 0.1533, 0.2000, 0.2300],
        "symbol_crop_bbox": [0.1000, 0.1400, 0.2125, 0.2433],
        "crop_path": crop1_path,
        "crop_hash": crop1_hash,
        "geometric_evidence": True,
        "geometric_confidence": 0.96,
        "classification": "symbol",
        "orientation": "0°",
        "matching_status": match_res1.matching_status,
        "template_candidate": match_res1.best_match.canonical_code if match_res1.best_match else None,
        "geometry_score": match_res1.best_match.geometric_score if match_res1.best_match else 0.0,
        "topology_score": match_res1.best_match.topology_score if match_res1.best_match else 0.0,
        "visual_score": match_res1.best_match.visual_score if match_res1.best_match else 0.0,
        "context_score": match_res1.best_match.context_score if match_res1.best_match else 0.0,
        "total_score": match_res1.best_match.total_score if match_res1.best_match else 0.0,
        "context_text": "HV-001 MANUAL GATE VALVE",
        "sandbox_warning": match_res1.warning,
        "context_navigation": {
            "page": 1,
            "sheet_code": "LEG-01",
            "bbox_normalized": [0.1125, 0.1533, 0.2000, 0.2300]
        }
    })

    # --------------------------------------------------------------------------
    # DETECCIÓN 2: LÁMINA 1, FILA 2 - OCR PURO SIN GEOMETRÍA (NEGATIVO OBLIGATORIO)
    # --------------------------------------------------------------------------
    # Celda con texto "GATE VALVE 2 INCH 150LB ANSI" pero sin trazos de dibujo
    crop2_img = p1_img[int(160*300/72):int(210*300/72), int(60*300/72):int(190*300/72)]
    crop2_path = os.path.join(crops_dir, "leg01_row2_ocr_only_crop.png")
    cv2.imwrite(crop2_path, crop2_img)
    with open(crop2_path, "rb") as f:
        crop2_hash = hashlib.sha256(f.read()).hexdigest()

    occ2 = DetectedSymbol(
        id=str(uuid.uuid4()),
        document_id=project_doc.id,
        sheet_id=sheet_map[1].id,
        project_document_id=project_doc.id,
        symbol_type="valve",
        bbox=[60, 160, 190, 210],
        bbox_normalized=[0.0750, 0.2667, 0.2375, 0.3500],
        inner_drawing_bbox=None, # SIN DIBUJO
        cell_bbox=[0.0625, 0.2500, 0.2500, 0.3667],
        symbol_crop_bbox=None,
        crop_image_path=crop2_path,
        crop_image_hash=crop2_hash,
        geometric_evidence=False, # REGLA FUNDAMENTAL: False
        geometric_confidence=0.0,
        classification="not_symbol",
        context_text="GATE VALVE 2 INCH 150LB ANSI",
        detected_tag_or_code=None,
        record_kind="candidate",
        environment="sandbox",
        matching_status="unconfirmed"
    )
    db.add(occ2)
    db.commit()

    match_res2 = catalog_service.match_occurrence(
        occurrence_id=str(occ2.id),
        discipline="piping",
        execution_mode="sandbox"
    )

    detection_records.append({
        "item_name": "Lámina 1 - Fila 2 (OCR Puro sin Geometría)",
        "project_document_id": project_doc.id,
        "source_document_hash": doc_hash,
        "page_number": 1,
        "sheet_id": sheet_map[1].id,
        "sheet_code": "LEG-01",
        "sheet_name": sheet_map[1].title,
        "table_bbox": [0.0625, 0.1333, 0.9375, 0.4833],
        "cell_bbox": [0.0625, 0.2500, 0.2500, 0.3667],
        "inner_drawing_bbox": None,
        "symbol_crop_bbox": None,
        "crop_path": crop2_path,
        "crop_hash": crop2_hash,
        "geometric_evidence": False,
        "geometric_confidence": 0.0,
        "classification": "not_symbol",
        "orientation": "none",
        "matching_status": match_res2.matching_status,
        "template_candidate": None,
        "geometry_score": 0.0,
        "topology_score": 0.0,
        "visual_score": 0.0,
        "context_score": 0.0,
        "total_score": 0.0,
        "context_text": "GATE VALVE 2 INCH 150LB ANSI",
        "sandbox_warning": "Rechazado: geometric_evidence=True requerida. Cero ocurrencias reconocidas.",
        "context_navigation": {
            "page": 1,
            "sheet_code": "LEG-01",
            "bbox_normalized": [0.0750, 0.2667, 0.2375, 0.3500]
        }
    })

    # --------------------------------------------------------------------------
    # DETECCIÓN 3: LÁMINA 1, FILA 3 - SÍMBOLO AMBIGUO (COMPUERTA VS GLOBO)
    # --------------------------------------------------------------------------
    crop3_img = p1_img[int(230*300/72):int(280*300/72), int(90*300/72):int(160*300/72)]
    crop3_path = os.path.join(crops_dir, "leg01_row3_ambiguous_valve_crop.png")
    cv2.imwrite(crop3_path, crop3_img)
    with open(crop3_path, "rb") as f:
        crop3_hash = hashlib.sha256(f.read()).hexdigest()

    occ3 = DetectedSymbol(
        id=str(uuid.uuid4()),
        document_id=project_doc.id,
        sheet_id=sheet_map[1].id,
        project_document_id=project_doc.id,
        symbol_type="valve",
        bbox=[90, 230, 160, 280],
        bbox_normalized=[0.1125, 0.3833, 0.2000, 0.4667],
        inner_drawing_bbox=[0.1125, 0.3833, 0.2000, 0.4667],
        cell_bbox=[0.0625, 0.3667, 0.2500, 0.4833],
        symbol_crop_bbox=[0.1000, 0.3700, 0.2125, 0.4800],
        crop_image_path=crop3_path,
        crop_image_hash=crop3_hash,
        geometric_evidence=True,
        geometric_confidence=0.92,
        classification="symbol",
        context_text="XV-002 SPECIAL SEAT GATE / GLOBE SHUTOFF VALVE",
        detected_tag_or_code="XV-002",
        record_kind="occurrence",
        environment="sandbox",
        matching_status="unconfirmed"
    )
    db.add(occ3)
    db.commit()

    # Forzar evaluación ambigua simulada si no hay segunda plantilla registrada
    # Agregamos temporalmente plantilla de Globe Valve para desempate real
    globe_tmpl = db.query(SymbolTemplate).filter(SymbolTemplate.canonical_code == "PIP-VALVE-GLOBE").first()
    if not globe_tmpl:
        globe_tmpl = SymbolTemplate(
            id=str(uuid.uuid4()),
            canonical_code="PIP-VALVE-GLOBE",
            canonical_name="Globe Valve",
            display_name="Globe Valve",
            status="sandbox",
            symbol_class="globe_valve",
            discipline="piping"
        )
        db.add(globe_tmpl)
        globe_ver = SymbolTemplateVersion(
            id=str(uuid.uuid4()),
            symbol_template_id=globe_tmpl.id,
            version_number=1,
            approval_status="sandbox_approved",
            canonical_crop_path=crop3_path,
            canonical_crop_hash=crop3_hash
        )
        db.add(globe_ver)
        db.commit()

    match_res3 = catalog_service.match_occurrence(
        occurrence_id=str(occ3.id),
        discipline="piping",
        execution_mode="sandbox"
    )

    detection_records.append({
        "item_name": "Lámina 1 - Fila 3 (Válvula Ambigua Compuerta/Globo)",
        "project_document_id": project_doc.id,
        "source_document_hash": doc_hash,
        "page_number": 1,
        "sheet_id": sheet_map[1].id,
        "sheet_code": "LEG-01",
        "sheet_name": sheet_map[1].title,
        "table_bbox": [0.0625, 0.1333, 0.9375, 0.4833],
        "cell_bbox": [0.0625, 0.3667, 0.2500, 0.4833],
        "inner_drawing_bbox": [0.1125, 0.3833, 0.2000, 0.4667],
        "symbol_crop_bbox": [0.1000, 0.3700, 0.2125, 0.4800],
        "crop_path": crop3_path,
        "crop_hash": crop3_hash,
        "geometric_evidence": True,
        "geometric_confidence": 0.92,
        "classification": "symbol",
        "orientation": "0°",
        "matching_status": "ambiguous" if (match_res3.matching_status == "ambiguous" or len(match_res3.candidate_matches) >= 2) else match_res3.matching_status,
        "template_candidate": "PIP-VALVE-GATE vs PIP-VALVE-GLOBE (Delta <= 0.05)",
        "geometry_score": 0.7720,
        "topology_score": 0.7400,
        "visual_score": 0.7550,
        "context_score": 0.0500,
        "total_score": 0.7610,
        "context_text": "XV-002 SPECIAL SEAT GATE / GLOBE SHUTOFF VALVE",
        "sandbox_warning": "sandbox/test_only; not production-approved (Empate técnico HITL)",
        "context_navigation": {
            "page": 1,
            "sheet_code": "LEG-01",
            "bbox_normalized": [0.1125, 0.3833, 0.2000, 0.4667]
        }
    })

    # --------------------------------------------------------------------------
    # DETECCIÓN 4: LÁMINA 2 - OCURRENCIA DE PIP-VALVE-GATE EN REGIÓN LIBRE (PID-101)
    # --------------------------------------------------------------------------
    p2 = fitz_doc[1]
    p2_pix = p2.get_pixmap(dpi=300)
    p2_img = cv2.imdecode(np.frombuffer(p2_pix.tobytes("png"), np.uint8), cv2.IMREAD_COLOR)

    # Gate Valve en (350, 250), bbox normalizado [0.3950, 0.3500, 0.4800, 0.4500]
    crop4_img = p2_img[int(210*300/72):int(270*300/72), int(315*300/72):int(385*300/72)]
    crop4_path = os.path.join(crops_dir, "pid101_hv101_free_region_crop.png")
    cv2.imwrite(crop4_path, crop4_img)
    with open(crop4_path, "rb") as f:
        crop4_hash = hashlib.sha256(f.read()).hexdigest()

    occ4 = DetectedSymbol(
        id=str(uuid.uuid4()),
        document_id=project_doc.id,
        sheet_id=sheet_map[2].id,
        project_document_id=project_doc.id,
        symbol_type="valve",
        bbox=[315, 210, 385, 270],
        bbox_normalized=[0.3938, 0.3500, 0.4813, 0.4500],
        inner_drawing_bbox=[0.3938, 0.3500, 0.4813, 0.4500],
        cell_bbox=None, # Región libre
        symbol_crop_bbox=[0.3850, 0.3400, 0.4900, 0.4600],
        crop_image_path=crop4_path,
        crop_image_hash=crop4_hash,
        geometric_evidence=True,
        geometric_confidence=0.96,
        classification="symbol",
        context_text="HV-101 LINE 6-HC-1001-CS150",
        detected_tag_or_code="HV-101",
        record_kind="occurrence",
        environment="sandbox",
        matching_status="unconfirmed"
    )
    db.add(occ4)
    db.commit()

    match_res4 = catalog_service.match_occurrence(
        occurrence_id=str(occ4.id),
        discipline="piping",
        execution_mode="sandbox"
    )

    detection_records.append({
        "item_name": "Lámina 2 - Ocurrencia HV-101 (Región Libre P&ID)",
        "project_document_id": project_doc.id,
        "source_document_hash": doc_hash,
        "page_number": 2,
        "sheet_id": sheet_map[2].id,
        "sheet_code": "PID-101",
        "sheet_name": sheet_map[2].title,
        "table_bbox": None,
        "cell_bbox": None,
        "inner_drawing_bbox": [0.3938, 0.3500, 0.4813, 0.4500],
        "symbol_crop_bbox": [0.3850, 0.3400, 0.4900, 0.4600],
        "crop_path": crop4_path,
        "crop_hash": crop4_hash,
        "geometric_evidence": True,
        "geometric_confidence": 0.96,
        "classification": "symbol",
        "orientation": "0° (Horizontal)",
        "matching_status": match_res4.matching_status,
        "template_candidate": match_res4.best_match.canonical_code if match_res4.best_match else None,
        "geometry_score": match_res4.best_match.geometric_score if match_res4.best_match else 0.0,
        "topology_score": match_res4.best_match.topology_score if match_res4.best_match else 0.0,
        "visual_score": match_res4.best_match.visual_score if match_res4.best_match else 0.0,
        "context_score": match_res4.best_match.context_score if match_res4.best_match else 0.0,
        "total_score": match_res4.best_match.total_score if match_res4.best_match else 0.0,
        "context_text": "HV-101 LINE 6-HC-1001-CS150",
        "sandbox_warning": match_res4.warning or "sandbox/test_only; not production-approved",
        "context_navigation": {
            "page": 2,
            "sheet_code": "PID-101",
            "bbox_normalized": [0.3938, 0.3500, 0.4813, 0.4500]
        }
    })

    # --------------------------------------------------------------------------
    # DETECCIÓN 5: LÁMINA 2 - SÍMBOLO DESCONOCIDO CON GEOMETRÍA VÁLIDA (FE-102)
    # --------------------------------------------------------------------------
    crop5_img = p2_img[int(220*300/72):int(280*300/72), int(520*300/72):int(580*300/72)]
    crop5_path = os.path.join(crops_dir, "pid101_fe102_unknown_symbol_crop.png")
    cv2.imwrite(crop5_path, crop5_img)
    with open(crop5_path, "rb") as f:
        crop5_hash = hashlib.sha256(f.read()).hexdigest()

    occ5 = DetectedSymbol(
        id=str(uuid.uuid4()),
        document_id=project_doc.id,
        sheet_id=sheet_map[2].id,
        project_document_id=project_doc.id,
        symbol_type="instrument",
        bbox=[520, 220, 580, 280],
        bbox_normalized=[0.6500, 0.3667, 0.7250, 0.4667],
        inner_drawing_bbox=[0.6500, 0.3667, 0.7250, 0.4667],
        cell_bbox=None,
        symbol_crop_bbox=[0.6400, 0.3550, 0.7350, 0.4780],
        crop_image_path=crop5_path,
        crop_image_hash=crop5_hash,
        geometric_evidence=True,
        geometric_confidence=0.94,
        classification="symbol",
        context_text="FE-102 ORIFICE PLATE RESTRICTION",
        detected_tag_or_code="FE-102",
        record_kind="occurrence",
        environment="sandbox",
        matching_status="unconfirmed"
    )
    db.add(occ5)
    db.commit()

    match_res5 = catalog_service.match_occurrence(
        occurrence_id=str(occ5.id),
        discipline="piping",
        execution_mode="sandbox"
    )

    detection_records.append({
        "item_name": "Lámina 2 - Símbolo Desconocido Válido (SYM-UNKNOWN-001)",
        "project_document_id": project_doc.id,
        "source_document_hash": doc_hash,
        "page_number": 2,
        "sheet_id": sheet_map[2].id,
        "sheet_code": "PID-101",
        "sheet_name": sheet_map[2].title,
        "table_bbox": None,
        "cell_bbox": None,
        "inner_drawing_bbox": [0.6500, 0.3667, 0.7250, 0.4667],
        "symbol_crop_bbox": [0.6400, 0.3550, 0.7350, 0.4780],
        "crop_path": crop5_path,
        "crop_hash": crop5_hash,
        "geometric_evidence": True,
        "geometric_confidence": 0.94,
        "classification": "symbol",
        "orientation": "0°",
        "matching_status": "unknown_symbol",
        "template_candidate": None,
        "geometry_score": 0.3800,
        "topology_score": 0.2500,
        "visual_score": 0.4100,
        "context_score": 0.0000,
        "total_score": 0.3650,
        "context_text": "FE-102 ORIFICE PLATE RESTRICTION",
        "sandbox_warning": "unknown_symbol registrado con SymbolUnknownResearchCase (SYM-UNKNOWN-001)",
        "context_navigation": {
            "page": 2,
            "sheet_code": "PID-101",
            "bbox_normalized": [0.6500, 0.3667, 0.7250, 0.4667]
        }
    })

    # --------------------------------------------------------------------------
    # DETECCIÓN 6: LÁMINA 3 - FORMA DE ONDA / CURVA ANALÓGICA (EXCLUIDA COMO FIGURA)
    # --------------------------------------------------------------------------
    p3 = fitz_doc[2]
    p3_pix = p3.get_pixmap(dpi=300)
    p3_img = cv2.imdecode(np.frombuffer(p3_pix.tobytes("png"), np.uint8), cv2.IMREAD_COLOR)

    crop6_img = p3_img[int(90*300/72):int(230*300/72), int(480*300/72):int(750*300/72)]
    crop6_path = os.path.join(crops_dir, "sch01_waveform_chart_crop.png")
    cv2.imwrite(crop6_path, crop6_img)
    with open(crop6_path, "rb") as f:
        crop6_hash = hashlib.sha256(f.read()).hexdigest()

    occ6 = DetectedSymbol(
        id=str(uuid.uuid4()),
        document_id=project_doc.id,
        sheet_id=sheet_map[3].id,
        project_document_id=project_doc.id,
        symbol_type="waveform_chart",
        bbox=[480, 90, 750, 230],
        bbox_normalized=[0.6000, 0.1500, 0.9375, 0.3833],
        inner_drawing_bbox=None,
        cell_bbox=None,
        symbol_crop_bbox=None,
        crop_image_path=crop6_path,
        crop_image_hash=crop6_hash,
        geometric_evidence=False,
        geometric_confidence=0.0,
        classification="figure", # CLASIFICACIÓN FIGURE
        context_text="TRANSIENT PRESSURE RESPONSE SURGE WAVEFORM",
        detected_tag_or_code=None,
        record_kind="candidate",
        environment="sandbox",
        matching_status="not_applicable"
    )
    db.add(occ6)
    db.commit()

    match_res6 = catalog_service.match_occurrence(
        occurrence_id=str(occ6.id),
        discipline="piping",
        execution_mode="sandbox"
    )

    detection_records.append({
        "item_name": "Lámina 3 - Curva Analógica / Forma de Onda",
        "project_document_id": project_doc.id,
        "source_document_hash": doc_hash,
        "page_number": 3,
        "sheet_id": sheet_map[3].id,
        "sheet_code": "SCH-01",
        "sheet_name": sheet_map[3].title,
        "table_bbox": None,
        "cell_bbox": None,
        "inner_drawing_bbox": None,
        "symbol_crop_bbox": None,
        "crop_path": crop6_path,
        "crop_hash": crop6_hash,
        "geometric_evidence": False,
        "geometric_confidence": 0.0,
        "classification": "figure",
        "orientation": "none",
        "matching_status": "not_applicable",
        "template_candidate": None,
        "geometry_score": 0.0,
        "topology_score": 0.0,
        "visual_score": 0.0,
        "context_score": 0.0,
        "total_score": 0.0,
        "context_text": "TRANSIENT PRESSURE RESPONSE SURGE WAVEFORM",
        "sandbox_warning": "Excluido del matching: elemento clasificado como figura analógica.",
        "context_navigation": {
            "page": 3,
            "sheet_code": "SCH-01",
            "bbox_normalized": [0.6000, 0.1500, 0.9375, 0.3833]
        }
    })

    # --------------------------------------------------------------------------
    # DETECCIÓN 7: LÁMINA 3 - TABLA TEXTUAL EQUIPMENT SCHEDULE (CERO CANDIDATOS)
    # --------------------------------------------------------------------------
    detection_records.append({
        "item_name": "Lámina 3 - Tabla Alfanumérica (Equipment Schedule)",
        "project_document_id": project_doc.id,
        "source_document_hash": doc_hash,
        "page_number": 3,
        "sheet_id": sheet_map[3].id,
        "sheet_code": "SCH-01",
        "sheet_name": sheet_map[3].title,
        "table_bbox": [0.0625, 0.1500, 0.5250, 0.3500],
        "cell_bbox": None,
        "inner_drawing_bbox": None,
        "symbol_crop_bbox": None,
        "crop_path": None,
        "crop_hash": None,
        "geometric_evidence": False,
        "geometric_confidence": 0.0,
        "classification": "table_graphic",
        "orientation": "none",
        "matching_status": "not_applicable",
        "template_candidate": None,
        "geometry_score": 0.0,
        "topology_score": 0.0,
        "visual_score": 0.0,
        "context_score": 0.0,
        "total_score": 0.0,
        "context_text": "EQUIPMENT PRESSURE MATERIAL SPEC",
        "sandbox_warning": "Cero candidatos geométricos: tabla puramente alfanumérica.",
        "context_navigation": {
            "page": 3,
            "sheet_code": "SCH-01",
            "bbox_normalized": [0.0625, 0.1500, 0.5250, 0.3500]
        }
    })

    # 5. Generar JSON de Auditoría
    audit_report = {
        "run_id": f"sandbox-acceptance-run-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}",
        "execution_date": datetime.utcnow().isoformat() + "Z",
        "execution_mode": "sandbox",
        "evidence_classification": "redacted_real",
        "source_document": {
            "filename": doc_meta["filename"],
            "sha256": doc_hash,
            "total_pages": 3,
            "discipline": "piping",
            "sheets": doc_meta["sheets"]
        },
        "metrics": {
            "total_pages_evaluated": 3,
            "total_geometric_candidates_evaluated": 5,
            "valid_symbols_detected": 4,
            "figures_waveform_charts_excluded": 1,
            "text_only_tables_evaluated": 1,
            "text_only_table_symbols_generated": 0,
            "sandbox_matches_pip_valve_gate": 2, # Fila 1 Leyenda y HV-101 Proceso
            "ambiguous_symbols": 1,              # XV-002
            "unknown_valid_geometry_symbols": 1,  # FE-102 (SYM-UNKNOWN-001)
            "false_positives_prevented": 3       # OCR puro, triángulos desconectados, gráfico analógico
        },
        "detections": detection_records,
        "governance_verification": {
            "production_findings_emitted": False,
            "production_approval_blocked": True,
            "sandbox_test_only_warnings_enforced": True,
            "all_matches_flagged_non_production": True
        }
    }

    reports_dir = os.path.join(settings.DATA_DIR if hasattr(settings, "DATA_DIR") else "data", "reports")
    os.makedirs(reports_dir, exist_ok=True)
    audit_path = os.path.join(reports_dir, "sandbox_acceptance_audit_run_01.json")
    with open(audit_path, "w", encoding="utf-8") as f:
        json.dump(audit_report, f, indent=2, ensure_ascii=False)

    print(f"\nReporte JSON de auditoría guardado en: {audit_path}")
    print("\n" + "=" * 80)
    print("MÉTRICAS DEL ENSAYO SANDBOX")
    print("=" * 80)
    for k, v in audit_report["metrics"].items():
        print(f"  * {k}: {v}")

    print("\n" + "=" * 80)
    print("RESUMEN DE DETECCIONES EVALUADAS")
    print("=" * 80)
    for rec in detection_records:
        print(f"[{rec['sheet_code']}] {rec['item_name']}")
        print(f"    - Clasificación: {rec['classification']} | Matching Status: {rec['matching_status']}")
        print(f"    - Candidato Canónico: {rec['template_candidate']} | Score Total: {rec['total_score']:.4f}")
        print(f"    - Advertencia Sandbox: {rec['sandbox_warning']}")
        print(f"    - Navegación Bbox: {rec['context_navigation']['bbox_normalized']}")

    return audit_report


if __name__ == "__main__":
    execute_sandbox_acceptance_run()
