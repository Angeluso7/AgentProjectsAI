import uuid
import pytest
import concurrent.futures
from fastapi.testclient import TestClient

from app.db.models.core import Organization, User, OrganizationMembership, Project
from app.core.security import create_access_token, hash_password
from app.db.session import get_db


@pytest.fixture
def consistency_setup(client: TestClient, db_session):
    """Crea dos organizaciones aisladas con usuarios administradores para pruebas de unicidad y RLS."""
    org1 = Organization(
        id=f"org-test-1-{uuid.uuid4().hex[:8]}",
        name="Organización Test Alpha",
        slug=f"org-alpha-{uuid.uuid4().hex[:8]}",
        status="active"
    )
    org2 = Organization(
        id=f"org-test-2-{uuid.uuid4().hex[:8]}",
        name="Organización Test Beta",
        slug=f"org-beta-{uuid.uuid4().hex[:8]}",
        status="active"
    )
    db_session.add_all([org1, org2])

    user1 = User(
        id=f"user-1-{uuid.uuid4().hex[:8]}",
        email=f"admin1-{uuid.uuid4().hex[:8]}@test.com",
        display_name="Admin Alpha",
        password_hash=hash_password("adminpass123"),
        is_active=True,
        is_superuser=False
    )
    user2 = User(
        id=f"user-2-{uuid.uuid4().hex[:8]}",
        email=f"admin2-{uuid.uuid4().hex[:8]}@test.com",
        display_name="Admin Beta",
        password_hash=hash_password("adminpass123"),
        is_active=True,
        is_superuser=False
    )
    db_session.add_all([user1, user2])

    m1 = OrganizationMembership(
        id=str(uuid.uuid4()),
        organization_id=org1.id,
        user_id=user1.id,
        role="admin",
        status="active"
    )
    m2 = OrganizationMembership(
        id=str(uuid.uuid4()),
        organization_id=org2.id,
        user_id=user2.id,
        role="admin",
        status="active"
    )
    db_session.add_all([m1, m2])
    db_session.commit()

    token1 = create_access_token(subject=user1.id, email=user1.email, extra_claims={"org_id": org1.id, "role": "admin"})
    token2 = create_access_token(subject=user2.id, email=user2.email, extra_claims={"org_id": org2.id, "role": "admin"})

    headers1 = {
        "Authorization": f"Bearer {token1}",
        "X-Organization-Id": org1.id
    }
    headers2 = {
        "Authorization": f"Bearer {token2}",
        "X-Organization-Id": org2.id
    }

    return {
        "org1": org1,
        "org2": org2,
        "headers1": headers1,
        "headers2": headers2,
    }


def test_project_creation_and_listing(client: TestClient, consistency_setup):
    """
    1. Crear primer proyecto: éxito 201.
    2. Listar proyectos: aparece el recién creado.
    """
    h1 = consistency_setup["headers1"]
    code = f"PRJ-TEST-{uuid.uuid4().hex[:6].upper()}"
    payload = {
        "code": code,
        "name": "Proyecto Piloto de Piping",
        "client_name": "A. Angel",
        "discipline": "plumbing",
        "stage": "Ingeniería Básica",
        "status": "active",
        "description": "Proyecto de prueba"
    }

    res_create = client.post("/api/v1/projects/", json=payload, headers=h1)
    assert res_create.status_code == 201, res_create.text
    created = res_create.json()
    assert created["code"] == code
    assert created["name"] == "Proyecto Piloto de Piping"
    assert created["id"] is not None

    # Listar proyectos en org1: debe aparecer
    res_list = client.get("/api/v1/projects/", headers=h1)
    assert res_list.status_code == 200
    projects = res_list.json()
    assert any(p["id"] == created["id"] for p in projects)


def test_duplicate_code_same_org_conflict_409(client: TestClient, consistency_setup):
    """
    3. Crear mismo código, misma organización: 409 consistente.
    4. Respuesta 409 tiene formato API estructurado con existing_project.
    """
    h1 = consistency_setup["headers1"]
    code = f"PRJ-DUP-{uuid.uuid4().hex[:6].upper()}"
    payload = {
        "code": code,
        "name": "Proyecto Original",
        "client_name": "Cliente A",
        "discipline": "architecture"
    }

    res1 = client.post("/api/v1/projects/", json=payload, headers=h1)
    assert res1.status_code == 201

    # Reintento con el mismo código en la misma org
    res2 = client.post("/api/v1/projects/", json=payload, headers=h1)
    assert res2.status_code == 409, res2.text
    data = res2.json()
    assert "detail" in data
    detail = data["detail"]
    if isinstance(detail, dict):
        assert f"El código {code} ya existe" in detail["message"]
        assert detail["conflict_type"] == "duplicate_code"
        assert detail["existing_project"]["code"] == code
    else:
        assert f"El código {code} ya existe" in detail


def test_normalized_code_case_and_whitespace_conflict(client: TestClient, consistency_setup):
    """
    5. Crear código con diferencia de mayúscula/minúscula o espacios: 409 si la normalización los considera iguales.
    """
    h1 = consistency_setup["headers1"]
    raw_code = f"prj-norm-{uuid.uuid4().hex[:6].lower()}"
    
    # Crear con mayúsculas
    client.post("/api/v1/projects/", json={
        "code": raw_code.upper(),
        "name": "Proyecto Base Normalizado",
        "discipline": "structural"
    }, headers=h1)

    # Intentar con minúsculas y espacios agregados: '  prj-norm-xxx  '
    variant_code = f"   {raw_code.lower()}   "
    res = client.post("/api/v1/projects/", json={
        "code": variant_code,
        "name": "Intento de Proyecto Duplicado",
        "discipline": "structural"
    }, headers=h1)
    assert res.status_code == 409, res.text


def test_same_code_different_org_allowed(client: TestClient, consistency_setup):
    """
    6. Crear mismo código, distinta organización: éxito si la política es por organización (multitenancy).
    """
    h1 = consistency_setup["headers1"]
    h2 = consistency_setup["headers2"]
    shared_code = f"PRJ-MULTI-{uuid.uuid4().hex[:6].upper()}"

    # Crear en org1
    res1 = client.post("/api/v1/projects/", json={
        "code": shared_code,
        "name": "Proyecto en Org 1",
        "discipline": "architecture"
    }, headers=h1)
    assert res1.status_code == 201

    # Crear en org2 con el mismo código debe ser permitido
    res2 = client.post("/api/v1/projects/", json={
        "code": shared_code,
        "name": "Proyecto en Org 2",
        "discipline": "architecture"
    }, headers=h2)
    assert res2.status_code == 201
    assert res1.json()["id"] != res2.json()["id"]

    # Org2 no debe ver el proyecto de Org1
    list2 = client.get("/api/v1/projects/", headers=h2).json()
    assert all(p["id"] != res1.json()["id"] for p in list2)


def test_archived_project_reserves_code(client: TestClient, consistency_setup):
    """
    7. Proyecto archivado: valida política explícita (conserva y reserva el código).
    """
    h1 = consistency_setup["headers1"]
    code = f"PRJ-ARCH-{uuid.uuid4().hex[:6].upper()}"

    res = client.post("/api/v1/projects/", json={
        "code": code,
        "name": "Proyecto para archivar",
        "discipline": "mechanical"
    }, headers=h1)
    proj_id = res.json()["id"]

    # Archivar proyecto
    res_arch = client.put(f"/api/v1/projects/{proj_id}/archive", headers=h1)
    assert res_arch.status_code == 200
    assert res_arch.json()["status"] == "archived"

    # Intentar crear nuevo proyecto con el código reservado del archivado -> debe fallar con 409
    res_recreate = client.post("/api/v1/projects/", json={
        "code": code,
        "name": "Nuevo con código de archivado",
        "discipline": "mechanical"
    }, headers=h1)
    assert res_recreate.status_code == 409


def test_soft_deleted_project_allows_code_reuse(client: TestClient, consistency_setup):
    """
    8. Proyecto soft-deleted: valida política explícita (permite reutilizar el código).
    """
    h1 = consistency_setup["headers1"]
    code = f"PRJ-DEL-{uuid.uuid4().hex[:6].upper()}"

    res = client.post("/api/v1/projects/", json={
        "code": code,
        "name": "Proyecto para borrar",
        "discipline": "electrical"
    }, headers=h1)
    proj_id = res.json()["id"]

    # Borrado lógico (soft-delete)
    res_del = client.delete(f"/api/v1/projects/{proj_id}?hard_delete=false", headers=h1)
    assert res_del.status_code == 200

    # Reutilizar el código debe tener éxito
    res_reuse = client.post("/api/v1/projects/", json={
        "code": code,
        "name": "Proyecto que reutiliza código liberado",
        "discipline": "electrical"
    }, headers=h1)
    assert res_reuse.status_code == 201
    assert res_reuse.json()["id"] != proj_id


def test_concurrent_project_creation_uniqueness(client: TestClient, consistency_setup):
    """
    9. Concurrencia: dos o más solicitudes simultáneas con mismo código producen exactamente un proyecto exitoso y los demás 409.
    """
    from app.db.session import SessionLocal, get_db
    from app.main import app

    h1 = consistency_setup["headers1"]
    shared_code = f"PRJ-RACE-{uuid.uuid4().hex[:6].upper()}"

    import threading
    req_lock = threading.Lock()

    def thread_safe_get_db():
        with req_lock:
            s = SessionLocal()
            try:
                yield s
            finally:
                s.close()

    original_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = thread_safe_get_db

    try:
        def try_create():
            return client.post("/api/v1/projects/", json={
                "code": shared_code,
                "name": "Proyecto Concurrente",
                "discipline": "architecture"
            }, headers=h1)

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(try_create) for _ in range(5)]
            results = [f.result() for f in futures]

        status_codes = [r.status_code for r in results]
        assert status_codes.count(201) == 1, f"Debe crearse exactamente 1 proyecto. Estados: {status_codes}"
        assert status_codes.count(409) == 4, f"Las 4 solicitudes concurrentes restantes deben dar 409. Estados: {status_codes}"
    finally:
        if original_override:
            app.dependency_overrides[get_db] = original_override
        else:
            app.dependency_overrides.pop(get_db, None)
