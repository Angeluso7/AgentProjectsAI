import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.settings import settings
from app.core.logging import setup_logging, logger
from app.db.session import engine, Base
from app.db.models import * # Importa todos los modelos para registro en Base.metadata
from app.api.v1.router import api_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Inicializar logging y crear tablas si no existen
    setup_logging()
    logger.info(f"Iniciando {settings.APP_NAME} v{settings.APP_VERSION} en entorno {settings.ENVIRONMENT}")
    try:
        Base.metadata.create_all(bind=engine)
        # Migraciones automáticas de columnas si no existen
        with engine.begin() as conn:
            conn.exec_driver_sql("ALTER TABLE knowledge_items ADD COLUMN IF NOT EXISTS ingestion_channel VARCHAR(64) DEFAULT 'manual_entry';")
            conn.exec_driver_sql("ALTER TABLE knowledge_items ADD COLUMN IF NOT EXISTS modality VARCHAR(64) DEFAULT 'text';")
            conn.exec_driver_sql("ALTER TABLE knowledge_items ADD COLUMN IF NOT EXISTS visual_crop_url VARCHAR(512);")
            conn.exec_driver_sql("ALTER TABLE knowledge_items ADD COLUMN IF NOT EXISTS legend_reference VARCHAR(512);")
            
            # Migraciones para information_acquisition_requests
            conn.exec_driver_sql("ALTER TABLE information_acquisition_requests ADD COLUMN IF NOT EXISTS iteration_count INTEGER DEFAULT 0;")
            conn.exec_driver_sql("ALTER TABLE information_acquisition_requests ADD COLUMN IF NOT EXISTS max_iterations INTEGER DEFAULT 3;")
            conn.exec_driver_sql("ALTER TABLE information_acquisition_requests ADD COLUMN IF NOT EXISTS search_sources_limit INTEGER DEFAULT 5;")
            conn.exec_driver_sql("ALTER TABLE information_acquisition_requests ADD COLUMN IF NOT EXISTS relevance_score FLOAT DEFAULT 0.0;")
            conn.exec_driver_sql("ALTER TABLE information_acquisition_requests ADD COLUMN IF NOT EXISTS confidence_score FLOAT DEFAULT 0.0;")
            conn.exec_driver_sql("ALTER TABLE information_acquisition_requests ADD COLUMN IF NOT EXISTS coverage_score FLOAT DEFAULT 0.0;")
            conn.exec_driver_sql("ALTER TABLE information_acquisition_requests ADD COLUMN IF NOT EXISTS overall_adequacy_score FLOAT DEFAULT 0.0;")
            conn.exec_driver_sql("ALTER TABLE information_acquisition_requests ADD COLUMN IF NOT EXISTS adequacy_classification VARCHAR(64) DEFAULT 'pending';")
            conn.exec_driver_sql("ALTER TABLE information_acquisition_requests ADD COLUMN IF NOT EXISTS termination_reason VARCHAR(64);")
            conn.exec_driver_sql("ALTER TABLE information_acquisition_requests ADD COLUMN IF NOT EXISTS escalation_details JSON DEFAULT '{}'::json;")
        logger.info("Esquemas de Base de Datos y las 4 Memorias inicializados correctamente.")
    except Exception as e:
        logger.warning(f"Aviso de inicialización de BD: {e}")
    yield
    # Shutdown
    logger.info("Deteniendo aplicación...")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Plataforma híbrida de revisión de planos PDF y documentos técnicos (Visión + OCR + Reglas + 4 Memorias)",
    lifespan=lifespan
)

# Configuración CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Montar ruta estática para previsualización de recortes y renders
if os.path.exists(settings.STORAGE_LOCAL_ROOT):
    app.mount("/data", StaticFiles(directory=settings.STORAGE_LOCAL_ROOT), name="data")

# Incluir Rutas de API v1
app.include_router(api_router, prefix=settings.API_V1_PREFIX)

@app.get("/health", tags=["health"])
def health_check():
    """Endpoint directo de salud del backend."""
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT
    }

@app.get("/")
def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs_url": "/docs",
        "health_url": "/health",
        "api_v1": settings.API_V1_PREFIX,
        "status": "ready"
    }
