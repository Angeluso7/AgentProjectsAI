import uuid
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import SessionLocal
from app.db.models.core import User, Organization, OrganizationMembership, Project
from app.db.models.decision_memory import (
    ReviewDiscipline,
    ReviewTopic,
    ReviewRun,
    ReviewRunStep,
    RuleExecution,
    RuleFinding,
    ReviewReport
)
from app.db.models.document_memory import Document
from app.db.models.completeness import DocumentDeliverable
from app.core.security import create_access_token


@pytest.fixture
def history_env():
    db: Session = SessionLocal()
    suffix = str(uuid.uuid4())[:8]

    org = Organization(id=f"org-{suffix}", name=f"Org {suffix}", slug=f"org-{suffix}")
    user = User(
        id=f"user-{suffix}",
        email=f"auditor-{suffix}@test.com",
        display_name=f"Auditor {suffix}",
        password_hash="fake",
        is_active=True
    )
    db.add(org)
    db.add(user)
    db.flush()

    membership = OrganizationMembership(
        id=f"mem-{suffix}",
        organization_id=org.id,
        user_id=user.id,
        role="admin"
    )
    db.add(membership)

    project = Project(
        id=f"proj-{suffix}",
        organization_id=org.id,
        name=f"Proyecto Historial {suffix}",
        code=f"PRJ-{suffix.upper()}",
        discipline="piping"
    )
    db.add(project)

    # Especialidad y tema
    disc = db.query(ReviewDiscipline).filter(ReviewDiscipline.code == "PIPING").first()
    if not disc:
        disc = ReviewDiscipline(id=f"disc-{suffix}", code="PIPING", name="Piping & Procesos", is_active=True)
        db.add(disc)
        db.flush()

    topic = db.query(ReviewTopic).filter(ReviewTopic.code == "PID_SYMBOLS").first()
    if not topic:
        topic = ReviewTopic(id=f"top-{suffix}", discipline_id=disc.id, code="PID_SYMBOLS", name="Simbología P&ID", is_active=True)
        db.add(topic)
        db.flush()

    # Documento de prueba
    doc = Document(
        id=f"doc-{suffix}",
        project_id=project.id,
        organization_id=org.id,
        filename="PID-001.pdf",
        status="processed"
    )
    db.add(doc)
    db.commit()

    token = create_access_token(user.id, email=user.email, extra_claims={"role": "admin", "org_id": org.id})
    client = TestClient(app)

    yield {
        "db": db,
        "org": org,
        "user": user,
        "project": project,
        "doc": doc,
        "discipline": disc,
        "topic": topic,
        "token": token,
        "client": client
    }

    db.close()


def test_review_runs_ordering_by_requested_at_desc(history_env):
    """
    FRENTE 2: Verificar que list_review_runs devuelve las corridas ordenadas estrictamente
    por requested_at descendente, incluso cuando la secuencia de inserción (created_at) es divergente.
    """
    db: Session = history_env["db"]
    client = history_env["client"]
    token = history_env["token"]
    proj = history_env["project"]
    disc = history_env["discipline"]
    topic = history_env["topic"]
    headers = {"Authorization": f"Bearer {token}"}

    base_time = datetime(2026, 10, 9, 10, 0, 0)
    # Crear 3 runs cronológicamente distintos, insertados en orden desordenado
    # Run A: requested hace 10 minutos (más reciente)
    # Run B: requested hace 30 minutos (intermedio)
    # Run C: requested hace 60 minutos (más antiguo)
    # Orden de inserción: B primero, luego A, luego C
    run_b = ReviewRun(
        id=str(uuid.uuid4()),
        project_id=proj.id,
        organization_id=proj.organization_id,
        discipline_id=disc.id,
        topic_id=topic.id,
        run_name="Run Intermedio B",
        execution_mode="sandbox",
        status="completed",
        requested_at=base_time - timedelta(minutes=30),
        created_at=base_time - timedelta(minutes=5) # created_at desalineado a propósito
    )
    db.add(run_b)
    db.commit()

    run_a = ReviewRun(
        id=str(uuid.uuid4()),
        project_id=proj.id,
        organization_id=proj.organization_id,
        discipline_id=disc.id,
        topic_id=topic.id,
        run_name="Run Reciente A",
        execution_mode="production",
        status="completed",
        requested_at=base_time - timedelta(minutes=10),
        created_at=base_time - timedelta(minutes=20) # created_at más antiguo que B
    )
    db.add(run_a)
    db.commit()

    run_c = ReviewRun(
        id=str(uuid.uuid4()),
        project_id=proj.id,
        organization_id=proj.organization_id,
        discipline_id=disc.id,
        topic_id=topic.id,
        run_name="Run Antiguo C",
        execution_mode="sandbox",
        status="completed",
        requested_at=base_time - timedelta(minutes=60),
        created_at=base_time - timedelta(minutes=1) # created_at más reciente en inserción
    )
    db.add(run_c)
    db.commit()

    # Consultar GET /api/v1/review/runs
    resp = client.get(f"/api/v1/review/runs?project_id={proj.id}", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data) == 3

    # El orden debe ser estrictamente A (reciente), B (intermedio), C (antiguo) según requested_at
    ids_returned = [r["id"] for r in data]
    assert ids_returned == [run_a.id, run_b.id, run_c.id]
    assert data[0]["run_name"] == "Run Reciente A"
    assert data[1]["run_name"] == "Run Intermedio B"
    assert data[2]["run_name"] == "Run Antiguo C"


def test_delete_individual_review_run_cascade(history_env):
    """
    FRENTE 1: Verificar que DELETE /api/v1/review/runs/{run_id} elimina la corrida
    y todas sus entidades hijas asociadas (pasos, ejecuciones, hallazgos, reportes).
    """
    db: Session = history_env["db"]
    client = history_env["client"]
    token = history_env["token"]
    proj = history_env["project"]
    disc = history_env["discipline"]
    topic = history_env["topic"]
    headers = {"Authorization": f"Bearer {token}"}

    run = ReviewRun(
        id=str(uuid.uuid4()),
        project_id=proj.id,
        organization_id=proj.organization_id,
        discipline_id=disc.id,
        topic_id=topic.id,
        run_name="Run para Borrar",
        execution_mode="sandbox",
        status="completed",
        requested_at=datetime.utcnow()
    )
    db.add(run)
    db.flush()

    step = ReviewRunStep(
        id=str(uuid.uuid4()),
        review_run_id=run.id,
        phase=1,
        phase_name="Preparación",
        step_type="preparation",
        status="succeeded"
    )
    db.add(step)

    finding = RuleFinding(
        id=str(uuid.uuid4()),
        review_run_id=run.id,
        organization_id=proj.organization_id,
        rule_code="TEST-RULE-01",
        rule_name="Test Rule",
        category="geometry_qa",
        title="Hallazgo de Prueba",
        description="Descripción de prueba"
    )
    db.add(finding)
    db.commit()

    run_id = run.id

    # Ejecutar DELETE
    del_resp = client.delete(f"/api/v1/review/runs/{run_id}", headers=headers)
    assert del_resp.status_code == 200, del_resp.text
    del_data = del_resp.json()
    assert del_data["deleted_run_id"] == run_id

    # Verificar que ya no existe en la base de datos
    assert db.query(ReviewRun).filter(ReviewRun.id == run_id).first() is None
    assert db.query(ReviewRunStep).filter(ReviewRunStep.review_run_id == run_id).first() is None
    assert db.query(RuleFinding).filter(RuleFinding.review_run_id == run_id).first() is None


def test_clear_review_runs_history(history_env):
    """
    FRENTE 1: Verificar que DELETE /api/v1/review/runs?project_id=...
    limpia en bloque el historial del proyecto.
    """
    db: Session = history_env["db"]
    client = history_env["client"]
    token = history_env["token"]
    proj = history_env["project"]
    disc = history_env["discipline"]
    topic = history_env["topic"]
    headers = {"Authorization": f"Bearer {token}"}

    # Crear 2 corridas
    for i in range(2):
        run = ReviewRun(
            id=str(uuid.uuid4()),
            project_id=proj.id,
            organization_id=proj.organization_id,
            discipline_id=disc.id,
            topic_id=topic.id,
            run_name=f"Run Lote {i}",
            execution_mode="sandbox",
            status="completed",
            requested_at=datetime.utcnow()
        )
        db.add(run)
    db.commit()

    # Limpiar historial
    resp = client.delete(f"/api/v1/review/runs?project_id={proj.id}", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["deleted_count"] >= 2

    # Verificar listado vacío
    list_resp = client.get(f"/api/v1/review/runs?project_id={proj.id}", headers=headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 0


def test_deliverable_classification_with_new_types_and_discipline(history_env):
    """
    FRENTE 3: Verificar que un documento puede clasificarse con nuevos DeliverableTypeEnum
    (pid_diagrama, isometrico_tuberias, hoja_de_datos) y con discipline_code explícito.
    """
    client = history_env["client"]
    token = history_env["token"]
    doc = history_env["doc"]
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "deliverable_type": "pid_diagrama",
        "discipline_code": "PIPING",
        "readiness_status": "eligible_as_evidence",
        "validation_notes": "Diagrama de cañerías P&ID validado por ingeniería"
    }

    resp = client.post(
        f"/api/v1/completeness/documents/{doc.id}/classify",
        json=payload,
        headers=headers
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["deliverable_type"] == "pid_diagrama"
    assert data["discipline_code"] == "PIPING"
    assert data["readiness_status"] == "eligible_as_evidence"
    assert data["validation_notes"] == "Diagrama de cañerías P&ID validado por ingeniería"
