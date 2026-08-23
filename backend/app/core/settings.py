from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field
import os

class Settings(BaseSettings):
    """Configuración global de la aplicación cargada desde variables de entorno."""
    APP_NAME: str = "Plan Review AI Hybrid"
    APP_VERSION: str = "0.2.0"
    ENVIRONMENT: str = Field(default="development", validation_alias="ENVIRONMENT")
    DEBUG: bool = True
    
    # API & Seguridad
    API_V1_PREFIX: str = "/api/v1"
    SECRET_KEY: str = Field(default="insecure-dev-secret-key-change-in-production", validation_alias="SECRET_KEY")
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:5173"]
    
    # Base de Datos PostgreSQL + PostGIS / SQLite
    DATABASE_URL: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/planreview",
        validation_alias="DATABASE_URL"
    )
    DB_ECHO: bool = False
    
    # Redis & Workers
    REDIS_URL: str = Field(default="redis://localhost:6379/0", validation_alias="REDIS_URL")
    
    # Directorios y Almacenamiento
    BASE_DIR: str = Field(default=".", validation_alias="BASE_DIR")
    DATA_DIR: str = Field(default="./data", validation_alias="DATA_DIR")
    STORAGE_LOCAL_ROOT: str = Field(default="./data", validation_alias="STORAGE_LOCAL_ROOT")
    RAW_DOCUMENTS_DIR: str = "./data/raw"
    RENDERED_SHEETS_DIR: str = "./data/rendered"
    EVIDENCE_CROPS_DIR: str = "./data/crops"
    
    # Rutas de conocimiento y memoria
    KNOWLEDGE_BASE_DIR: str = "./knowledge"
    MEMORY_STORAGE_DIR: str = "./memory"
    RULES_DEFINITION_DIR: str = "./rules"
    MODELS_REGISTRY_DIR: str = "./models"
    
    # Inferencia, Ingesta & Rasterizado
    DEFAULT_RENDER_DPI: int = Field(default=150, validation_alias="DEFAULT_RENDER_DPI") # 150 DPI conservador para desarrollo
    THUMBNAIL_RENDER_DPI: int = Field(default=72, validation_alias="THUMBNAIL_RENDER_DPI")
    UNCERTAINTY_MIN_CONF: float = 0.35
    UNCERTAINTY_MAX_CONF: float = 0.70
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"

settings = Settings()

# Crear directorios de datos locales si no existen
for path in [
    settings.RAW_DOCUMENTS_DIR,
    settings.RENDERED_SHEETS_DIR,
    settings.EVIDENCE_CROPS_DIR,
]:
    os.makedirs(path, exist_ok=True)
