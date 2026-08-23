import os
import uuid
from datetime import datetime, timedelta
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.db.session import Base, get_db
from app.db.models.core import Organization, User, OrganizationMembership, Project
from app.db.models.document_memory import Document, DocumentSheet
from app.db.models.reporting import AuditReport
from app.db.models.operations import ReviewPipelineRun
from app.core.security import hash_password, verify_password, create_access_token
from app.services.operations.pipeline_service import ReviewPipelineService
from app.main import app

TEST_DB_URL = "sqlite:///./test_auth_rbac.db"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    if os.path.exists("./test_auth_rbac.db"):
        try:
            os.remove("./test_auth_rbac.db")
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

def _create_tenant_fixtures(db):
    """Crea dos organizaciones con usuarios y proyectos separados para pruebas multi-tenant y RBAC."""
    # 1. Organización Alpha
    org_a = Organization(
        id=str(uuid.uuid4()),
        name="Constructora Alpha",
        slug=f"org-alpha-{uuid.uuid4().hex[:6]}"
    )
    db.add(org_a)

    # 2. Organización Beta
    org_b = Organization(
        id=str(uuid.uuid4()),
        name="Ingeniería Beta",
        slug=f"org-beta-{uuid.uuid4().hex[:6]}"
    )
    db.add(org_b)
    db.commit()

    # 3. Usuarios en Org Alpha
    users = {}
    for role in ["admin", "audit_lead", "reviewer", "contributor", "viewer"]:
        u = User(
            id=str(uuid.uuid4()),
            email=f"{role}@alpha.com",
            display_name=f"User {role.capitalize()}",
            password_hash=hash_password("Password123!"),
            is_active=True
        )
        db.add(u)
        db.commit()
        
        mem = OrganizationMembership(
            id=str(uuid.uuid4()),
            organization_id=org_a.id,
            user_id=u.id,
            role=role,
            status="active"
        )
        db.add(mem)
        db.commit()
        users[role] = u

    # 4. Usuario en Org Beta (Admin Beta)
    user_beta = User(
        id=str(uuid.uuid4()),
        email="admin@beta.com",
        display_name="Admin Beta",
        password_hash=hash_password("Password123!"),
        is_active=True
    )
    db.add(user_beta)
    db.commit()
    mem_beta = OrganizationMembership(
        id=str(uuid.uuid4()),
        organization_id=org_b.id,
        user_id=user_beta.id,
        role="admin",
        status="active"
    )
    db.add(mem_beta)
    db.commit()
    users["beta_admin"] = user_beta

    # 5. Proyecto y Documento en Org Alpha
    proj_a = Project(
        id=str(uuid.uuid4()),
        organization_id=org_a.id,
        code=f"PRJ-A-{uuid.uuid4().hex[:4]}",
        name="Proyecto Alpha Torre 1"
    )
    db.add(proj_a)
    db.commit()

    doc_a = Document(
        id=str(uuid.uuid4()),
        organization_id=org_a.id,
        project_id=proj_a.id,
        filename="plano_alpha.pdf",
        file_path="./plano_alpha.pdf",
        file_hash_sha256=f"sha256-{uuid.uuid4().hex}",
        file_size_bytes=1024,
        total_pages=1
    )
    db.add(doc_a)
    
    sheet_a = DocumentSheet(
        id=str(uuid.uuid4()),
        document_id=doc_a.id,
        sheet_number=1,
        sheet_code="A-01",
        rendered_image_path="./data/rendered/test.png",
        width_pixels=2000,
        height_pixels=1500
    )
    db.add(sheet_a)
    db.commit()

    # 6. Proyecto y Documento en Org Beta
    proj_b = Project(
        id=str(uuid.uuid4()),
        organization_id=org_b.id,
        code=f"PRJ-B-{uuid.uuid4().hex[:4]}",
        name="Proyecto Beta Galpón"
    )
    db.add(proj_b)
    db.commit()

    doc_b = Document(
        id=str(uuid.uuid4()),
        organization_id=org_b.id,
        project_id=proj_b.id,
        filename="plano_beta.pdf",
        file_path="./plano_beta.pdf",
        file_hash_sha256=f"sha256-{uuid.uuid4().hex}",
        file_size_bytes=2048,
        total_pages=1
    )
    db.add(doc_b)
    db.commit()

    return {
        "org_a": org_a,
        "org_b": org_b,
        "users": users,
        "proj_a": proj_a,
        "doc_a": doc_a,
        "sheet_a": sheet_a,
        "proj_b": proj_b,
        "doc_b": doc_b
    }

def test_password_hashing_and_verification():
    """Verifica que el hashing de contraseñas sea seguro y resistente."""
    pwd = "MiContraseñaSuperSegura2026!"
    hashed = hash_password(pwd)
    assert hashed.startswith("$pbkdf2-sha256$") or hashed.startswith("$argon2id$")
    
    is_valid, _ = verify_password(pwd, hashed)
    assert is_valid is True

    is_invalid, _ = verify_password("PasswordErronea", hashed)
    assert is_invalid is False

def test_auth_jwt_login_and_me(client, db):
    """Verifica login, generación de access token corto y consulta de perfil /me."""
    fixtures = _create_tenant_fixtures(db)
    
    # 1. Login exitoso
    res = client.post("/api/v1/auth/login", json={
        "email": "admin@alpha.com",
        "password": "Password123!"
    })
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["active_role"] == "admin"
    assert data["active_organization_id"] == fixtures["org_a"].id
    token = data["access_token"]

    # 2. Login con password errónea -> 401
    res_err = client.post("/api/v1/auth/login", json={
        "email": "admin@alpha.com",
        "password": "MalPassword"
    })
    assert res_err.status_code == 401

    # 3. GET /auth/me con token válido
    res_me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res_me.status_code == 200
    assert res_me.json()["user"]["email"] == "admin@alpha.com"
    assert len(res_me.json()["memberships"]) >= 1

    # 4. GET /auth/me sin token -> 401
    res_unauth = client.get("/api/v1/auth/me")
    assert res_unauth.status_code == 401

def test_x_organization_header_validation(client, db):
    """Verifica que X-Organization-Id se valide estrictamente contra membresías activas."""
    fixtures = _create_tenant_fixtures(db)
    user_alpha = fixtures["users"]["admin"]
    token = create_access_token(subject=user_alpha.id, email=user_alpha.email)

    # 1. Solicitar organización legítima (Org Alpha) -> 200
    res = client.get(
        "/api/v1/organizations/current",
        headers={"Authorization": f"Bearer {token}", "X-Organization-Id": fixtures["org_a"].id}
    )
    assert res.status_code == 200
    assert res.json()["id"] == fixtures["org_a"].id

    # 2. Solicitar organización ilegítima donde no es miembro (Org Beta) -> 403 Forbidden
    res_forbidden = client.get(
        "/api/v1/organizations/current",
        headers={"Authorization": f"Bearer {token}", "X-Organization-Id": fixtures["org_b"].id}
    )
    assert res_forbidden.status_code == 403

def test_rbac_permissions_matrix(client, db):
    """Verifica la matriz de permisos RBAC para viewer, contributor, reviewer y admin."""
    fixtures = _create_tenant_fixtures(db)
    doc_a = fixtures["doc_a"]

    # 1. Viewer intentando lanzar pipeline -> 403 Forbidden
    token_viewer = create_access_token(
        subject=fixtures["users"]["viewer"].id,
        email=fixtures["users"]["viewer"].email
    )
    res_v = client.post(
        f"/api/v1/pipelines/documents/{doc_a.id}/run",
        headers={"Authorization": f"Bearer {token_viewer}", "X-Organization-Id": fixtures["org_a"].id},
        json={"force_reprocess": True}
    )
    assert res_v.status_code == 403

    # 2. Contributor lanzando pipeline permitido -> 202 Accepted
    token_contrib = create_access_token(
        subject=fixtures["users"]["contributor"].id,
        email=fixtures["users"]["contributor"].email
    )
    res_c = client.post(
        f"/api/v1/pipelines/documents/{doc_a.id}/run",
        headers={"Authorization": f"Bearer {token_contrib}", "X-Organization-Id": fixtures["org_a"].id},
        json={"force_reprocess": True}
    )
    assert res_c.status_code == 202

    # 3. Admin gestionando miembros -> 200
    token_admin = create_access_token(
        subject=fixtures["users"]["admin"].id,
        email=fixtures["users"]["admin"].email
    )
    res_m = client.get(
        f"/api/v1/organizations/{fixtures['org_a'].id}/members",
        headers={"Authorization": f"Bearer {token_admin}", "X-Organization-Id": fixtures["org_a"].id}
    )
    assert res_m.status_code == 200
    assert len(res_m.json()) >= 5

def test_multitenant_isolation(client, db):
    """Verifica que un usuario de Organización A no pueda acceder ni ver recursos de Organización B (404)."""
    fixtures = _create_tenant_fixtures(db)
    token_alpha = create_access_token(
        subject=fixtures["users"]["admin"].id,
        email=fixtures["users"]["admin"].email
    )

    # 1. Usuario Alpha intentando consultar proyecto de Organización Beta -> 404 Not Found
    res = client.get(
        f"/api/v1/projects/{fixtures['proj_b'].id}",
        headers={"Authorization": f"Bearer {token_alpha}", "X-Organization-Id": fixtures["org_a"].id}
    )
    assert res.status_code == 404

    # 2. Usuario Alpha listando proyectos -> solo ve los de Org Alpha
    res_list = client.get(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {token_alpha}", "X-Organization-Id": fixtures["org_a"].id}
    )
    assert res_list.status_code == 200
    project_ids = [p["id"] for p in res_list.json()]
    assert fixtures["proj_a"].id in project_ids
    assert fixtures["proj_b"].id not in project_ids

def test_concurrency_lock_and_orphan_recovery(db):
    """Verifica que el pipeline bloquee ejecuciones dobles concurrentes y libere locks huérfanos (>30 min)."""
    fixtures = _create_tenant_fixtures(db)
    doc_a = fixtures["doc_a"]
    svc = ReviewPipelineService(db)

    # 1. Primer pipeline run creado en status="running"
    run1 = svc.create_pipeline_run(
        scope_type="document",
        scope_id=doc_a.id,
        organization_id=fixtures["org_a"].id
    )
    run1.status = "running"
    run1.updated_at = datetime.utcnow()
    db.commit()

    # 2. Segundo intento concurrente con lock activo -> ValueError (409)
    with pytest.raises(ValueError) as exc:
        svc.create_pipeline_run(
            scope_type="document",
            scope_id=doc_a.id,
            organization_id=fixtures["org_a"].id,
            force_reprocess=False
        )
    assert "Existe un pipeline activo" in str(exc.value)

    # 3. Simular lock huérfano (inactivo por 45 minutos)
    run1.updated_at = datetime.utcnow() - timedelta(minutes=45)
    db.commit()

    # 4. Nuevo intento -> libera el lock huérfano y permite crear la nueva corrida
    run2 = svc.create_pipeline_run(
        scope_type="document",
        scope_id=doc_a.id,
        organization_id=fixtures["org_a"].id,
        force_reprocess=False
    )
    assert run2.id is not None
    assert run1.status == "failed"
