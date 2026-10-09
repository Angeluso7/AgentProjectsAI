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
    # Startup: Inicializar logging
    setup_logging()
    logger.info(f"Iniciando {settings.APP_NAME} v{settings.APP_VERSION} en entorno {settings.ENVIRONMENT}")
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
    expose_headers=["Content-Disposition", "Content-Length", "X-Report-SHA256"],
)

# Montar ruta estática para previsualización de recortes y renders
if os.path.exists(settings.STORAGE_LOCAL_ROOT):
    app.mount("/data", StaticFiles(directory=settings.STORAGE_LOCAL_ROOT), name="data")

storage_root = os.path.join(os.getcwd(), "storage")
if os.path.exists(storage_root):
    app.mount("/storage", StaticFiles(directory=storage_root), name="storage")

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
