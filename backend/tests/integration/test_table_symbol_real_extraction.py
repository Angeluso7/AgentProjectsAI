import os
import sys
import uuid
import tempfile
import pytest
import fitz  # PyMuPDF
from pathlib import Path
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models.core import Organization, Project
from app.db.models.intake_extractions import (
    SourceExtraction, ExtractedItem, StructuredSymbol, RuleDocument
)
from app.services.tables.extractor import TableExtractor, ExtractedCellDTO
from app.services.extraction.candidate_generator_service import CandidateGeneratorService
from app.services.extraction.candidate_enrichment_service import CandidateEnrichmentService
from app.services.engines.registry import engine_registry


def create_oguc_legend_table_pdf() -> tuple[bytes, dict]:
    """
    Crea un PDF sintético en memoria con una tabla de simbología equivalente a la OGUC
    (Ordenanza General de Urbanismo y Construcciones de Chile, Art. 4.3.4 / NCh 1433 / NFPA).
    
    Estructura de la tabla:
    - 6 filas (1 encabezado + 5 filas de datos)
    - 3 columnas:
      Col 0: SÍMBOLO (vectores gráficos B/N en la celda)
      Col 1: DENOMINACIÓN TÉCNICA (texto a la derecha)
      Col 2: NORMATIVA APLICABLE (texto normativo)
    
    Retorna métricas esperadas:
    - visible_symbols_drawn = 5
    """
    doc = fitz.open()
    page = doc.new_page(width=800, height=600)

    # Título del documento
    page.insert_text(
        fitz.Point(50, 40),
        "CUADRO DE SIMBOLOGÍA DE SEGURIDAD CONTRA INCENDIOS - OGUC ART. 4.3.4",
        fontsize=12,
        fontname="helv",
        color=(0, 0, 0)
    )

    # Coordenadas de la tabla
    col_x = [50, 180, 560, 750]  # 3 columnas
    row_y = [70, 110, 170, 230, 290, 350, 410]  # 6 filas (0 = encabezado, 1..5 = símbolos)

    # 1. Dibujar cuadrícula de la tabla con líneas vectoriales
    # Líneas horizontales
    for y in row_y:
        page.draw_line(fitz.Point(col_x[0], y), fitz.Point(col_x[-1], y), color=(0, 0, 0), width=1.0)
    # Líneas verticales
    for x in col_x:
        page.draw_line(fitz.Point(x, row_y[0]), fitz.Point(x, row_y[-1]), color=(0, 0, 0), width=1.0)

    # 2. Encabezados (Fila 0)
    page.insert_text(fitz.Point(col_x[0] + 30, row_y[0] + 25), "SÍMBOLO", fontsize=10, fontname="helv", color=(0, 0, 0))
    page.insert_text(fitz.Point(col_x[1] + 20, row_y[0] + 25), "DENOMINACIÓN / ESPECIFICACIÓN TÉCNICA", fontsize=10, fontname="helv", color=(0, 0, 0))
    page.insert_text(fitz.Point(col_x[2] + 15, row_y[0] + 25), "NORMA APLICABLE", fontsize=10, fontname="helv", color=(0, 0, 0))

    # 3. Filas de datos con símbolos B/N en Col 0 y descripciones a la derecha
    symbols_spec = [
        {
            "row": 1,
            "name": "Puerta Cortafuego F-60 con Cierrapuertas Automático",
            "standard": "OGUC Art. 4.3.4 / NCh 935",
            # Dibujar símbolo 1: marco de puerta + arco de abatimiento
            "draw": lambda p, cx, cy: (
                p.draw_rect(fitz.Rect(cx - 20, cy - 20, cx + 20, cy + 20), color=(0, 0, 0), width=1.5),
                p.draw_line(fitz.Point(cx - 20, cy + 20), fitz.Point(cx + 10, cy - 10), color=(0, 0, 0), width=2.0),
                p.draw_circle(fitz.Point(cx - 20, cy + 20), 28, color=(0, 0, 0), width=1.0)
            )
        },
        {
            "row": 2,
            "name": "Extintor Polvo Químico Seco PQS 10kg ABC",
            "standard": "DS 594 Art. 45 / NCh 1433",
            # Dibujar símbolo 2: cilindro de extintor con manija y tobera
            "draw": lambda p, cx, cy: (
                p.draw_rect(fitz.Rect(cx - 12, cy - 15, cx + 12, cy + 20), color=(0, 0, 0), fill=(0.1, 0.1, 0.1), width=1.5),
                p.draw_line(fitz.Point(cx, cy - 15), fitz.Point(cx, cy - 24), color=(0, 0, 0), width=2.0),
                p.draw_line(fitz.Point(cx - 8, cy - 24), fitz.Point(cx + 8, cy - 24), color=(0, 0, 0), width=2.0),
                p.draw_line(fitz.Point(cx + 3, cy - 20), fitz.Point(cx + 18, cy - 5), color=(0, 0, 0), width=1.5)
            )
        },
        {
            "row": 3,
            "name": "Gabinete Red Húmeda Manguera Semirrígida 25m",
            "standard": "RIDAA Art. 54 / NCh 1433",
            # Dibujar símbolo 3: gabinete cuadrado con carrete circular interno
            "draw": lambda p, cx, cy: (
                p.draw_rect(fitz.Rect(cx - 22, cy - 22, cx + 22, cy + 22), color=(0, 0, 0), width=1.5),
                p.draw_circle(fitz.Point(cx, cy), 14, color=(0, 0, 0), width=1.5),
                p.draw_circle(fitz.Point(cx, cy), 5, color=(0, 0, 0), fill=(0, 0, 0))
            )
        },
        {
            "row": 4,
            "name": "Detector Fotoeléctrico Óptico de Humo Direccionable",
            "standard": "NFPA 72 / OGUC Art. 4.3.8",
            # Dibujar símbolo 4: círculo con cruceta y anillo concéntrico
            "draw": lambda p, cx, cy: (
                p.draw_circle(fitz.Point(cx, cy), 20, color=(0, 0, 0), width=1.5),
                p.draw_circle(fitz.Point(cx, cy), 10, color=(0, 0, 0), width=1.0),
                p.draw_line(fitz.Point(cx - 20, cy), fitz.Point(cx + 20, cy), color=(0, 0, 0), width=1.0),
                p.draw_line(fitz.Point(cx, cy - 20), fitz.Point(cx, cy + 20), color=(0, 0, 0), width=1.0)
            )
        },
        {
            "row": 5,
            "name": "Pulsador Manual de Alarma de Incendio Tipo Tirador",
            "standard": "NFPA 72 / NCh 1433",
            # Dibujar símbolo 5: caja cuadrada con palanca central y triángulo
            "draw": lambda p, cx, cy: (
                p.draw_rect(fitz.Rect(cx - 18, cy - 18, cx + 18, cy + 18), color=(0, 0, 0), width=1.5),
                p.draw_rect(fitz.Rect(cx - 8, cy - 8, cx + 8, cy + 8), color=(0, 0, 0), fill=(0.2, 0.2, 0.2), width=1.0),
                p.draw_line(fitz.Point(cx, cy + 8), fitz.Point(cx, cy + 16), color=(0, 0, 0), width=2.5)
            )
        }
    ]

    for item in symbols_spec:
        r = item["row"]
        y_top = row_y[r]
        y_bottom = row_y[r + 1]
        cy = (y_top + y_bottom) / 2
        cx = (col_x[0] + col_x[1]) / 2

        # Dibujar símbolo gráfico dentro de la celda de la columna 0
        item["draw"](page, cx, cy)

        # Insertar textos en columna 1 y columna 2
        page.insert_text(fitz.Point(col_x[1] + 10, cy + 4), item["name"], fontsize=8.5, fontname="helv", color=(0, 0, 0))
        page.insert_text(fitz.Point(col_x[2] + 10, cy + 4), item["standard"], fontsize=8.5, fontname="helv", color=(0, 0, 0))

    pdf_bytes = doc.write()
    doc.close()

    return pdf_bytes, {
        "visible_symbols_drawn": len(symbols_spec),
        "total_rows": len(row_y) - 1,
        "total_cols": len(col_x) - 1,
        "symbols_spec": symbols_spec,
        "table_bbox_norm": [col_x[0] / 800.0, row_y[0] / 600.0, col_x[-1] / 800.0, row_y[-1] / 600.0]
    }


def test_oguc_real_case_symbol_table_pipeline_end_to_end(db_session: Session):
    """
    Condición Obligatoria 1: Validación con un caso real equivalente al de OGUC.
    
    Demostración cuantitativa exigida por el usuario:
    1. Número de símbolos visibles en la tabla: 5
    2. Número de symbol_cell detectadas: 5
    3. Número de StructuredSymbol creados: 5
    4. Número de crops válidos existentes físicamente en disco: 5
    5. Número de símbolos efectivamente visibles en el filtro UI (Símbolos): 5
    """
    # 1. Crear documento PDF sintético en memoria representativo de OGUC
    pdf_bytes, meta = create_oguc_legend_table_pdf()
    
    visible_symbols_in_table = meta["visible_symbols_drawn"]
    assert visible_symbols_in_table == 5, "Debe haber exactamente 5 símbolos dibujados en la tabla."

    # Abrir documento con fitz desde memoria
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[0]
    doc_uid = f"oguc_test_{uuid.uuid4().hex[:8]}"

    try:
        # Extraer palabras del PDF
        raw_words = page.get_text("words")
        texts = []
        for w in raw_words:
            texts.append({
                "text": w[4],
                "clean_text": w[4].strip(),
                "bbox_normalized": [w[0] / page.rect.width, w[1] / page.rect.height, w[2] / page.rect.width, w[3] / page.rect.height],
                "id": str(uuid.uuid4())
            })

        # 2. Ejecutar TableExtractor sobre la región geométrica exacta de la tabla
        extractor = TableExtractor(width_px=int(page.rect.width), height_px=int(page.rect.height))
        extracted_table = extractor.extract_from_region(
            region_bbox_norm=meta["table_bbox_norm"],
            texts=texts,
            symbols=[],  # Sin símbolos previos: debe descubrirlos examinando la tinta visual de cada celda
            page=page,
            doc_uid=doc_uid
        )

        assert extracted_table is not None, "La tabla de simbología debe ser detectada."
        assert extracted_table.row_count == 6, f"Debe tener 6 filas (1 encabezado + 5 datos), obtuvo {extracted_table.row_count}"
        assert extracted_table.column_count == 3, f"Debe tener 3 columnas, obtuvo {extracted_table.column_count}"

        # 3. Validar detección de symbol_cell / symbol_only en la geometría tabular
        detected_symbol_cells = [c for c in extracted_table.cells if c.cell_type in ("symbol_only", "symbol_cell") and c.has_symbol]
        number_of_symbol_cells_detected = len(detected_symbol_cells)
        
        print(f"\n========================================================")
        print(f" DEMOSTRACIÓN CUANTITATIVA CASO REAL OGUC (Art. 4.3.4)")
        print(f"========================================================")
        print(f" [MÉTRICA 1] Símbolos visibles dibujados en tabla:     {visible_symbols_in_table}")
        print(f" [MÉTRICA 2] Celdas clasificadas como 'symbol_cell':   {number_of_symbol_cells_detected}")
        assert number_of_symbol_cells_detected == 5, (
            f"Se esperaban 5 symbol_cell detectadas en col 0 (filas 1..5), se detectaron {number_of_symbol_cells_detected}"
        )

        # Todas las symbol_cells deben estar en la columna 0 (filas 1 a 5)
        for c in detected_symbol_cells:
            assert c.column_index == 0, f"La celda de símbolo debe estar en columna 0, fila {c.row_index}"
            assert 1 <= c.row_index <= 5, f"La fila del símbolo debe estar entre 1 y 5, obtuvo {c.row_index}"
            assert c.crop_image_path is not None, f"La celda {c.row_index}, {c.column_index} debe tener crop_image_path"

        # 4. Validar generación de candidatos de símbolos enriquecidos desde la tabla
        assert len(extracted_table.extracted_symbols) == 5, (
            f"Se esperaban 5 extracted_symbols en ExtractedTableDTO, obtuvo {len(extracted_table.extracted_symbols)}"
        )

        # Validar enriquecimiento de dos fuentes semánticas: texto a la derecha + encabezado superior
        sym0 = extracted_table.extracted_symbols[0]
        assert "Puerta Cortafuego" in sym0.symbol_name or "Puerta" in sym0.symbol_description, (
            f"El símbolo fila 1 debe haber absorbido el texto de la derecha. Obtenido: {sym0.symbol_name} / {sym0.symbol_description}"
        )
        assert sym0.context_association_mode in ("two_sources_right_top", "directional_row_major")
        assert sym0.col_index == 0
        assert sym0.row_index == 1

        # 5. Validar existencia física de los crops en disco
        valid_crops_on_disk = 0
        for sym_cand in extracted_table.extracted_symbols:
            crop_rel_path = sym_cand.crop_image_path
            assert crop_rel_path is not None, "El candidato de símbolo debe tener crop_image_path asignado"
            
            crop_filename = Path(crop_rel_path).name
            expected_disk_path = Path(settings.STORAGE_LOCAL_ROOT) / "crops" / "symbols" / crop_filename
            
            assert expected_disk_path.exists(), f"El archivo de recorte {expected_disk_path} debe existir físicamente en disco."
            assert expected_disk_path.stat().st_size > 100, f"El archivo de recorte debe tener contenido visual (> 100 bytes), tamaño: {expected_disk_path.stat().st_size}"
            valid_crops_on_disk += 1

        print(f" [MÉTRICA 4] Recortes visuales válidos en disco:       {valid_crops_on_disk}")
        assert valid_crops_on_disk == 5, f"Se esperaban 5 crops válidos en disco, se encontraron {valid_crops_on_disk}"

        # 6. Integración con Capa 2: CandidateGeneratorService & Base de Datos
        org = Organization(id=str(uuid.uuid4()), name="Org OGUC Test", slug=f"org-oguc-{uuid.uuid4().hex[:6]}")
        proj = Project(id=str(uuid.uuid4()), organization_id=org.id, code=f"PRJ-{uuid.uuid4().hex[:4].upper()}", name="Proyecto OGUC", status="active")
        db_session.add(org)
        db_session.add(proj)

        extraction = SourceExtraction(
            id=str(uuid.uuid4()),
            organization_id=org.id,
            project_id=proj.id,
            source_asset_id=doc_uid,
            source_origin="document",
            title="OGUC Tabla de Simbología Incendio",
            extraction_mode="ai_document",
            status="pending",
            metadata_info={"file_name": "oguc_seguridad_incendios_legend.pdf"}
        )
        db_session.add(extraction)
        db_session.commit()

        # Armar evidence_payload multimodal con la tabla y sus símbolos extraídos
        evidence_payload = {
            "document_id": doc_uid,
            "provenance": {"file_hash_sha256": "fake_hash_oguc"},
            "tables": [
                {
                    "title": "CUADRO DE SIMBOLOGÍA DE SEGURIDAD CONTRA INCENDIOS",
                    "headers": ["SÍMBOLO", "DENOMINACIÓN", "NORMA"],
                    "rows": [
                        [c.text for c in extracted_table.cells if c.row_index == r]
                        for r in range(1, 6)
                    ],
                    "node_id": f"tbl_node_{doc_uid}",
                    "crop_image_path": f"/data/crops/tables/tbl_{doc_uid}.png",
                    "bbox_normalized": [0.05, 0.05, 0.95, 0.75],
                    "page_number": 1,
                    "extracted_symbols": [
                        {
                            "id": s.id,
                            "tag_or_code": s.tag_or_code,
                            "symbol_name": s.symbol_name,
                            "symbol_description": s.symbol_description,
                            "canonical_symbol_family": s.canonical_symbol_family,
                            "standard_reference": s.standard_reference,
                            "crop_image_path": s.crop_image_path,
                            "needs_visual_crop": s.needs_visual_crop,
                            "crop_error_reason": s.crop_error_reason,
                            "source_table_id": None,
                            "row_index": s.row_index,
                            "col_index": s.col_index,
                            "cell_bbox": s.cell_bbox,
                            "row_bbox": s.row_bbox,
                            "context_association_mode": s.context_association_mode,
                            "aliases": s.aliases,
                            "estimated_physical_size_mm": s.estimated_physical_size_mm
                        }
                        for s in extracted_table.extracted_symbols
                    ]
                }
            ],
            "symbols": []
        }

        gen_service = CandidateGeneratorService(db=db_session)
        generated_candidates = gen_service.generate_candidates_from_evidence(
            extraction_id=extraction.id,
            evidence_payload=evidence_payload,
            discipline="fire_protection",
            document_title="OGUC Art 4.3.4"
        )
        db_session.commit()

        # Verificar candidatos de tipo symbol generados
        symbol_candidates = [c for c in generated_candidates if c.item_type == "symbol" and c.candidate_type == "symbol_candidate"]
        assert len(symbol_candidates) == 5, f"Se esperaban 5 candidatos de símbolo generados, obtuvo {len(symbol_candidates)}"

        # 7. Sincronizar y materializar StructuredSymbol con CandidateEnrichmentService
        enrich_service = CandidateEnrichmentService(db=db_session)
        for cand in symbol_candidates:
            # compute_completeness valida la existencia física del crop en disco
            status = enrich_service.compute_completeness(cand)
            assert status == "complete", f"El candidato {cand.title} debe ser 'complete' al tener crop válido en disco, obtuvo: {status}"
            cand.completeness_status = status
            
            # Materializar StructuredSymbol
            enrich_service.sync_structured_models(cand)

        db_session.commit()

        # Consultar StructuredSymbol en la base de datos
        structured_symbols_in_db = db_session.query(StructuredSymbol).all()
        number_of_structured_symbols_created = len(structured_symbols_in_db)
        print(f"[MÉTRICA 3] Registros 'StructuredSymbol' creados en base de datos: {number_of_structured_symbols_created}")
        assert number_of_structured_symbols_created == 5, (
            f"Se esperaban 5 StructuredSymbol creados, obtuvo {number_of_structured_symbols_created}"
        )

        # Validar linaje tabular en cada StructuredSymbol
        for ss in structured_symbols_in_db:
            assert ss.crop_image_path is not None, "StructuredSymbol debe tener crop_image_path"
            assert ss.layout_context == "inside_table", "StructuredSymbol debe registrar layout_context='inside_table'"
            assert ss.source_table_id is not None, "StructuredSymbol debe registrar source_table_id"
            assert ss.row_index in [1, 2, 3, 4, 5], f"StructuredSymbol debe registrar row_index válido, obtuvo {ss.row_index}"
            assert ss.col_index == 0, f"StructuredSymbol debe registrar col_index=0, obtuvo {ss.col_index}"
            assert ss.context_association_mode in ("two_sources_right_top", "directional_row_major")

        # 8. Validar el filtro de la UI: simular función isSymbolItem del frontend
        def is_symbol_item_ui(it: ExtractedItem) -> bool:
            return (
                it.item_type in ['symbol', 'simbolo', 'leyenda', 'symbol_candidate'] or
                it.candidate_type == 'symbol_candidate' or
                getattr(it, 'category', None) == 'symbol'
            )

        all_extracted_items = db_session.query(ExtractedItem).filter(ExtractedItem.extraction_id == extraction.id).all()
        ui_visible_symbols = [it for it in all_extracted_items if is_symbol_item_ui(it)]
        number_of_ui_visible_symbols = len(ui_visible_symbols)

        print(f"[MÉTRICA 5] Símbolos efectivamente visibles en el filtro 'Símbolos' de la UI: {number_of_ui_visible_symbols}")
        assert number_of_ui_visible_symbols == 5, (
            f"Se esperaban 5 símbolos visibles en el filtro de la UI, obtuvo {number_of_ui_visible_symbols}"
        )

        # Validar que NINGÚN símbolo visible en UI carezca de crop válido
        for ui_sym in ui_visible_symbols:
            assert ui_sym.crop_image_path is not None and len(ui_sym.crop_image_path) > 0, (
                f"Símbolo {ui_sym.title} visible en UI no tiene crop_image_path!"
            )
            assert ui_sym.completeness_status == "complete", (
                f"Símbolo {ui_sym.title} con crop válido debe tener completeness_status='complete', obtuvo {ui_sym.completeness_status}"
            )
            # Metadatos de procedencia para el badge de tabla en UI
            assert ui_sym.metadata_payload.get("source_table_id") is not None
            assert ui_sym.metadata_payload.get("row_index") in [1, 2, 3, 4, 5]
            assert ui_sym.metadata_payload.get("col_index") == 0
    finally:
        doc.close()


def test_ai_task_policy_matrix_defined_per_task():
    """
    Condición Obligatoria 2: Política de IA definida por tarea, no como preferencia global única.
    
    Verifica que la matriz contenga:
    1. Tareas individuales explícitas: OCR, Tables, Symbols, Reasoning, QA/QC Rules
    2. Opción gratuita por defecto en cada tarea (default_engine)
    3. Opción de pago habilitada (paid_engine)
    4. Criterio de fallback explícito (fallback_criteria)
    5. Condiciones de escalamiento (escalation_conditions)
    """
    registry = engine_registry
    policies = registry.list_task_policies()

    assert len(policies) >= 5, f"Deben existir al menos 5 políticas de tareas definidas, obtuvo {len(policies)}"

    required_tasks = ["ocr", "tables", "symbols", "reasoning", "qa_qc_rules"]
    policy_by_task = {p.task_id: p for p in policies}

    for task_id in required_tasks:
        assert task_id in policy_by_task, f"La tarea obligatoria '{task_id}' no está presente en la matriz de políticas de IA."
        policy = policy_by_task[task_id]
        
        # 1. Opción gratuita por defecto
        assert policy.free_default_engine_id is not None and len(policy.free_default_engine_id) > 0, (
            f"Tarea {task_id} debe tener opción gratuita por defecto (free_default_engine_id)"
        )
        assert policy.free_default_name is not None and len(policy.free_default_name) > 0
        
        # 2. Opción paga habilitada
        assert policy.paid_enabled_engine_id is not None and len(policy.paid_enabled_engine_id) > 0, (
            f"Tarea {task_id} debe tener opción de pago habilitada (paid_enabled_engine_id)"
        )
        assert policy.paid_enabled_name is not None and len(policy.paid_enabled_name) > 0

        # 3. Criterio de fallback
        assert policy.fallback_criteria is not None and len(policy.fallback_criteria) > 0, (
            f"Tarea {task_id} debe tener criterio de fallback explícito"
        )

        # 4. Condiciones de escalamiento
        assert policy.escalation_conditions is not None and len(policy.escalation_conditions) > 0, (
            f"Tarea {task_id} debe tener condiciones de escalamiento definidas"
        )

    print("\n[MATRIZ IA] Validación exitosa de las 5 tareas con configuración por tarea.")


def test_missing_crop_enforces_needs_visual_crop_status(db_session: Session):
    """
    Verifica la condición de seguridad:
    Si un candidato de símbolo no posee un crop físico comprobable en disco,
    su estado NO puede ser 'complete' y debe quedar marcado como 'needs_visual_crop'.
    """
    org = Organization(id=str(uuid.uuid4()), name="Org Test Crop", slug=f"org-crop-{uuid.uuid4().hex[:6]}")
    proj = Project(id=str(uuid.uuid4()), organization_id=org.id, code=f"PRJ-{uuid.uuid4().hex[:4].upper()}", name="Proj Test Crop", status="active")
    db_session.add(org)
    db_session.add(proj)

    extraction = SourceExtraction(
        id=str(uuid.uuid4()),
        organization_id=org.id,
        project_id=proj.id,
        source_asset_id="doc_crop_test",
        source_origin="document",
        title="Test Crop Missing",
        extraction_mode="ai_document",
        status="pending",
        metadata_info={}
    )
    db_session.add(extraction)
    db_session.commit()

    # Símbolo con ruta a un archivo inexistente
    item_missing_crop = ExtractedItem(
        id=str(uuid.uuid4()),
        extraction_id=extraction.id,
        item_type="symbol",
        candidate_type="symbol_candidate",
        title="Símbolo Sin Imagen",
        crop_image_path="/data/crops/symbols/non_existent_file_99999.png",
        completeness_status="complete",  # Supuestamente completo
        metadata_payload={"canonical_symbol_family": "valves"}
    )
    db_session.add(item_missing_crop)
    db_session.commit()

    enrich_service = CandidateEnrichmentService(db=db_session)
    status = enrich_service.compute_completeness(item_missing_crop)

    assert status == "needs_visual_crop", (
        f"Al no existir el archivo en disco, el estado debe ser forzado a 'needs_visual_crop', obtuvo: {status}"
    )
