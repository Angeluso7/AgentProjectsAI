import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import io
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.core import Organization, User, OrganizationMembership, Project
from app.db.models.document_memory import Document, DocumentStructuralNode
from app.db.models.knowledge_base import KnowledgeItem, KnowledgeChunk
from app.core.security import hash_password, create_access_token
from app.services.document_processing.docling_service import DoclingService
from app.services.cad.dxf_service import DxfService
from app.services.knowledge.vector_store import VectorStore
from app.services.knowledge.service import KnowledgeBaseService
from app.services.assistant.service import AssistantService
from app.schemas.assistant import AssistantExecutionRequest, AssistantTaskTypeEnum
from app.schemas.knowledge_base import KnowledgeSearchQuery

def _get_test_context(client: TestClient, db_session: Session):
    org_id = str(uuid.uuid4())
    org = Organization(
        id=org_id,
        name="Piping Engineering Org",
        slug=f"piping-org-{uuid.uuid4().hex[:6]}"
    )
    db_session.add(org)

    user_id = str(uuid.uuid4())
    user = User(
        id=user_id,
        email=f"lead.piping.{uuid.uuid4().hex[:6]}@piping.com",
        display_name="Piping Lead Auditor",
        password_hash=hash_password("PasswordSeguro123!"),
        is_active=True,
        is_superuser=False
    )
    db_session.add(user)

    membership = OrganizationMembership(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        user_id=user_id,
        role="admin",
        status="active"
    )
    db_session.add(membership)

    project_id = str(uuid.uuid4())
    project = Project(
        id=project_id,
        organization_id=org_id,
        code="PRJ-PIP-PHASE1",
        name="Refinería BioBío - Unidad Hidrocraqueo",
        client_name="ENAP Refinerías",
        discipline="piping",
        status="active"
    )
    db_session.add(project)
    db_session.commit()

    token = create_access_token(
        subject=user.id,
        email=user.email,
        extra_claims={
            "org_id": org_id,
            "role": "admin"
        }
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Organization-Id": org_id
    }

    return {
        "client": client,
        "headers": headers,
        "org": org,
        "user": user,
        "project": project,
        "db": db_session
    }


def _create_dummy_dxf_with_piping_blocks() -> bytes:
    """Crea un archivo DXF válido con capas, textos y bloques de válvulas."""
    import ezdxf
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()

    # 1. Crear capas
    doc.layers.add(name="PIP-PIPE", color=1)
    doc.layers.add(name="PIP-VALV", color=3)
    doc.layers.add(name="INST-TAG", color=4)

    # 2. Crear definición de bloque de válvula
    valve_block = doc.blocks.new(name="VALVE_GATE")
    valve_block.add_line((-2, -1), (2, 1))
    valve_block.add_line((-2, 1), (2, -1))
    valve_block.add_line((-2, -1), (-2, 1))
    valve_block.add_line((2, -1), (2, 1))
    valve_block.add_attdef(tag="TAG", insert=(0, 2), height=1.0)
    valve_block.add_attdef(tag="SIZE", insert=(0, -2), height=1.0)

    # 3. Insertar bloques en modelspace con atributos
    ins1 = msp.add_blockref("VALVE_GATE", (100.0, 150.0), dxfattribs={"layer": "PIP-VALV"})
    ins1.add_attrib("TAG", "HV-101")
    ins1.add_attrib("SIZE", "4\"")

    ins2 = msp.add_blockref("VALVE_GATE", (200.0, 150.0), dxfattribs={"layer": "PIP-VALV"})
    ins2.add_attrib("TAG", "HV-102")
    ins2.add_attrib("SIZE", "6\"")

    # 4. Añadir textos técnicos
    msp.add_text("LINEA 4-CW-102-CS150", dxfattribs={"layer": "PIP-PIPE", "insert": (100.0, 170.0), "height": 3.0})
    msp.add_text("PT-101", dxfattribs={"layer": "INST-TAG", "insert": (120.0, 180.0), "height": 2.5})

    # 5. Añadir líneas de cañería
    msp.add_line((50.0, 150.0), (300.0, 150.0), dxfattribs={"layer": "PIP-PIPE"})

    out_stream = io.StringIO()
    doc.write(out_stream)
    return out_stream.getvalue().encode("utf-8")


def _create_dummy_line_schedule_csv() -> bytes:
    """Genera un archivo CSV representativo de un Line Schedule de Piping."""
    csv_content = (
        "Line Number,Fluid,Size,Piping Class,Design Press (psig),Design Temp (C),Insulation\n"
        "4-CW-101-CS150,Cooling Water,4\",CS150,150,45,None\n"
        "6-HC-202-CS300,Hydrocarbon,6\",CS300,285,180,Thermal (50mm)\n"
        "2-IA-303-SS304,Instrument Air,2\",SS304,100,30,None\n"
        "8-STM-404-CS600,High Pressure Steam,8\",CS600,600,350,Thermal (80mm)\n"
    )
    return csv_content.encode("utf-8")


# =============================================================================
# CASO 1: EXTRACCIÓN DOCLING DE TABLA (LINE SCHEDULE / SPECS)
# =============================================================================
def test_docling_table_extraction_line_schedule(client: TestClient, db_session: Session):
    """Verifica que Docling extraiga tablas con filas, columnas y representación Markdown intacta."""
    ctx = _get_test_context(client, db_session)
    doc_id = str(uuid.uuid4())
    csv_bytes = _create_dummy_line_schedule_csv()

    docling_svc = DoclingService()
    nodes = docling_svc.extract_structural_nodes(
        file_bytes=csv_bytes,
        filename="line_schedule_area100.csv",
        document_id=doc_id
    )

    assert len(nodes) >= 1
    table_node = nodes[0]
    assert table_node.node_type == "table"
    assert "Line Number" in table_node.content_text
    assert "4-CW-101-CS150" in table_node.content_text
    assert table_node.structured_payload["row_count"] == 4
    assert table_node.structured_payload["col_count"] == 7
    assert table_node.structured_payload["headers"][0] == "Line Number"


# =============================================================================
# CASO 2: EXTRACCIÓN DXF DE CAPAS, BLOQUES Y ATRIBUTOS
# =============================================================================
def test_dxf_layers_and_blocks_extraction(client: TestClient, db_session: Session):
    """Verifica que DxfService extraiga capas, bloques de válvulas con atributos y textos."""
    ctx = _get_test_context(client, db_session)
    headers = ctx["headers"]
    project_id = ctx["project"].id

    dxf_bytes = _create_dummy_dxf_with_piping_blocks()

    # 1. Cargar archivo DXF en el endpoint de upload
    upload_res = client.post(
        "/api/v1/documents/upload",
        headers=headers,
        data={"project_id": project_id},
        files={"file": ("p_and_id_area100.dxf", dxf_bytes, "application/acad")}
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    # 2. Consultar entidades CAD extraídas
    cad_res = client.get(f"/api/v1/documents/{doc_id}/cad-entities", headers=headers)
    assert cad_res.status_code == 200
    cad_data = cad_res.json()

    # Validar capas
    layer_names = [l["name"] for l in cad_data["layers"]]
    assert "PIP-PIPE" in layer_names
    assert "PIP-VALV" in layer_names
    assert "INST-TAG" in layer_names

    # Validar bloques insertados con tags
    blocks = cad_data["blocks_inserted"]
    assert len(blocks) == 2
    tags = [b["attributes"].get("TAG") for b in blocks]
    assert "HV-101" in tags
    assert "HV-102" in tags

    # Validar textos de cañería
    texts = [t["text"] for t in cad_data["texts"]]
    assert any("LINEA 4-CW-102-CS150" in t for t in texts)

    # 3. Consultar nodos estructurales generados
    struct_res = client.get(f"/api/v1/documents/{doc_id}/structural-nodes", headers=headers)
    assert struct_res.status_code == 200
    struct_nodes = struct_res.json()
    assert len(struct_nodes) >= 2
    node_types = [n["node_type"] for n in struct_nodes]
    assert "table" in node_types or "dxf_block_summary" in node_types


# =============================================================================
# CASO 3: CHUNKING ESTRUCTURAL SIN CORTE ARBITRARIO
# =============================================================================
def test_structural_chunking_integrity(client: TestClient, db_session: Session):
    """Verifica que el chunking respete secciones normativas y tablas completas."""
    ctx = _get_test_context(client, db_session)
    org_id = ctx["org"].id

    kb_svc = KnowledgeBaseService(db_session, in_memory_vector=True)

    # Crear ítem con norma extensa con cláusulas
    normative_text = (
        "## CAPÍTULO II - DISEÑO DE PRESIÓN DE CAÑERÍAS\n\n"
        "304.1 Espesor Mínimo Requerido de Tubería Recta.\n"
        "El espesor mínimo de diseño de tubería sujeta a presión interna se calculará considerando "
        "el esfuerzo admisible del material, el factor de calidad de soldadura y el factor de temperatura Y.\n\n"
        "## CAPÍTULO III - MATERIALES Y REQUISITOS DE IMPACTO\n\n"
        "323.2 Requisitos de Ensayos de Impacto Charpy V-Notch.\n"
        "Los materiales de acero al carbono grado ASTM A106 Gr.B operando bajo -29°C requieren ensayo de impacto mandatorio."
    )

    item = KnowledgeItem(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        domain="normative_knowledge",
        item_type="normative_specification",
        title="Norma ASME B31.3 - Tuberías de Proceso",
        content_text=normative_text,
        discipline="piping",
        status="validated",
        is_active_for_reuse=True,
        author="lead.auditor"
    )
    db_session.add(item)
    db_session.commit()

    chunks = kb_svc._generate_chunks_for_item(item)
    assert len(chunks) == 2
    assert chunks[0].chunk_type == "section_chunk"
    assert chunks[1].chunk_type == "section_chunk"
    assert "304.1" in chunks[0].chunk_text
    assert "323.2" in chunks[1].chunk_text
    assert "/Norma_ASME" in chunks[0].hierarchy_path or "CAP" in chunks[0].chunk_title


# =============================================================================
# CASO 4: SINCRONIZACIÓN HÍBRIDA CON FILTRO DE GOBERNANZA
# =============================================================================
def test_qdrant_hybrid_sync_governance_filter(client: TestClient, db_session: Session):
    """Verifica que Qdrant SOLO indexe ítems aprobados y excluya estrictamente borradores/inactivos."""
    ctx = _get_test_context(client, db_session)
    org_id = ctx["org"].id

    vector_store = VectorStore(in_memory=True)
    assert vector_store.is_available() is True

    # 1. Crear ítem borrador inactivo (NO debe indexarse)
    draft_item = KnowledgeItem(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        domain="rule_knowledge",
        item_type="qaqc_rule",
        title="Regla en Borrador - No Aprobada",
        content_text="Verificar espesor de cañería en borrador.",
        status="draft",
        is_active_for_reuse=False
    )
    db_session.add(draft_item)

    # 2. Crear ítem validado activo (SÍ debe indexarse)
    approved_item = KnowledgeItem(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        domain="piping_specs",
        item_type="line_specification",
        title="Especificación de Cañería Clase CS150",
        content_text="Material ASTM A106 Gr.B, Bridas ASME B16.5 Clase 150 RF, Rating máximo 285 psig.",
        status="approved_for_reuse",
        is_active_for_reuse=True
    )
    db_session.add(approved_item)
    db_session.commit()

    # Generar chunks
    chunk_draft = KnowledgeChunk(
        id=str(uuid.uuid4()),
        knowledge_item_id=draft_item.id,
        chunk_title=draft_item.title,
        chunk_text=draft_item.content_text
    )
    chunk_appr = KnowledgeChunk(
        id=str(uuid.uuid4()),
        knowledge_item_id=approved_item.id,
        chunk_title=approved_item.title,
        chunk_text=approved_item.content_text
    )
    db_session.add(chunk_draft)
    db_session.add(chunk_appr)
    db_session.commit()

    # Intentar indexar ambos
    res_draft = vector_store.upsert_approved_chunks(org_id, None, [chunk_draft], draft_item)
    res_appr = vector_store.upsert_approved_chunks(org_id, None, [chunk_appr], approved_item)

    assert res_draft is False # Rechazado por gobernanza
    assert res_appr is True   # Aprobado e indexado

    # Buscar en Qdrant
    hits = vector_store.hybrid_search(org_id, "ASTM A106 Gr.B Clase 150")
    assert len(hits) == 1
    assert hits[0]["item_id"] == approved_item.id
    assert hits[0]["title"] == "Especificación de Cañería Clase CS150"


# =============================================================================
# CASO 5: FALLBACK AUTOMÁTICO A SQL SI QDRANT FALLA
# =============================================================================
def test_qdrant_failure_sql_fallback(client: TestClient, db_session: Session):
    """Verifica que si Qdrant no está disponible, search_knowledge responda sin error vía SQL."""
    ctx = _get_test_context(client, db_session)
    org_id = ctx["org"].id

    kb_svc = KnowledgeBaseService(db_session, in_memory_vector=True)
    # Simular caída de Qdrant
    kb_svc.vector_store._is_available = False
    kb_svc.vector_store.client = None

    item = KnowledgeItem(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        domain="piping_specs",
        item_type="valve_spec",
        title="Válvulas de Retención Check ASME B16.34",
        content_text="Las válvulas check deben instalarse en posición horizontal o vertical ascendente.",
        status="approved_for_reuse",
        is_active_for_reuse=True
    )
    db_session.add(item)
    db_session.commit()
    kb_svc._generate_chunks_for_item(item)

    query = KnowledgeSearchQuery(
        query="válvulas check posición horizontal",
        active_only=True,
        top_k=3
    )

    # La búsqueda debe retornar el resultado mediante fallback SQL sin lanzar excepción
    search_resp = kb_svc.search_knowledge(org_id, query)
    assert search_resp.total_matches >= 1
    assert search_resp.results[0].item_id == item.id
    assert "Retención Check" in search_resp.results[0].title


# =============================================================================
# CASO 6: COPILOT USANDO CHUNKS ESTRUCTURADOS DE TABLAS
# =============================================================================
def test_copilot_using_structured_chunk(client: TestClient, db_session: Session):
    """Verifica que el Copilot reciba y cite chunks estructurados de tablas en su contexto RAG."""
    ctx = _get_test_context(client, db_session)
    org_id = ctx["org"].id
    project_id = ctx["project"].id

    # 1. Crear conocimiento de tabla Line Schedule
    csv_bytes = _create_dummy_line_schedule_csv()
    docling_svc = DoclingService()
    nodes = docling_svc.extract_structural_nodes(csv_bytes, "line_schedule.csv", "doc-test-123")
    table_node = nodes[0]

    item = KnowledgeItem(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        project_id=project_id,
        domain="project_knowledge",
        item_type="stage_deliverable_spec",
        title="Line Schedule - Unidad Hidrocraqueo",
        content_text=table_node.content_text,
        structured_payload=table_node.structured_payload,
        modality="table",
        discipline="piping",
        status="approved_for_reuse",
        is_active_for_reuse=True
    )
    db_session.add(item)
    db_session.commit()

    kb_svc = KnowledgeBaseService(db_session, in_memory_vector=True)
    chunks = kb_svc._generate_chunks_for_item(item)
    assert any(c.chunk_type == "table_chunk" for c in chunks)

    # 2. Ejecutar consulta asistida del Copilot
    assistant_svc = AssistantService(db_session)
    assistant_svc.kb_service = kb_svc

    req = AssistantExecutionRequest(
        task_type=AssistantTaskTypeEnum.normative_query,
        prompt="¿Cuál es la temperatura y presión de diseño de la línea 6-HC-202-CS300?",
        project_id=project_id,
        discipline="piping"
    )

    exec_res = assistant_svc.execute_task(organization_id=org_id, payload=req)
    assert exec_res.interaction_id is not None
    assert len(exec_res.retrieved_sources) >= 1
    top_rag = exec_res.retrieved_sources[0]
    assert "Line Schedule" in top_rag.title
    assert "6-HC-202-CS300" in top_rag.snippet
