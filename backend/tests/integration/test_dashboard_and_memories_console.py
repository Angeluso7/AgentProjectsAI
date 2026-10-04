import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import get_db
from app.db.models.core import Organization, Project
from app.db.models.document_memory import Document, DocumentSheet
from app.db.models.normative_memory import NormativeDocument, NormativeClause, NormativeCriterion
from app.db.models.template_memory import TitleBlockTemplate, SymbolLibrary, OntologyDictionary
from app.db.models.decision_memory import ReviewRun, RuleFinding, HumanFeedback


@pytest.fixture
def client(db_session: Session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_executive_dashboard_summary_returns_project_and_agent_metrics(client: TestClient, db_session: Session):
    """
    Verifica que el endpoint GET /api/v1/dashboard/executive-summary:
    1. Agrega métricas ejecutivas del proyecto activo (documentos, láminas, reglas, hallazgos, última auditoría).
    2. Monitorea la salud de los 6 motores IA y la cola de jobs en background.
    3. Genera actividades recientes, alertas recomendadas y atajos operativos.
    """
    # 1. Crear organización y proyecto de prueba
    org = Organization(
        id=str(uuid.uuid4()),
        name="Org Test Dashboard",
        slug=f"org-test-{uuid.uuid4().hex[:6]}"
    )
    db_session.add(org)
    db_session.flush()

    project = Project(
        id=str(uuid.uuid4()),
        organization_id=org.id,
        name="Hospital Regional Biobío - Pabellón Quirúrgico",
        code="HOSP-BB-01",
        client_name="Servicio de Salud",
        discipline="arquitectura/sanitaria",
        settings={"stage": "Ingeniería de Detalle"}
    )
    db_session.add(project)
    db_session.flush()

    doc = Document(
        id=str(uuid.uuid4()),
        organization_id=org.id,
        project_id=project.id,
        filename="PL-HOSP-001-ARQ.pdf",
        file_path="/storage/docs/PL-HOSP-001-ARQ.pdf",
        file_hash_sha256=uuid.uuid4().hex,
        file_size_bytes=1024000,
        mime_type="application/pdf",
        status="processed",
        page_count=2
    )
    db_session.add(doc)
    db_session.flush()

    sheet = DocumentSheet(
        id=str(uuid.uuid4()),
        document_id=doc.id,
        sheet_number=1,
        width_px=3508,
        height_px=2480,
        dpi=300,
        raster_image_path="/storage/sheets/sheet_hosp_1.png"
    )
    db_session.add(sheet)

    run = ReviewRun(
        id=str(uuid.uuid4()),
        organization_id=org.id,
        project_id=project.id,
        run_name="Auditoría Inicial Hospital",
        status="completed",
        rules_applied_count=18,
        findings_count=2,
        execution_time_sec=1.4
    )
    db_session.add(run)
    db_session.flush()

    finding = RuleFinding(
        id=str(uuid.uuid4()),
        organization_id=org.id,
        review_run_id=run.id,
        document_id=doc.id,
        sheet_id=sheet.id,
        rule_code="R-DIM-01",
        rule_name="Ancho Mínimo de Pasillo",
        category="normative_compliance",
        finding_type="dimension_non_compliance",
        severity="critical",
        status="open",
        confidence=0.96,
        title="Ancho de pasillo no reglamentario",
        description="Ancho de pasillo de emergencia inferior a 2.20 m según OGUC."
    )
    db_session.add(finding)
    db_session.commit()

    # 2. Consultar Endpoint Ejecutivo
    response = client.get(f"/api/v1/dashboard/executive-summary?project_id={project.id}")
    assert response.status_code == 200
    data = response.json()

    # 3. Validar métricas de proyecto
    p_metrics = data["project_metrics"]
    assert p_metrics["project_name"] == "Hospital Regional Biobío - Pabellón Quirúrgico"
    assert p_metrics["project_code"] == "HOSP-BB-01"
    assert p_metrics["documents_total"] >= 1
    assert p_metrics["documents_processed"] >= 1
    assert p_metrics["sheets_rasterized"] >= 1
    assert p_metrics["findings_total"] >= 1
    assert p_metrics["findings_critical"] >= 1
    assert p_metrics["last_review_run"] is not None
    assert p_metrics["last_review_run"]["run_name"] == "Auditoría Inicial Hospital"

    # 4. Validar salud del Agente IA y Motores
    agent = data["agent_health"]
    assert agent["overall_status"] == "healthy"
    assert len(agent["engines"]) == 6
    categories = [e["category"] for e in agent["engines"]]
    assert "vision" in categories
    assert "ocr" in categories
    assert "rules" in categories
    assert "llm" in categories
    assert "web" in categories
    assert "mlops" in categories

    # 5. Validar Alertas y Atajos
    assert len(data["alerts_and_recommendations"]) > 0
    assert any(a["severity"] == "critical" for a in data["alerts_and_recommendations"])
    assert len(data["quick_shortcuts"]) >= 5


def test_memories_overview_and_records_filtering(client: TestClient, db_session: Session):
    """
    Verifica que la Consola de las 4 Memorias:
    1. GET /api/v1/memories/overview retorna el resumen de las 4 memorias con métricas de salud.
    2. GET /api/v1/memories/{type}/records permite listar, filtrar por disciplina y buscar registros.
    """
    # 1. Crear registros en normative_memory y template_memory
    norm_doc = NormativeDocument(
        id=str(uuid.uuid4()),
        code="NCh-ELEC-2024",
        title="Norma Chilena de Instalaciones Eléctricas de BT",
        authority="SEC",
        discipline="eléctrica",
        version_year=2024
    )
    db_session.add(norm_doc)
    db_session.flush()

    clause = NormativeClause(
        id=str(uuid.uuid4()),
        document_id=norm_doc.id,
        clause_number="Art. 8.2.1",
        title="Canalización Subterránea de Fuerza",
        content_text="Los conductores enterrados deben protegerse en ducto de PVC pesado o acero galvanizado.",
        summary="Canalizaciones eléctricas bajo tierra."
    )
    db_session.add(clause)
    db_session.flush()

    crit = NormativeCriterion(
        id=str(uuid.uuid4()),
        clause_id=clause.id,
        criterion_code="CRIT-NCh-821-DUCT",
        name="Canalización Subterránea",
        target_entity="duct",
        property_name="duct_type",
        operator="in",
        threshold_value={"allowed": ["pvc_heavy", "galvanized_steel"]},
        severity="high"
    )
    db_session.add(crit)

    onto = OntologyDictionary(
        id=str(uuid.uuid4()),
        domain="eléctrica",
        canonical_term="ELECTRICAL_PANEL_MAIN",
        display_label="Tablero Eléctrico Principal",
        synonyms=["TG", "TABLERO GENERAL", "TDA", "MAIN PANEL"],
        description="Tablero eléctrico de distribución principal."
    )
    db_session.add(onto)
    db_session.commit()

    # 2. Endpoint Overview
    res_overview = client.get("/api/v1/memories/overview")
    assert res_overview.status_code == 200
    ov_data = res_overview.json()
    assert ov_data["total_memories_count"] == 4
    assert len(ov_data["memories"]) == 4
    types = [m["memory_type"] for m in ov_data["memories"]]
    assert "document_memory" in types
    assert "normative_memory" in types
    assert "template_memory" in types
    assert "decision_memory" in types

    # 3. Endpoint Records de normative_memory con filtro de búsqueda
    res_records = client.get("/api/v1/memories/normative_memory/records?search=Subterr&discipline=eléctrica")
    assert res_records.status_code == 200
    rec_data = res_records.json()
    assert rec_data["memory_type"] == "normative_memory"
    assert rec_data["total_count"] >= 1
    found_item = rec_data["records"][0]
    assert found_item["code_or_identifier"] == "Art. 8.2.1"
    assert found_item["discipline"] == "eléctrica"
    assert found_item["status"] == "active"


def test_memories_crud_lifecycle_transitions(client: TestClient, db_session: Session):
    """
    Prueba el ciclo de vida completo de un registro en una memoria:
    1. POST /records -> Creación manual.
    2. PATCH /records/{id} -> Edición y transición de estado (active -> obsolete).
    3. DELETE /records/{id} -> Eliminación controlada.
    """
    # 1. Crear nuevo registro en normative_memory
    create_payload = {
        "memory_type": "normative_memory",
        "code_or_identifier": "Art. 9.9.9",
        "title": "Altura Mínima de Barandas de Escalera",
        "description": "Las barandas de escaleras de uso público deberán tener una altura mínima de 0.95 m.",
        "discipline": "arquitectura",
        "category_or_nature": "high",
        "status": "active",
        "metadata_payload": {"rule_expression": "railing_height_m >= 0.95"}
    }
    create_res = client.post("/api/v1/memories/normative_memory/records", json=create_payload)
    assert create_res.status_code == 201
    created_item = create_res.json()
    record_id = created_item["id"]
    assert created_item["code_or_identifier"] == "Art. 9.9.9"
    assert created_item["status"] == "active"

    # 2. Actualizar registro (Cambiar estado a obsolete y ajustar título)
    update_payload = {
        "title": "Altura Mínima de Barandas de Escalera (Modificada 2026)",
        "status": "obsolete",
        "description": "Reemplazado por nueva exigencia de 1.05 m en edificios de uso intensivo."
    }
    patch_res = client.patch(f"/api/v1/memories/normative_memory/records/{record_id}", json=update_payload)
    assert patch_res.status_code == 200
    updated_item = patch_res.json()
    assert updated_item["status"] == "obsolete"
    assert "Modificada 2026" in updated_item["title"]

    # 3. Eliminar registro
    delete_res = client.delete(f"/api/v1/memories/normative_memory/records/{record_id}")
    assert delete_res.status_code == 200
    assert delete_res.json()["success"] is True

    # 4. Confirmar que ya no existe
    verify_res = client.get(f"/api/v1/memories/normative_memory/records?search=9.9.9")
    assert verify_res.status_code == 200
    assert verify_res.json()["total_count"] == 0


def test_cross_consistency_check_and_maintenance(client: TestClient, db_session: Session):
    """
    Prueba el diagnóstico de consistencia transversal entre las 4 memorias,
    la rutina de mantenimiento/reparación y la exportación de respaldo.
    """
    # 1. Ejecutar chequeo de consistencia
    diag_res = client.get("/api/v1/memories/cross-consistency-check")
    assert diag_res.status_code == 200
    diag_data = diag_res.json()
    assert diag_data["total_checks_run"] >= 10
    assert "consistency_health" in diag_data

    # 2. Ejecutar rutina de mantenimiento
    maint_payload = {
        "action": "full_maintenance",
        "memory_type": None
    }
    maint_res = client.post("/api/v1/memories/maintenance/run", json=maint_payload)
    assert maint_res.status_code == 200
    maint_data = maint_res.json()
    assert maint_data["status"] == "success"
    assert maint_data["action"] == "full_maintenance"

    # 3. Exportar datos de respaldo
    export_res = client.get("/api/v1/memories/export")
    assert export_res.status_code == 200
    export_data = export_res.json()
    assert "document_memory" in export_data
    assert "normative_memory" in export_data
    assert "template_memory" in export_data
    assert "decision_memory" in export_data
    assert export_data["version"] == "1.0"
