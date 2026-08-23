import pytest
import time
from app.db.models.document_memory import Document, DocumentSheet, ExtractedText
from app.db.models.operations import ProcessingJob, JobEvent, ConfidencePolicy, ReviewTask, ReviewDecision, DecisionTrace
from app.services.operations.service import OperationsService

def test_job_creation_and_lifecycle(client, db_session):
    """Verifica la creación, ejecución síncrona/asíncrona y registro de eventos de un ProcessingJob."""
    # 1. Crear proyecto y documento
    proj_res = client.post("/api/v1/projects/", json={
        "code": "PRJ-OPS-001",
        "name": "Proyecto Operaciones QA",
        "discipline": "architecture"
    })
    project_id = proj_res.json()["id"]

    doc = Document(
        project_id=project_id,
        filename="plano_ops.pdf",
        file_path="dummy_ops.pdf",
        file_hash_sha256="hash_ops_001",
        file_size_bytes=2048,
        status="ready",
        page_count=1
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)

    sheet = DocumentSheet(
        document_id=doc.id,
        sheet_number=1,
        width_px=4000,
        height_px=3000,
        dpi=150
    )
    db_session.add(sheet)
    db_session.commit()
    db_session.refresh(sheet)

    # 2. Encolar job de OCR de lámina en modo síncrono para test
    ops_svc = OperationsService(db_session)
    job = ops_svc.submit_job(
        job_type="sheet_ocr",
        target_type="sheet",
        target_id=sheet.id,
        project_id=project_id,
        async_mode=False
    )

    # 3. Verificar estado completed y eventos registrados
    assert job.status == "completed"
    assert job.progress_percent == 100
    assert job.completed_at is not None

    # Consultar eventos del job vía endpoint
    events_res = client.get(f"/api/v1/jobs/{job.id}/events")
    assert events_res.status_code == 200
    events = events_res.json()
    assert len(events) >= 2
    event_types = [e["event_type"] for e in events]
    assert "created" in event_types
    assert "completed" in event_types

def test_async_ocr_endpoint_returns_202_accepted(client, db_session):
    """Verifica que el endpoint /async responda inmediatamente con HTTP 202 Accepted y job_id."""
    # 1. Crear estructura
    proj_res = client.post("/api/v1/projects/", json={
        "code": "PRJ-ASYNC-001",
        "name": "Proyecto Async Test",
        "discipline": "architecture"
    })
    project_id = proj_res.json()["id"]

    doc = Document(
        project_id=project_id,
        filename="plano_async.pdf",
        file_path="dummy_async.pdf",
        file_hash_sha256="hash_async_001",
        file_size_bytes=2048,
        status="ready",
        page_count=1
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)

    sheet = DocumentSheet(
        document_id=doc.id,
        sheet_number=1,
        width_px=4000,
        height_px=3000,
        dpi=150
    )
    db_session.add(sheet)
    db_session.commit()
    db_session.refresh(sheet)

    # 2. Llamar al endpoint asíncrono
    res = client.post(f"/api/v1/ocr/sheets/{sheet.id}/async", json={"force_reprocess": True})
    assert res.status_code == 202
    data = res.json()
    assert "job_id" in data
    assert data["status"] == "queued"
    assert data["poll_url"] == f"/api/v1/jobs/{data['job_id']}"

    # 3. Consultar job en /jobs/{job_id}
    job_res = client.get(f"/api/v1/jobs/{data['job_id']}")
    assert job_res.status_code == 200
    assert job_res.json()["id"] == data["job_id"]

def test_confidence_policy_and_review_task_creation(client, db_session):
    """Verifica que un resultado bajo umbral genere una ReviewTask y persista DecisionTrace."""
    ops_svc = OperationsService(db_session)
    ops_svc.seed_default_policies()

    # 1. Crear lámina con texto de viñeta simulando baja confianza
    proj_res = client.post("/api/v1/projects/", json={
        "code": "PRJ-LOWCONF-001",
        "name": "Proyecto Baja Confianza",
        "discipline": "architecture"
    })
    project_id = proj_res.json()["id"]

    doc = Document(
        project_id=project_id,
        filename="plano_low.pdf",
        file_path="dummy_low.pdf",
        file_hash_sha256="hash_low_001",
        file_size_bytes=1024,
        status="ready",
        page_count=1
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)

    sheet = DocumentSheet(
        document_id=doc.id,
        sheet_number=1,
        width_px=3000,
        height_px=2000,
        dpi=150
    )
    db_session.add(sheet)
    db_session.commit()
    db_session.refresh(sheet)

    # 2. Ejecutar layout job síncrono (sin anchors suficientes generará score bajo)
    job = ops_svc.submit_job(
        job_type="sheet_layout",
        target_type="sheet",
        target_id=sheet.id,
        project_id=project_id,
        async_mode=False
    )
    assert job.status == "completed"

    # 3. Verificar que se haya creado ReviewTask en estado 'open'
    tasks_res = client.get(f"/api/v1/review-tasks?project_id={project_id}")
    assert tasks_res.status_code == 200
    tasks = tasks_res.json()
    assert len(tasks) >= 1
    task = tasks[0]
    assert task["status"] == "open"
    assert task["task_type"] == "title_block_match_review"

    # 4. Resolver tarea mediante decisión humana (corregir escala)
    dec_res = client.post(f"/api/v1/review-tasks/{task['id']}/decision", json={
        "decision": "corrected",
        "corrected_value": {"scale_text": "1:75", "sheet_code": "ARQ-101-REV"},
        "reviewer": "auditor_senior_1",
        "notes": "Escala corregida tras inspección visual humana."
    })
    assert dec_res.status_code == 200
    dec_data = dec_res.json()
    assert dec_data["decision"] == "corrected"
    assert dec_data["corrected_value"]["scale_text"] == "1:75"
    assert dec_data["reviewer"] == "auditor_senior_1"

    # 5. Verificar que la tarea quedó en estado 'corrected'
    task_after = client.get(f"/api/v1/review-tasks/{task['id']}").json()
    assert task_after["status"] == "corrected"

    # 6. Consultar trazas de decisión
    traces_res = client.get(f"/api/v1/traces/TitleBlockExtraction/{sheet.id}")
    assert traces_res.status_code == 200
    traces = traces_res.json()
    assert len(traces) >= 1
    assert any("title_block_match" in t["trace_type"] for t in traces)
