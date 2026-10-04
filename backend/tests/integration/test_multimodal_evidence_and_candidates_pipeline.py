import os
import pytest
import uuid
from datetime import datetime
from fastapi.testclient import TestClient

from app.main import app
from app.db.models.core import Organization, Project
from app.db.models.document_memory import Document, DocumentSheet, DocumentStructuralNode
from app.db.models.intake_extractions import SourceExtraction, ExtractedItem, RuleDocument, SupportingKnowledgeItem
from app.db.models.knowledge_base import KnowledgeItem, KnowledgeChunk
from app.services.extraction.multimodal_evidence_service import MultimodalEvidenceService
from app.services.extraction.candidate_generator_service import CandidateGeneratorService
from app.services.knowledge.vector_store import VectorStore
from app.services.knowledge.service import KnowledgeBaseService

@pytest.fixture
def test_setup_data(db_session):
    org = Organization(
        id=str(uuid.uuid4()),
        name="Org Multimodal Test",
        slug=f"org-multi-{uuid.uuid4().hex[:6]}",
        status="active"
    )
    db_session.add(org)
    db_session.commit()

    proj = Project(
        id=str(uuid.uuid4()),
        organization_id=org.id,
        name="Proyecto Planta Procesos Multimodal",
        code=f"PRJ-MULTI-{uuid.uuid4().hex[:4].upper()}",
        discipline="piping",
        status="active"
    )
    db_session.add(proj)
    db_session.commit()

    return {"organization": org, "project": proj}

# =========================================================================
# TEST 1: CAPA 1 - EXTRACCIÓN DE EVIDENCIA MULTIMODAL (TABLAS, DXF, JERARQUÍA)
# =========================================================================
def test_layer1_multimodal_evidence_extraction(client, db_session, test_setup_data):
    org = test_setup_data["organization"]
    proj = test_setup_data["project"]

    csv_content = (
        "LINE_NUMBER,SPEC,SIZE_INCH,FLUID,DESIGN_PRESS_PSIG,DESIGN_TEMP_C\n"
        "100-P-101-4\"-A1A,A1A,4,Water,150,45\n"
        "100-P-102-6\"-A1A,A1A,6,Water,150,45\n"
        "100-S-201-2\"-B1A,B1A,2,Steam,300,180\n"
    ).encode("utf-8")

    doc = Document(
        id=str(uuid.uuid4()),
        organization_id=org.id,
        project_id=proj.id,
        filename="Line_Schedule_Area100.csv",
        file_path="/tmp/Line_Schedule_Area100.csv",
        file_hash_sha256="hash123multimodal",
        file_size_bytes=len(csv_content),
        mime_type="text/csv",
        page_count=1,
        status="ready"
    )
    db_session.add(doc)
    db_session.commit()

    evidence_svc = MultimodalEvidenceService(db_session)
    evidence_payload = evidence_svc.extract_document_evidence(
        document_id=doc.id,
        file_bytes=csv_content,
        filename=doc.filename
    )

    assert evidence_payload["document_id"] == doc.id
    assert len(evidence_payload["structural_nodes"]) >= 1
    assert len(evidence_payload["tables"]) >= 1

    tbl = evidence_payload["tables"][0]
    assert tbl["headers"] == ["LINE_NUMBER", "SPEC", "SIZE_INCH", "FLUID", "DESIGN_PRESS_PSIG", "DESIGN_TEMP_C"]
    assert tbl["row_count"] == 3
    assert evidence_payload["provenance"]["file_size_bytes"] == len(csv_content)

# =========================================================================
# TEST 2: CAPA 2 - GENERACIÓN DE LOS 7 CANDIDATOS DE INTERPRETACIÓN TÉCNICA
# =========================================================================
def test_layer2_technical_interpretation_candidates_generation(client, db_session, test_setup_data):
    org = test_setup_data["organization"]
    proj = test_setup_data["project"]

    extraction = SourceExtraction(
        id=str(uuid.uuid4()),
        organization_id=org.id,
        project_id=proj.id,
        title="Especificación de Piping y Schedules",
        document_type="manual",
        authority="ASME / Normativa Interna",
        discipline="piping",
        extraction_mode="ai_document",
        source_origin="document",
        status="extracting"
    )
    db_session.add(extraction)
    db_session.commit()

    mock_evidence = {
        "tables": [
            {
                "node_id": str(uuid.uuid4()),
                "title": "Valve Schedule Área 200",
                "headers": ["TAG", "SIZE", "RATING", "TYPE", "SPEC"],
                "rows": [
                    {"TAG": "XV-101", "SIZE": "4\"", "RATING": "150#", "TYPE": "Ball", "SPEC": "A1A"},
                    {"TAG": "PSV-201", "SIZE": "2\"", "RATING": "300#", "TYPE": "Safety", "SPEC": "B1A"}
                ],
                "page_number": 1
            }
        ],
        "structural_nodes": [
            {
                "id": str(uuid.uuid4()),
                "node_type": "dxf_block_summary",
                "title": "Bloque CAD: VALV_BALL_4IN",
                "content_text": "Bloque de válvula bola en capa PIPING_VALVES con tag XV-101.",
                "structured_payload": {"block_name": "VALV_BALL_4IN", "layer": "PIPING_VALVES", "attributes": {"TAG": "XV-101", "SIZE": "4\""}},
                "page_number": 1
            },
            {
                "id": str(uuid.uuid4()),
                "node_type": "paragraph",
                "title": "Cláusula 4.2: Espesor mínimo de cañerías",
                "content_text": "El espesor mínimo de pared deberá ser de 3.5 mm para líneas de vapor a más de 150 psig.",
                "page_number": 2
            },
            {
                "id": str(uuid.uuid4()),
                "node_type": "paragraph",
                "title": "Ejemplo de Montaje en Batería de Bombas",
                "content_text": "A modo de ejemplo ilustrativo, la disposición de válvulas de retención debe colocarse antes de la descarga.",
                "page_number": 3
            }
        ]
    }

    cand_svc = CandidateGeneratorService(db_session)
    candidates = cand_svc.generate_candidates_from_evidence(
        extraction_id=extraction.id,
        evidence_payload=mock_evidence,
        discipline="piping",
        document_title="Especificación de Piping y Schedules"
    )

    candidate_types = [c.candidate_type for c in candidates]

    # Verificar presencia de los tipos canónicos
    assert "table_matrix_candidate" in candidate_types
    assert "premise_candidate" in candidate_types
    assert "rule_candidate" in candidate_types
    assert "example_candidate" in candidate_types
    assert "symbol_candidate" in candidate_types
    assert "equipment_image_candidate" in candidate_types

    # Verificar que todos arrancan en estado 'to_confirm' y NUNCA en 'validada'
    for c in candidates:
        assert c.review_status == "to_confirm"
        assert c.validated_at is None

    # Verificar que diagram_candidate / CAD incluye el disclaimer explícito de ausencia de topología
    cad_cands = [c for c in candidates if "CAD" in (c.code_or_number or "")]
    for cc in cad_cands:
        assert cc.disclaimer_notes is not None
        assert "sin inferencia de conectividad topológica" in cc.disclaimer_notes.lower()

# =========================================================================
# TEST 3: GOBERNANZA - CANDIDATOS NO APROBADOS NO ALIMENTAN REGLAS NI RAG
# =========================================================================
def test_governance_unapproved_candidates_isolated_from_rules_and_rag(client, db_session, test_setup_data):
    org = test_setup_data["organization"]
    proj = test_setup_data["project"]

    extraction = SourceExtraction(
        id=str(uuid.uuid4()),
        organization_id=org.id,
        project_id=proj.id,
        title="Norma Preliminar Borrador",
        document_type="norma",
        discipline="piping",
        extraction_mode="ai_document",
        status="extracting"
    )
    db_session.add(extraction)
    db_session.commit()

    # Candidato 1: En 'to_confirm' (No aprobado)
    cand_unapproved = ExtractedItem(
        id=str(uuid.uuid4()),
        extraction_id=extraction.id,
        item_type="rule",
        candidate_type="rule_candidate",
        title="Regla No Validada: Presión de prueba 500 psi",
        content_text="Regla preliminar sin validación humana.",
        review_status="to_confirm",
        target_destination="rules_engine"
    )
    # Candidato 2: Rechazado
    cand_rejected = ExtractedItem(
        id=str(uuid.uuid4()),
        extraction_id=extraction.id,
        item_type="table",
        candidate_type="table_matrix_candidate",
        title="Tabla Descartada",
        content_text="Datos erróneos.",
        review_status="rejected",
        target_destination="both"
    )
    # Candidato 3: Validado formalmente
    cand_approved = ExtractedItem(
        id=str(uuid.uuid4()),
        extraction_id=extraction.id,
        item_type="rule",
        candidate_type="rule_candidate",
        title="Regla Aprobada: Espesor Mínimo Cañería 4mm",
        content_text="Requisito validado por auditor líder.",
        review_status="validada",
        target_destination="rules_engine"
    )
    db_session.add_all([cand_unapproved, cand_rejected, cand_approved])
    db_session.commit()

    # Realizar commit selectivo SOLO para el candidato aprobado
    from app.db.repositories.intake_extraction_repository import IntakeExtractionRepository
    repo = IntakeExtractionRepository(db_session)
    res = repo.commit_extraction_to_rules(
        extraction_id=extraction.id,
        approved_item_ids=[cand_approved.id],
        target_rule_document_title="Norma Aprobada de Piping"
    )

    assert res["rules_incorporated_count"] == 1

    # Verificar que solo cand_approved existe en RuleDocumentItem
    rule_doc_items = db_session.query(RuleDocument).first().items
    assert len(rule_doc_items) == 1
    assert rule_doc_items[0].title == "Regla Aprobada: Espesor Mínimo Cañería 4mm"

    # Verificar que los candidatos no aprobados NO están en RuleDocumentItem
    item_titles = [r.title for r in rule_doc_items]
    assert "Regla No Validada: Presión de prueba 500 psi" not in item_titles
    assert "Tabla Descartada" not in item_titles

# =========================================================================
# TEST 4: PAYLOAD INDEXES EN QDRANT Y BÚSQUEDA VECTORIAL AISLADA
# =========================================================================
def test_qdrant_payload_indexes_and_governance_filtering(db_session, test_setup_data):
    org = test_setup_data["organization"]
    proj = test_setup_data["project"]

    vector_store = VectorStore(in_memory=True)
    assert vector_store.is_available() is True

    # Item A: Aprobado y activo
    item_approved = KnowledgeItem(
        id=str(uuid.uuid4()),
        organization_id=org.id,
        project_id=proj.id,
        domain="normative_knowledge",
        item_type="rule_candidate",
        title="Especificación Aprobada ASME B31.3",
        content_text="Criterios mandatorios para cañerías de proceso químico y vapor.",
        status="validated",
        is_active_for_reuse=True,
        confidence_score=1.0,
        version_number=1,
        author="lead_auditor",
        origin_type="auto_extraction",
        discipline="piping"
    )
    chunk_approved = KnowledgeChunk(
        id=str(uuid.uuid4()),
        knowledge_item_id=item_approved.id,
        chunk_index=0,
        chunk_title="ASME B31.3 - Espesores",
        chunk_type="section_chunk",
        chunk_text="Espesores de pared según presión de diseño para ASME B31.3."
    )

    # Item B: Borrador / Inactivo (No debe indexarse)
    item_draft = KnowledgeItem(
        id=str(uuid.uuid4()),
        organization_id=org.id,
        project_id=proj.id,
        domain="normative_knowledge",
        item_type="premise_candidate",
        title="Borrador no validado",
        content_text="Texto no revisado.",
        status="draft",
        is_active_for_reuse=False
    )
    chunk_draft = KnowledgeChunk(
        id=str(uuid.uuid4()),
        knowledge_item_id=item_draft.id,
        chunk_index=0,
        chunk_text="Texto no validado para RAG."
    )

    # Intentar indexar ambos
    ok_approved = vector_store.upsert_approved_chunks(
        organization_id=org.id,
        project_id=proj.id,
        chunks=[chunk_approved],
        item=item_approved
    )
    ok_draft = vector_store.upsert_approved_chunks(
        organization_id=org.id,
        project_id=proj.id,
        chunks=[chunk_draft],
        item=item_draft
    )

    assert ok_approved is True
    assert ok_draft is False # Rechazado por gobernanza

    # Búsqueda vectorial
    results = vector_store.hybrid_search(
        organization_id=org.id,
        query_text="ASME B31.3 espesores",
        project_id=proj.id,
        top_k=5
    )
    assert len(results) >= 1
    assert any(r["chunk_id"] == chunk_approved.id for r in results)
    assert not any(r["chunk_id"] == chunk_draft.id for r in results)

# =========================================================================
# TEST 5: API ENDPOINTS - CONSULTA DE CANDIDATOS Y METADATOS MULTIMODALES
# =========================================================================
def test_api_candidates_query_and_update(client, db_session, test_setup_data):
    org = test_setup_data["organization"]
    proj = test_setup_data["project"]

    # 1. Crear sesión de extracción con IA
    process_res = client.post("/api/v1/intake/extractions/process-with-ai", json={
        "title": "Manual Técnico de Válvulas y Cañerías",
        "document_type": "manual",
        "authority": "Norma Sectorial",
        "discipline": "piping",
        "extraction_mode": "ai_document",
        "project_id": proj.id
    })
    assert process_res.status_code == 201
    extraction_data = process_res.json()
    ext_id = extraction_data["id"]

    # 2. Consultar candidatos vía endpoint Capa 2
    cands_res = client.get(f"/api/v1/intake/extractions/{ext_id}/candidates")
    assert cands_res.status_code == 200
    cands_list = cands_res.json()
    assert len(cands_list) >= 5

    # 3. Filtrar candidatos por candidate_type
    tbl_res = client.get(f"/api/v1/intake/extractions/{ext_id}/candidates?candidate_type=table_matrix_candidate")
    assert tbl_res.status_code == 200
    tbl_list = tbl_res.json()
    assert len(tbl_list) >= 1
    assert tbl_list[0]["candidate_type"] == "table_matrix_candidate"
    assert "structured_matrix" in tbl_list[0]

    # 4. Actualizar estado de revisión de un candidato
    cand_id = tbl_list[0]["id"]
    update_res = client.put(f"/api/v1/intake/extractions/{ext_id}/items/{cand_id}", json={
        "review_status": "validada",
        "governance_note": "Aprobada por auditor técnico"
    })
    assert update_res.status_code == 200
    assert update_res.json()["review_status"] == "validada"

# =========================================================================
# TEST 6: PUNTO 3 - PROMOCIÓN ATÓMICA CANDIDATO -> REGLA / CONOCIMIENTO
# =========================================================================
def test_atomic_candidate_promotion_to_rule_and_knowledge(client, db_session, test_setup_data):
    """PUNTO 3: Promoción atómica gobernada de candidatos 'validada' a RuleDocument y KnowledgeBase."""
    from app.db.repositories.intake_extraction_repository import IntakeExtractionRepository
    from app.schemas.intake_extractions import ExtractionCommitRequest
    from app.db.models.intake_extractions import RuleDocumentItem
    
    org = test_setup_data["organization"]
    proj = test_setup_data["project"]

    repo = IntakeExtractionRepository(db_session)
    extraction = SourceExtraction(
        id=str(uuid.uuid4()),
        organization_id=org.id,
        project_id=proj.id,
        title="Norma Atómica de Piping ASME B31.3",
        document_type="standard",
        authority="ASME",
        discipline="piping",
        extraction_mode="ai_document",
        status="extracting"
    )
    db_session.add(extraction)
    db_session.commit()

    # Crear 3 candidatos: 2 validados, 1 en to_confirm
    c1 = ExtractedItem(
        id=str(uuid.uuid4()),
        extraction_id=extraction.id,
        item_type="rule_candidate",
        candidate_type="normative_clause_candidate",
        title="Regla Aprobada 1: Espesores Mínimos",
        code_or_number="PIPE-ATM-01",
        description="Espesor mínimo = 4.5mm",
        content_text="Espesor mínimo = 4.5mm",
        review_status="validada",
        page_number=12,
        bbox_normalized=[0.1, 0.2, 0.5, 0.4]
    )
    c2 = ExtractedItem(
        id=str(uuid.uuid4()),
        extraction_id=extraction.id,
        item_type="premise_candidate",
        candidate_type="technical_matrix_candidate",
        title="Premisa Aprobada 2: Conexiones Bridadas",
        code_or_number="PIPE-ATM-02",
        description="Rating ANSI 300# obligatorio en vapor",
        content_text="Rating ANSI 300# obligatorio en vapor",
        review_status="validada",
        page_number=15,
        bbox_normalized=[0.2, 0.3, 0.8, 0.6]
    )
    c3_draft = ExtractedItem(
        id=str(uuid.uuid4()),
        extraction_id=extraction.id,
        item_type="rule_candidate",
        candidate_type="exception_condition_candidate",
        title="Candidato No Validado",
        code_or_number="PIPE-ATM-03",
        description="Texto no aprobado",
        content_text="Texto no aprobado",
        review_status="to_confirm",
        page_number=20,
        bbox_normalized=[0.0, 0.0, 1.0, 1.0]
    )
    db_session.add_all([c1, c2, c3_draft])
    db_session.commit()

    # Promoción atómica
    res = repo.commit_extraction_to_rules(
        extraction_id=extraction.id,
        approved_item_ids=[c1.id, c2.id],
        target_rule_document_title="Normativa Oficial Promovida ASME B31.3",
        target_rule_document_description="Promoción formal auditada y aprobada"
    )

    assert res["extraction_id"] == extraction.id
    assert res["rules_incorporated_count"] == 2
    assert res["rule_document_id"] is not None

    # Verificar en SQL que el RuleDocument y los RuleDocumentItem fueron creados
    rule_doc = db_session.query(RuleDocument).filter_by(id=res["rule_document_id"]).first()
    assert rule_doc is not None
    assert rule_doc.organization_id == org.id

    rule_items = db_session.query(RuleDocumentItem).filter_by(rule_document_id=rule_doc.id).all()
    assert len(rule_items) == 2

    # Verificar que el candidato no validado (c3_draft) NO fue promovido
    promoted_codes = [i.code_or_number for i in rule_items]
    assert "PIPE-ATM-01" in promoted_codes
    assert "PIPE-ATM-02" in promoted_codes
    assert "PIPE-ATM-03" not in promoted_codes

# =========================================================================
# TEST 7: PUNTOS 4 & 8 - DESINDEXACIÓN Y EXCLUSIÓN DE ESTADOS NO APROBADOS
# =========================================================================
def test_vector_store_deindex_and_invalidation_lifecycle(db_session, test_setup_data):
    """PUNTOS 4 & 8: Desindexación inmediata en Qdrant al rechazar, archivar o marcar superseded."""
    org = test_setup_data["organization"]
    proj = test_setup_data["project"]

    vector_store = VectorStore(in_memory=True)
    kb_service = KnowledgeBaseService(db_session, vector_store=vector_store)

    # 1. Crear item activo y validado
    item = KnowledgeItem(
        id=str(uuid.uuid4()),
        organization_id=org.id,
        project_id=proj.id,
        domain="normative_knowledge",
        item_type="rule_candidate",
        title="Regla Activa: Soldadura en Piping",
        content_text="Procedimientos de soldadura GTAW calificados bajo ASME Sec IX.",
        status="validated",
        is_active_for_reuse=True,
        confidence_score=1.0,
        version_number=1,
        author="welding_specialist",
        origin_type="manual_expert",
        discipline="piping"
    )
    chunk = KnowledgeChunk(
        id=str(uuid.uuid4()),
        knowledge_item_id=item.id,
        chunk_index=0,
        chunk_title="ASME Sec IX - GTAW",
        chunk_type="section_chunk",
        chunk_text="Procedimientos de soldadura GTAW calificados bajo ASME Sec IX.",
        metadata_payload={"is_active_for_reuse": True}
    )
    db_session.add_all([item, chunk])
    db_session.commit()

    # Indexar en Qdrant
    vector_store.upsert_approved_chunks(
        organization_id=org.id,
        project_id=proj.id,
        chunks=[chunk],
        item=item
    )

    # Validar que es recuperable mientras está 'validated'
    search_res = vector_store.hybrid_search(
        organization_id=org.id,
        query_text="soldadura GTAW ASME Sec IX",
        project_id=proj.id
    )
    assert len(search_res) == 1
    assert search_res[0]["chunk_id"] == chunk.id

    # 2. Transición de estado a 'archived' -> Debe desindexarse de Qdrant inmediatamente
    kb_service.transition_status(item.id, org.id, "archived", author="governance_board")
    search_after_archive = vector_store.hybrid_search(
        organization_id=org.id,
        query_text="soldadura GTAW ASME Sec IX",
        project_id=proj.id
    )
    assert len(search_after_archive) == 0

    # 3. Transición a 'validated' nuevamente -> Se reindexa
    kb_service.transition_status(item.id, org.id, "validated", author="governance_board")
    search_after_reactivate = vector_store.hybrid_search(
        organization_id=org.id,
        query_text="soldadura GTAW ASME Sec IX",
        project_id=proj.id
    )
    assert len(search_after_reactivate) == 1

    # 4. Transición a 'withdrawn' -> Se desindexa
    kb_service.transition_status(item.id, org.id, "withdrawn", author="governance_board")
    search_after_withdrawn = vector_store.hybrid_search(
        organization_id=org.id,
        query_text="soldadura GTAW ASME Sec IX",
        project_id=proj.id
    )
    assert len(search_after_withdrawn) == 0

    # 5. Comprobar que estados superseded, draft, rejected, inactive nunca son recuperados en consultas activas
    for invalid_status in ["superseded", "draft", "rejected", "inactive"]:
        db_session.query(KnowledgeItem).filter_by(id=item.id).update({
            "status": invalid_status,
            "is_active_for_reuse": False
        })
        db_session.commit()
        
        items, count = kb_service.list_items(
            organization_id=org.id,
            project_id=proj.id,
            search="soldadura GTAW",
            active_only=True
        )
        assert count == 0

# =========================================================================
# TEST 8: PUNTO 5 - MANEJO DE ESTADO DE SINCRONIZACIÓN Y RESILIENCIA VECTORIAL
# =========================================================================
def test_vector_sync_status_and_resilience_on_failure(db_session, test_setup_data):
    """PUNTO 5: Resiliencia ante fallos en Qdrant y registro de estado de sincronización."""
    org = test_setup_data["organization"]
    proj = test_setup_data["project"]

    # Simular VectorStore fallido
    class BrokenVectorStore(VectorStore):
        def is_available(self):
            return False
        def upsert_approved_chunks(self, *args, **kwargs):
            return False
        def delete_item_vectors(self, *args, **kwargs):
            return False

    broken_vector_store = BrokenVectorStore(in_memory=True)
    kb_service = KnowledgeBaseService(db_session, vector_store=broken_vector_store)

    item = KnowledgeItem(
        id=str(uuid.uuid4()),
        organization_id=org.id,
        project_id=proj.id,
        domain="normative_knowledge",
        item_type="rule_candidate",
        title="Regla de Aislamiento Térmico",
        content_text="Aislamiento obligatorio en líneas de vapor > 60°C.",
        status="draft",
        is_active_for_reuse=False,
        confidence_score=1.0,
        version_number=1,
        author="thermal_specialist",
        discipline="piping"
    )
    chunk = KnowledgeChunk(
        id=str(uuid.uuid4()),
        knowledge_item_id=item.id,
        chunk_index=0,
        chunk_text="Aislamiento obligatorio en líneas de vapor > 60°C."
    )
    db_session.add_all([item, chunk])
    db_session.commit()

    # Transición a 'validated' con Qdrant con fallo: la transacción SQL no debe romperse
    res = kb_service.transition_status(item.id, org.id, "validated", author="lead_auditor")
    assert res is not None
    assert res.status == "validated"
    assert res.is_active_for_reuse is True
    # Estado de sincronización debe registrar que el vector store falló
    assert res.structured_payload.get("qdrant_sync_status") in ["failed", "vector_store_unavailable"]

    # Eliminar con Qdrant caído: SQL debe tener éxito
    del_res = kb_service.delete_item(item.id, org.id)
    assert del_res is True

# =========================================================================
# TEST 9: PUNTO 6 - FILTRADO MULTIDISCIPLINARIO
# =========================================================================
def test_multidisciplinary_search_filtering(db_session, test_setup_data):
    """PUNTO 6: Búsqueda y filtrado multidisciplinario con primary_discipline y secondary_disciplines."""
    org = test_setup_data["organization"]
    proj = test_setup_data["project"]

    vector_store = VectorStore(in_memory=True)

    # Item 1: Piping primario
    item_piping = KnowledgeItem(
        id=str(uuid.uuid4()),
        organization_id=org.id,
        project_id=proj.id,
        domain="normative_knowledge",
        item_type="rule_candidate",
        title="Regla Piping: Soportes de Cañerías",
        content_text="Espaciamiento máximo entre soportes según diámetro.",
        status="validated",
        is_active_for_reuse=True,
        confidence_score=1.0,
        version_number=1,
        author="piping_eng",
        discipline="piping"
    )
    chunk_piping = KnowledgeChunk(
        id=str(uuid.uuid4()),
        knowledge_item_id=item_piping.id,
        chunk_index=0,
        chunk_title="Soportes Piping",
        chunk_type="section_chunk",
        chunk_text="Espaciamiento máximo entre soportes según diámetro.",
        metadata_payload={"discipline": "piping", "is_active_for_reuse": True}
    )

    # Item 2: Mecánica (secundaria para piping)
    item_mecanica = KnowledgeItem(
        id=str(uuid.uuid4()),
        organization_id=org.id,
        project_id=proj.id,
        domain="normative_knowledge",
        item_type="rule_candidate",
        title="Regla Mecánica: Esfuerzos en Bridas de Bomba",
        content_text="Límites de carga en boquillas de bombas centrífugas API 610.",
        status="validated",
        is_active_for_reuse=True,
        confidence_score=1.0,
        version_number=1,
        author="mech_eng",
        discipline="mecanica"
    )
    chunk_mecanica = KnowledgeChunk(
        id=str(uuid.uuid4()),
        knowledge_item_id=item_mecanica.id,
        chunk_index=0,
        chunk_title="Esfuerzos Mecánicos",
        chunk_type="section_chunk",
        chunk_text="Límites de carga en boquillas de bombas centrífugas API 610.",
        metadata_payload={"discipline": "mecanica", "is_active_for_reuse": True}
    )

    # Item 3: Eléctrica (disciplina no consultada)
    item_electrica = KnowledgeItem(
        id=str(uuid.uuid4()),
        organization_id=org.id,
        project_id=proj.id,
        domain="normative_knowledge",
        item_type="rule_candidate",
        title="Regla Eléctrica: Puesta a Tierra de Bandejas",
        content_text="Continuidad de tierra en bandejas portacables.",
        status="validated",
        is_active_for_reuse=True,
        confidence_score=1.0,
        version_number=1,
        author="elec_eng",
        discipline="electrica"
    )
    chunk_electrica = KnowledgeChunk(
        id=str(uuid.uuid4()),
        knowledge_item_id=item_electrica.id,
        chunk_index=0,
        chunk_title="Puesta a Tierra",
        chunk_type="section_chunk",
        chunk_text="Continuidad de tierra en bandejas portacables.",
        metadata_payload={"discipline": "electrica", "is_active_for_reuse": True}
    )

    db_session.add_all([item_piping, chunk_piping, item_mecanica, chunk_mecanica, item_electrica, chunk_electrica])
    db_session.commit()

    # Indexar los 3 items en el vector store
    vector_store.upsert_approved_chunks(organization_id=org.id, project_id=proj.id, chunks=[chunk_piping], item=item_piping)
    vector_store.upsert_approved_chunks(organization_id=org.id, project_id=proj.id, chunks=[chunk_mecanica], item=item_mecanica)
    vector_store.upsert_approved_chunks(organization_id=org.id, project_id=proj.id, chunks=[chunk_electrica], item=item_electrica)

    # Búsqueda multidisciplinaria: primary=piping, secondary=[mecanica]
    multi_search = vector_store.hybrid_search(
        organization_id=org.id,
        query_text="criterios y limites de carga",
        project_id=proj.id,
        discipline="piping",
        secondary_disciplines=["mecanica"],
        top_k=10
    )

    returned_titles = [it.get("chunk_title") or it.get("payload", {}).get("title") for it in multi_search]
    assert any("Soportes" in t for t in returned_titles)
    assert any("Mecánicos" in t for t in returned_titles)
    assert not any("Puesta a Tierra" in t for t in returned_titles)

# =========================================================================
# TEST 10: PUNTO 7 - PRESERVACIÓN DE PROCEDENCIA Y REFERENCIAS EN CANDIDATOS
# =========================================================================
def test_candidate_provenance_and_navigation_metadata(db_session, test_setup_data):
    """PUNTO 7: Evidencia de que cada candidato conserva document_id, página/lámina, bbox, hash SHA-256."""
    org = test_setup_data["organization"]
    proj = test_setup_data["project"]

    generator = CandidateGeneratorService(db_session)

    test_evidence = {
        "document_id": "doc-prov-uuid-12345",
        "provenance": {
            "file_hash_sha256": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
            "filename": "Spec_Piping_Area200.pdf",
            "file_size_bytes": 2048576,
            "mime_type": "application/pdf"
        },
        "tables": [{
            "table_id": "tbl-01",
            "page_number": 4,
            "headers": ["ITEM", "SERVICE", "PIPE_SPEC", "RATING"],
            "rows": [["1", "High Pressure Steam", "A106-B", "600#"]],
            "row_count": 1,
            "column_count": 4,
            "bbox": [50, 100, 500, 300],
            "bbox_normalized": [0.05, 0.1, 0.5, 0.3]
        }],
        "clauses": [{
            "clause_id": "cls-01",
            "page_number": 6,
            "clause_code": "CLAUSE-3.2",
            "title": "Criterio de Temperatura de Operación",
            "body": "La temperatura máxima de operación no debe exceder 400°C.",
            "exceptions": ["Excepto en líneas con jacket de enfriamiento activo."],
            "notes": ["Verificar con termocuplas tipo K."],
            "cross_references": ["P&ID Area 200", "Hoja de Datos HD-201"],
            "bbox": [100, 200, 600, 400],
            "bbox_normalized": [0.1, 0.2, 0.6, 0.4]
        }],
        "visual_elements": [{
            "element_id": "vis-01",
            "page_number": 8,
            "element_type": "picture",
            "caption": "Detalle de Sello Mecánico",
            "bbox": [200, 300, 700, 600],
            "bbox_normalized": [0.2, 0.3, 0.7, 0.6]
        }],
        "cad_entities": [{
            "entity_id": "cad-01",
            "layer": "PIPING_SPEC",
            "entity_type": "LINE",
            "raw_properties": {"length": 12.5, "spec": "A1A"}
        }]
    }

    extraction = SourceExtraction(
        id=str(uuid.uuid4()),
        organization_id=org.id,
        project_id=proj.id,
        title="Spec Piping Area 200",
        document_type="standard",
        authority="ASME",
        discipline="piping",
        extraction_mode="ai_document",
        status="extracting"
    )
    db_session.add(extraction)
    db_session.commit()

    candidates = generator.generate_candidates_from_evidence(
        extraction_id=extraction.id,
        evidence_payload=test_evidence,
        discipline="piping"
    )

    assert len(candidates) >= 4

    for cand in candidates:
        # Aserción obligatoria Punto 7
        assert cand.metadata_payload.get("document_id") == "doc-prov-uuid-12345"
        assert cand.metadata_payload.get("file_hash_sha256") == "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
        assert cand.review_status == "to_confirm"
        assert cand.metadata_payload.get("topological_connectivity_inferred") is False
        assert "sin inferencia" in (cand.disclaimer_notes or "") or "topológica" in cand.metadata_payload.get("disclaimer_topology_unverified", "")
        assert cand.page_number is not None
        assert cand.bbox_normalized is not None
        assert isinstance(cand.evidence_references, list)
        assert len(cand.evidence_references) >= 0

