import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.session import Base, get_db
from app.db.models import *

# In-memory SQLite para pruebas rápidas y aisladas
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Patch global app.db.session for integration tests
import app.db.session as app_session_mod
app_session_mod.SessionLocal = TestingSessionLocal
app_session_mod.engine = engine


@pytest.fixture(scope="function")
def db_session():
    """Crea una base de datos limpia en memoria para cada prueba."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        try:
            from app.services.operations.dispatcher import wait_for_all_jobs
            wait_for_all_jobs(timeout=3.0)
        except Exception:
            pass
        import time
        for i in range(15):
            try:
                Base.metadata.drop_all(bind=engine)
                break
            except Exception as e:
                if i < 14:
                    time.sleep(0.15)
                else:
                    raise

@pytest.fixture(autouse=True)
def auto_override_db(db_session):
    """Garantiza que get_db siempre utilice la sesión SQLite en memoria."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)

@pytest.fixture(scope="function")
def client(db_session):
    """Cliente HTTP de prueba con inyección de sesión de BD en memoria."""
    with TestClient(app) as c:
        yield c

