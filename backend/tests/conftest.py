import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("DISABLE_SQLALCHEMY_C_EXTENSIONS", "1")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.session import Base, get_db
from app.db.models import *

import tempfile
import atexit
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.main import app
from app.db.session import Base, get_db
from app.db.models import *

# Para pruebas con SQLite concurrente (background jobs en ThreadPool),
# SQLite en memoria (:memory:) con StaticPool comparte la misma conexión C entre hilos sin serialización,
# provocando SQLITE_MISUSE ('sqlite3.InterfaceError: bad parameter or other API misuse')
# y colisiones de transacciones entre sesiones concurrentes.
# El uso de base de datos SQLite en archivo temporal con WAL mode y NullPool otorga a cada
# hilo/sesión una conexión independiente y soporte completo de concurrencia WAL multi-hilo.
TEST_DB_FILE = os.path.join(tempfile.gettempdir(), f"planreview_test_{os.getpid()}.db")
SQLALCHEMY_DATABASE_URL = f"sqlite:///{TEST_DB_FILE}"
os.environ["DATABASE_URL"] = SQLALCHEMY_DATABASE_URL

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30.0},
    poolclass=NullPool,
)

@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()

def _cleanup_test_db():
    for ext in ["", "-wal", "-shm"]:
        target = TEST_DB_FILE + ext
        if os.path.exists(target):
            try:
                os.remove(target)
            except Exception:
                pass

atexit.register(_cleanup_test_db)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Patch global app.db.session for integration tests
import app.db.session as app_session_mod
app_session_mod.SessionLocal = TestingSessionLocal
app_session_mod.engine = engine


@pytest.fixture(scope="function")
def db_session():
    """Crea una base de datos limpia para cada prueba."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        try:
            from app.services.operations.dispatcher import wait_for_all_jobs
            wait_for_all_jobs(timeout=10.0)
        except Exception:
            pass

        db.close()

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

