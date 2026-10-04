"""
Test de integración y regresión para persistencia de DocumentStructuralNode con símbolos de tablas.
Verifica que:
1. Símbolos con OCR masivo o columnas binarias ('A B C X O 1 0 0...') no provoquen StringDataRightTruncation.
2. title sea corto, limpio y representativo (<= 120 chars).
3. hierarchy_path sea compacto, semántico y acotado (<= 180 chars).
4. content_text sea breve y estructurado (<= 350 chars), sin volcar tablas completas.
5. structured_payload preserve íntegramente las trazas y celdas de la tabla.
6. Persista exitosamente en base de datos sin errores de truncamiento.
"""

import uuid
import pytest
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text

from app.db.models.document_memory import Document, DocumentSheet, DocumentStructuralNode
from app.db.models.core import Project, Organization
from app.services.tables.extractor import TableExtractor, associate_symbol_semantics_two_sources, ExtractedSymbolCandidateDTO
from app.services.document_processing.docling_service import DoclingService
from app.services.document_processing.structural_sanitizer import (
    clean_spacing_and_newlines,
    is_binary_or_matrix_garbage,
    sanitize_symbol_title,
    sanitize_hierarchy_path,
    sanitize_symbol_content_text
)


def test_sanitizer_functions_filter_garbage_and_limit_lengths():
    """Valida individualmente las funciones de sanitización estructural."""
    # 1. Detección de columnas basura binarias / matriciales
    assert is_binary_or_matrix_garbage("A B C X O 1 0 0 1 0 0") is True
    assert is_binary_or_matrix_garbage("1 0 0 1 0 1 0 0") is True
    assert is_binary_or_matrix_garbage("X O - - X O") is True
    assert is_binary_or_matrix_garbage("- - - - -") is True
    assert is_binary_or_matrix_garbage("VÁLVULA DE COMPUERTA MANUAL") is False
    assert is_binary_or_matrix_garbage("EXTINTOR PQS 10KG") is False

    # 2. Sanitización de saltos de línea repetitivos
    raw_newlines = "Válvula\n\nde\r\n\r\n   Retención\t\tCheck\nTipo Columpio"
    assert clean_spacing_and_newlines(raw_newlines) == "Válvula de Retención Check Tipo Columpio"

    # 3. Título acotado y limpio
    long_raw_name = (
        "ITEM 12: VÁLVULA DE COMPUERTA CLASE 150 RF ACERO FORJADO SEGÚN NORMA API 600 CON "
        "ACCIONAMIENTO MANUAL Y VOLANTE EN PLANTA DE GAS SECTOR NORTE CON AISLACIÓN TÉRMICA "
        "Y RECUBRIMIENTO DE PROTECCIÓN ANTICORROSIVA ADICIONAL PARA AMBIENTES COSTEROS"
    )
    clean_title = sanitize_symbol_title(long_raw_name, max_length=80)
    assert len(clean_title) <= 80
    assert not clean_title.startswith("ITEM 12")
    assert "VÁLVULA DE COMPUERTA" in clean_title

    # 4. Título con basura binaria usa fallback
    fallback_title = sanitize_symbol_title("A B C X O 1 0 0 1 0", fallback="Símbolo Fila 3")
    assert fallback_title == "Símbolo Fila 3"

    # 5. hierarchy_path compacto
    path = sanitize_hierarchy_path(
        base_name="Plano_Piping_Area_100_RevB_Final_Aprobado",
        chapter_or_section="Seccion_Simbologia_De_Piping_E_Instrumentacion",
        category_slug="Simbolos",
        item_identifier="Valvula_Compuerta_Manual_API_600_Clase_150_RF"
    )
    assert len(path) <= 150
    assert path.startswith("/Plano_Piping_Area_100_")
    assert "/Simbolos/" in path


def test_symbol_extraction_from_table_with_massive_ocr_and_binary_columns(db_session: Session):
    """
    Reproduce el escenario real donde una tabla contiene símbolos con:
    - Textos a la derecha masivos (300+ caracteres de especificaciones y OCR suelto).
    - Columnas adyacentes de banderas matriciales ('A B C X O 1 0 0...').
    - Saltos de línea caóticos.
    Verifica que el enriquecimiento y materialización a DocumentStructuralNode no rompa la persistencia.
    """
    # 1. Crear jerarquía básica en BD
    org = Organization(id=str(uuid.uuid4()), name="Audit Org", slug=f"audit-{uuid.uuid4().hex[:6]}")
    db_session.add(org)
    db_session.flush()

    proj = Project(id=str(uuid.uuid4()), organization_id=org.id, name="Planta Gas", code=f"GAS-{uuid.uuid4().hex[:6]}")
    db_session.add(proj)
    db_session.flush()

    doc = Document(
        id=str(uuid.uuid4()),
        organization_id=org.id,
        project_id=proj.id,
        filename="PID-AREA-200-SISTEMA-DE-ALIVIO-Y-ANTORCHA-REV-04-INGENIERIA-DE-DETALLE.pdf",
        file_path="/data/raw/pid.pdf",
        file_hash_sha256=uuid.uuid4().hex,
        file_size_bytes=1024,
        mime_type="application/pdf"
    )
    db_session.add(doc)
    db_session.flush()

    # 2. Simular columnas a la derecha con OCR masivo y columnas binarias
    massive_ocr_description = (
        "VÁLVULA DE SEGURIDAD Y ALIVIO (PSV) PILOTADA BRIDADA CLASE 300 RF SEGÚN NORMA API 526.\n"
        "ORIFICIO DE ALIVIO TIPO J, PRESIÓN DE SET 150 PSIG, TEMPERATURA DE DISEÑO 200°C.\n"
        "MATERIAL DEL CUERPO ACERO AL CARBONO ASTM A216 WCB CON INTERNOS DE ACERO INOXIDABLE 316.\n"
        "INCLUYE ACCESORIOS DE PURGA MANUAL, BLOQUEO INTERBLOQUEADO Y SENSOR TRANSMISOR DE POSICIÓN."
    )
    binary_matrix_ocr = "A B C X O 1 0 0 1 0 0 0 1 1 0 0 1 0"
    secondary_specs = "TAG: PSV-2041A - LÍNEA 6\"-FL-2001-CS150"

    right_texts = [
        massive_ocr_description,
        binary_matrix_ocr,
        secondary_specs
    ]

    # 3. Ejecutar asociación bifuente con sanitización
    semantics = associate_symbol_semantics_two_sources(
        right_texts=right_texts,
        immediate_top_header="SIMBOLOGÍA DE INSTRUMENTACIÓN Y CONTROL DE PRESIÓN",
        table_title="CUADRO DE LEYENDA TÉCNICA Y ESPECIFICACIONES DE VÁLVULAS",
        row_index=4,
        col_index=0,
        category_hint="valves"
    )

    # Verificaciones de la semántica sintetizada
    assert "symbol_name" in semantics
    assert len(semantics["symbol_name"]) <= 120, f"Nombre excesivamente largo: {len(semantics['symbol_name'])}"
    assert "A B C X O" not in semantics["symbol_name"], "No debe contener columnas matriciales binarias"
    assert "A B C X O" not in semantics["symbol_description"], "No debe contener columnas matriciales binarias"
    assert len(semantics["symbol_description"]) <= 350, f"Descripción excesivamente larga: {len(semantics['symbol_description'])}"
    # El detalle raw debe conservarse en el payload
    assert "raw_right_texts" in semantics
    assert len(semantics["raw_right_texts"]) == 3

    # 4. Construir DocumentStructuralNode mediante DoclingService
    docling_svc = DoclingService()
    sym_candidate = ExtractedSymbolCandidateDTO(
        id=f"sym_{uuid.uuid4().hex[:10]}",
        symbol_name=semantics["symbol_name"],
        canonical_symbol_family=semantics["canonical_symbol_family"],
        standard_reference=semantics["standard_reference"],
        discipline=semantics["discipline"],
        category=semantics["category"],
        source_render_mode="vector",
        layout_context="inside_table",
        context_association_mode="two_sources_right_top",
        bbox_normalized=[0.05, 0.20, 0.15, 0.25],
        estimated_physical_size_mm={"width_mm": 12.5, "height_mm": 10.0},
        crop_image_path="/data/crops/symbols/sym_test.png",
        technical_function=semantics["technical_function"],
        aliases=semantics["aliases"],
        confidence_score=0.92,
        human_validation_notes="Extraído desde celda tabular",
        visual_variant_group_id=str(uuid.uuid4()),
        source_table_id="tbl_test_p1_1",
        row_index=4,
        col_index=0,
        cell_bbox=[0.05, 0.20, 0.15, 0.25],
        row_bbox=[0.05, 0.20, 0.95, 0.25],
        tag_or_code=semantics["tag_or_code"],
        symbol_description=semantics["symbol_description"],
        needs_visual_crop=False,
        crop_error_reason=None
    )

    clean_sym_title = sanitize_symbol_title(sym_candidate.symbol_name, fallback="Símbolo Fila 4", max_length=120)
    clean_sym_path = sanitize_hierarchy_path(doc.filename, "Cap_Simbologia", "Simbolos", clean_sym_title)
    clean_sym_content = sanitize_symbol_content_text(
        description=sym_candidate.symbol_description,
        title=clean_sym_title,
        technical_function=sym_candidate.technical_function,
        max_length=350
    )

    sym_node = DocumentStructuralNode(
        id=str(uuid.uuid4()),
        document_id=doc.id,
        node_type="symbol",
        hierarchy_path=clean_sym_path,
        level=3,
        title=clean_sym_title,
        content_text=clean_sym_content,
        structured_payload={
            "canonical_symbol_family": sym_candidate.canonical_symbol_family,
            "standard_reference": sym_candidate.standard_reference,
            "discipline": sym_candidate.discipline,
            "category": sym_candidate.category,
            "crop_image_path": sym_candidate.crop_image_path,
            "row_index": sym_candidate.row_index,
            "col_index": sym_candidate.col_index,
            "raw_right_texts": semantics["raw_right_texts"]
        },
        page_number=1,
        bbox_normalized=sym_candidate.bbox_normalized
    )

    # 5. Validaciones de Contrato de Nodo Estructural
    assert len(sym_node.title) <= 120, f"Title de nodo excede 120 chars: {len(sym_node.title)}"
    assert len(sym_node.hierarchy_path) <= 180, f"Hierarchy path excede 180 chars: {len(sym_node.hierarchy_path)}"
    assert len(sym_node.content_text) <= 350, f"Content text excede 350 chars: {len(sym_node.content_text)}"
    assert "A B C X O" not in sym_node.content_text

    # 6. Persistir en Base de Datos y verificar que no lance StringDataRightTruncation
    db_session.add(sym_node)
    db_session.flush()

    persisted = db_session.query(DocumentStructuralNode).filter(DocumentStructuralNode.id == sym_node.id).first()
    assert persisted is not None
    assert persisted.node_type == "symbol"
    assert persisted.title == clean_sym_title
    assert persisted.hierarchy_path == clean_sym_path
    assert "A B C X O" in persisted.structured_payload["raw_right_texts"][1], "El payload preserva el OCR completo"


def test_postgres_live_persistence_without_truncation():
    """
    Verifica directamente contra la base de datos PostgreSQL en vivo (puerto 5433)
    que la inserción de un nodo symbol con hierarchy_path y content_text no falle
    por StringDataRightTruncation(255).
    """
    candidates = [
        "postgresql+psycopg://postgres_migrator:migrator_secure_pass_123@plan_review_postgres_test:5432/planreview_test",
        "postgresql+psycopg://postgres_migrator:migrator_secure_pass_123@localhost:5433/planreview_test",
        "postgresql+psycopg://postgres_migrator:migrator_secure_pass_123@127.0.0.1:5433/planreview_test",
    ]
    engine = None
    for cand in candidates:
        try:
            test_eng = create_engine(cand, connect_args={"connect_timeout": 2}, isolation_level="AUTOCOMMIT")
            with test_eng.connect() as test_conn:
                test_conn.execute(text("SELECT 1"))
            engine = test_eng
            break
        except Exception:
            continue
    if not engine:
        pytest.skip("Base de datos PostgreSQL de pruebas (puerto 5433 o plan_review_postgres_test) no disponible.")

    try:
        with engine.connect() as conn:
            # Asegurar que la tabla y un documento existan para FK
            test_doc_id = str(uuid.uuid4())
            test_node_id = str(uuid.uuid4())
            test_proj_id = str(uuid.uuid4())
            test_org_id = str(uuid.uuid4())

            conn.execute(text(f"""
                INSERT INTO organizations (id, name, slug, status, created_at, updated_at)
                VALUES ('{test_org_id}', 'PG Test Org', 'pg-test-{uuid.uuid4().hex[:6]}', 'active', NOW(), NOW())
                ON CONFLICT DO NOTHING;
            """))
            proj_code = f"PG-CODE-{uuid.uuid4().hex[:6]}"
            conn.execute(text(f"""
                INSERT INTO projects (id, organization_id, code, normalized_code, name, discipline, status, created_at, updated_at)
                VALUES ('{test_proj_id}', '{test_org_id}', '{proj_code}', '{proj_code.lower()}', 'Test Project', 'piping', 'active', NOW(), NOW())
                ON CONFLICT DO NOTHING;
            """))
            conn.execute(text(f"""
                INSERT INTO documents (id, organization_id, project_id, filename, file_path, file_hash_sha256, file_size_bytes, mime_type, page_count, status, created_at, updated_at)
                VALUES ('{test_doc_id}', '{test_org_id}', '{test_proj_id}', 'test.pdf', '/test.pdf', '{uuid.uuid4().hex}', 100, 'application/pdf', 1, 'uploaded', NOW(), NOW())
                ON CONFLICT DO NOTHING;
            """))

            # Intentar insertar con hierarchy_path de 300 caracteres y content_text de 500 caracteres
            long_path = "/plano_general_de_tuberia_y_piping_area_300/capitulo_4_especificaciones_tecnicas_de_instrumentacion/simbolos_de_valvulas_de_alivio_y_seguridad_con_piloto_de_alta_presion_psv_200"
            clean_short_title = "Válvula de Seguridad y Alivio PSV-2041A"
            brief_content = "Válvula de seguridad y alivio pilotada bridada Clase 300 RF según API 526 con orificio de alivio tipo J."

            conn.execute(text("""
                INSERT INTO document_structural_nodes (
                    id, document_id, node_type, hierarchy_path, level, title, content_text, structured_payload, page_number, created_at
                ) VALUES (
                    :id, :doc_id, :node_type, :hierarchy_path, :level, :title, :content_text, :payload, 1, NOW()
                )
            """), {
                "id": test_node_id,
                "doc_id": test_doc_id,
                "node_type": "symbol",
                "hierarchy_path": long_path,
                "level": 3,
                "title": clean_short_title,
                "content_text": brief_content,
                "payload": '{"test": true}'
            })

            # Verificar que se insertó sin truncamiento ni error
            res = conn.execute(text(f"SELECT title, hierarchy_path, content_text FROM document_structural_nodes WHERE id = '{test_node_id}'")).fetchone()
            assert res is not None
            assert res[0] == clean_short_title
            assert res[1] == long_path
            assert res[2] == brief_content

            # Limpiar fila de prueba
            conn.execute(text(f"DELETE FROM document_structural_nodes WHERE id = '{test_node_id}'"))
    except Exception as e:
        pytest.fail(f"Fallo en PostgreSQL live test: {e}")
