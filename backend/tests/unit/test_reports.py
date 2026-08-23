import pytest
import os
import uuid
import json
import zipfile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.db.session import Base, get_db
from app.main import app
from app.db.models.core import Project
from app.db.models.document_memory import Document, DocumentSheet, TitleBlockExtraction
from app.db.models.decision_memory import RuleDefinition, RuleFinding, FindingResolution
from app.db.models.operations import DecisionTrace
from app.services.reporting.service import ReportingService
from app.services.rules.engine import RuleRegistry
from app.core.config import settings

TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    RuleRegistry.seed_database_definitions(db)
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

def test_generate_sheet_audit_report(db_session):
    proj = Project(id=str(uuid.uuid4()), name="Torre Costanera", code="TC-01")
    db_session.add(proj)
    doc = Document(id=str(uuid.uuid4()), project_id=proj.id, filename="plano_piso_10.pdf", page_count=1)
    db_session.add(doc)
    sheet = DocumentSheet(id=str(uuid.uuid4()), document_id=doc.id, sheet_number=1, sheet_code="ARQ-10")
    db_session.add(sheet)
    
    tb = TitleBlockExtraction(
        id=str(uuid.uuid4()),
        sheet_id=sheet.id,
        sheet_code="ARQ-10",
        scale_text="1:50",
        revision="C",
        discipline="architecture"
    )
    db_session.add(tb)

    rule_def = db_session.query(RuleDefinition).first()

    finding1 = RuleFinding(
        id=str(uuid.uuid4()),
        document_id=doc.id,
        sheet_id=sheet.id,
        rule_id=rule_def.id if rule_def else None,
        rule_code="RULE_DOOR_COUNT_MATCH_V1",
        rule_name="Door Count Match",
        category="cross_reconciliation",
        severity="high",
        status="confirmed",
        title="Discrepancia de Conteo de Puertas (Delta: -2)",
        description="Se detectaron 8 puertas pero el cuadro declara 10.",
        expected_value=10,
        observed_value=8,
        delta=-2,
        recommendation="Actualizar rotulación en planta."
    )
    db_session.add(finding1)

    res = FindingResolution(
        id=str(uuid.uuid4()),
        finding_id=finding1.id,
        resolution_type="confirmed",
        resolved_by="auditor_lead",
        notes="Confirmada omisión de 2 puertas de acceso secundario"
    )
    db_session.add(res)

    trace = DecisionTrace(
        id=str(uuid.uuid4()),
        trace_type="rule_evaluation",
        entity_type="RuleExecution",
        entity_id="exec-123",
        confidence=0.95,
        decision_status="review_required",
        explanation="Evaluación de regla con delta de conteo",
        document_id=doc.id,
        sheet_id=sheet.id
    )
    db_session.add(trace)
    db_session.commit()

    svc = ReportingService(db_session)
    report = svc.generate_sheet_report(sheet_id=sheet.id, generated_by="auditor_test")

    assert report is not None
    assert report.status == "completed"
    assert report.report_scope == "sheet"
    assert report.summary["total_findings"] == 1
    assert report.summary["by_severity"]["high"] == 1
    assert report.summary["by_status"]["confirmed"] == 1
    assert report.manifest_hash is not None

    # Verificar que los archivos físicos se hayan creado
    pdf_abs = os.path.join(settings.BASE_DIR, report.artifact_pdf_path)
    json_abs = os.path.join(settings.BASE_DIR, report.artifact_json_path)
    zip_abs = os.path.join(settings.BASE_DIR, report.artifact_bundle_path)

    assert os.path.exists(pdf_abs)
    assert os.path.exists(json_abs)
    assert os.path.exists(zip_abs)

    # Verificar contenido de JSON export
    with open(json_abs, "r", encoding="utf-8") as f:
        json_data = json.load(f)
    assert json_data["metadata"]["report_id"] == report.id
    assert json_data["target"]["sheet_code"] == "ARQ-10"
    assert len(json_data["findings"]) == 1
    assert json_data["findings"][0]["rule_code"] == "RULE_DOOR_COUNT_MATCH_V1"
    assert json_data["findings"][0]["resolutions"][0]["resolved_by"] == "auditor_lead"

    # Verificar contenido del ZIP bundle
    with zipfile.ZipFile(zip_abs, "r") as zf:
        namelist = zf.namelist()
        assert any("audit-report.pdf" in n for n in namelist)
        assert any("audit-report.json" in n for n in namelist)
        assert any("manifest.json" in n for n in namelist)
        assert any("findings.json" in n for n in namelist)

def test_api_report_endpoints_and_download(client, db_session):
    proj = Project(id=str(uuid.uuid4()), name="Centro Cívico", code="CC-01")
    db_session.add(proj)
    doc = Document(id=str(uuid.uuid4()), project_id=proj.id, filename="civico.pdf", page_count=1)
    db_session.add(doc)
    sheet = DocumentSheet(id=str(uuid.uuid4()), document_id=doc.id, sheet_number=1, sheet_code="ARQ-01")
    db_session.add(sheet)
    db_session.commit()

    # 1. Generar reporte síncrono
    resp_create = client.post(f"/api/v1/reports/sheets/{sheet.id}", json={"generated_by": "qa_tester"})
    assert resp_create.status_code == 200
    report_data = resp_create.json()
    report_id = report_data["id"]

    # 2. Consultar listado y detalle
    resp_list = client.get("/api/v1/reports")
    assert resp_list.status_code == 200
    assert len(resp_list.json()) >= 1

    resp_detail = client.get(f"/api/v1/reports/{report_id}")
    assert resp_detail.status_code == 200
    assert resp_detail.json()["id"] == report_id

    # 3. Consultar manifiesto
    resp_manifest = client.get(f"/api/v1/reports/{report_id}/manifest")
    assert resp_manifest.status_code == 200
    manifest = resp_manifest.json()
    assert "files" in manifest["manifest_json"]
    assert len(manifest["manifest_json"]["files"]) >= 4

    # 4. Descargar PDF, JSON y Bundle ZIP
    resp_pdf = client.get(f"/api/v1/reports/{report_id}/download/pdf")
    assert resp_pdf.status_code == 200
    assert resp_pdf.headers["content-type"] == "application/pdf"

    resp_json = client.get(f"/api/v1/reports/{report_id}/download/json")
    assert resp_json.status_code == 200
    assert resp_json.headers["content-type"] == "application/json"

    resp_zip = client.get(f"/api/v1/reports/{report_id}/download/bundle")
    assert resp_zip.status_code == 200
    assert resp_zip.headers["content-type"] == "application/zip"

    # 5. Encolar reporte asíncrono
    resp_async = client.post(f"/api/v1/reports/sheets/{sheet.id}/async")
    assert resp_async.status_code == 202
    assert "job_id" in resp_async.json()
