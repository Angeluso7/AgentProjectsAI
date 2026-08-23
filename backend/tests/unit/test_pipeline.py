import os
import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.db.session import Base, get_db
from app.db.models.core import Project
from app.db.models.document_memory import Document, DocumentSheet
from app.db.models.operations import ReviewPipelineRun, PipelineStageRun
from app.services.operations.pipeline_service import ReviewPipelineService
from app.main import app

TEST_DB_URL = "sqlite:///./test_pipeline.db"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    if os.path.exists("./test_pipeline.db"):
        try:
            os.remove("./test_pipeline.db")
        except Exception:
            pass

@pytest.fixture
def db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()

@pytest.fixture
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

def _create_sample_doc(db):
    org = Organization(
        id=str(uuid.uuid4()),
        name="Org Test E2E",
        slug=f"org-test-{uuid.uuid4().hex[:6]}"
    )
    db.add(org)
    
    user = User(
        id=str(uuid.uuid4()),
        email=f"tester-{uuid.uuid4().hex[:4]}@planreview.ai",
        display_name="Tester Lead",
        password_hash=hash_password("Pass123!"),
        is_superuser=True
    )
    db.add(user)
    db.commit()

    mem = OrganizationMembership(
        id=str(uuid.uuid4()),
        organization_id=org.id,
        user_id=user.id,
        role="admin",
        status="active"
    )
    db.add(mem)
    db.commit()

    project = Project(
        id=str(uuid.uuid4()),
        organization_id=org.id,
        name="Proyecto E2E Test",
        code=f"PRJ-E2E-{uuid.uuid4().hex[:4]}"
    )
    db.add(project)
    
    doc = Document(
        id=str(uuid.uuid4()),
        organization_id=org.id,
        project_id=project.id,
        filename="plano_e2e_general.pdf",
        file_path="./test_e2e.pdf",
        file_hash_sha256=f"hash-{uuid.uuid4().hex}",
        file_size_bytes=1024,
        total_pages=1,
        status="active"
    )
    db.add(doc)
    
    sheet = DocumentSheet(
        id=str(uuid.uuid4()),
        document_id=doc.id,
        sheet_number=1,
        sheet_code="ARQ-01",
        title="Planta General de Arquitectura",
        discipline="architecture",
        rendered_image_path="./data/rendered/test_sheet.png",
        width_pixels=2400,
        height_pixels=1600
    )
    db.add(sheet)
    db.commit()
    db.refresh(doc)
    db.refresh(sheet)
    return doc, sheet, user, org

def test_pipeline_document_happy_path(db):
    """Verifica la ejecución feliz del pipeline One-Click sobre un documento completo."""
    doc, sheet, user, org = _create_sample_doc(db)
    svc = ReviewPipelineService(db)

    # 1. Crear pipeline run
    pipeline_run = svc.create_pipeline_run(
        scope_type="document",
        scope_id=doc.id,
        requested_by="auditor_lead",
        force_reprocess=True,
        organization_id=org.id
    )
    assert pipeline_run.id is not None
    assert pipeline_run.status == "queued"
    assert len(pipeline_run.stages) == 8

    # 2. Ejecutar pipeline de extremo a extremo
    result = svc.execute_pipeline(pipeline_run_id=pipeline_run.id, force_reprocess=True)
    assert result.status in ["completed", "awaiting_review"]
    assert result.progress_percent == 100
    assert result.current_stage == "completed"
    assert result.final_report_id is not None

    # 3. Validar estados de cada etapa
    stages = db.query(PipelineStageRun).filter(PipelineStageRun.pipeline_run_id == result.id).order_by(PipelineStageRun.stage_order.asc()).all()
    assert len(stages) == 8
    stage_names = [s.stage_name for s in stages]
    assert stage_names == ["ingest", "ocr", "layout", "title_block", "tables", "symbols", "rules", "reports"]
    for s in stages:
        assert s.status == "completed"

def test_pipeline_idempotency_reuse(db):
    """Verifica que ejecutar dos veces sobre el mismo input reutiliza artefactos sin fallar."""
    doc, sheet, user, org = _create_sample_doc(db)
    svc = ReviewPipelineService(db)

    # Primera corrida
    run1 = svc.create_pipeline_run(scope_type="document", scope_id=doc.id, force_reprocess=True, organization_id=org.id)
    res1 = svc.execute_pipeline(run1.id, force_reprocess=True)
    assert res1.status in ["completed", "awaiting_review"]

    # Segunda corrida sin force_reprocess (Idempotencia)
    run2 = svc.create_pipeline_run(scope_type="document", scope_id=doc.id, force_reprocess=True, organization_id=org.id)
    res2 = svc.execute_pipeline(run2.id, force_reprocess=False)
    assert res2.status in ["completed", "awaiting_review"]
    assert res2.final_report_id is not None

def test_pipeline_sheet_scope(db):
    """Verifica la ejecución integral del pipeline para una lámina individual."""
    doc, sheet, user, org = _create_sample_doc(db)
    svc = ReviewPipelineService(db)

    run = svc.create_pipeline_run(scope_type="sheet", scope_id=sheet.id, force_reprocess=True, organization_id=org.id)
    res = svc.execute_pipeline(run.id, force_reprocess=True)
    assert res.status in ["completed", "awaiting_review"]
    assert res.progress_percent == 100
    assert res.final_report_id is not None

def test_pipeline_cancel_and_retry(db):
    """Verifica la cancelación y reintento del pipeline."""
    doc, sheet, user, org = _create_sample_doc(db)
    svc = ReviewPipelineService(db)

    run = svc.create_pipeline_run(scope_type="document", scope_id=doc.id, organization_id=org.id)
    cancelled = svc.cancel_pipeline(run.id)
    assert cancelled.status == "cancelled"

    retried = svc.retry_pipeline(run.id)
    assert retried.status in ["completed", "awaiting_review"]

def test_api_pipeline_endpoints(client, db):
    """Verifica los endpoints REST /api/v1/pipelines con token y header de tenant."""
    doc, sheet, user, org = _create_sample_doc(db)
    token = create_access_token(subject=user.id, email=user.email)
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org.id}

    # 1. POST /api/v1/pipelines/documents/{doc_id}/run (Async 202)
    res = client.post(f"/api/v1/pipelines/documents/{doc.id}/run", json={"force_reprocess": True}, headers=headers)
    assert res.status_code == 202
    data = res.json()
    assert "pipeline_run_id" in data
    assert data["status"] == "queued"
    p_id = data["pipeline_run_id"]

    # 2. GET /api/v1/pipelines/{id}
    res_get = client.get(f"/api/v1/pipelines/{p_id}", headers=headers)
    assert res_get.status_code == 200
    assert res_get.json()["id"] == p_id

    # 3. GET /api/v1/pipelines/{id}/stages
    res_stages = client.get(f"/api/v1/pipelines/{p_id}/stages", headers=headers)
    assert res_stages.status_code == 200
    stages = res_stages.json()
    assert len(stages) == 8

    # 4. POST /api/v1/pipelines/{id}/cancel
    res_cancel = client.post(f"/api/v1/pipelines/{p_id}/cancel", headers=headers)
    assert res_cancel.status_code == 200
    assert res_cancel.json()["status"] == "cancelled"

    # 5. POST /api/v1/pipelines/{id}/retry
    res_retry = client.post(f"/api/v1/pipelines/{p_id}/retry", headers=headers)
    assert res_retry.status_code == 200
