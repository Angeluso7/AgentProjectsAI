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

            # Migraciones para extracted_items (Visual Split, Crop e Historial de Linaje)
            conn.exec_driver_sql("ALTER TABLE extracted_items ADD COLUMN IF NOT EXISTS parent_item_id VARCHAR(36);")
            conn.exec_driver_sql("ALTER TABLE extracted_items ADD COLUMN IF NOT EXISTS is_derived BOOLEAN DEFAULT FALSE;")
            conn.exec_driver_sql("ALTER TABLE extracted_items ADD COLUMN IF NOT EXISTS split_mode VARCHAR(50);")
            conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_extracted_items_parent_item_id ON extracted_items (parent_item_id);")
            conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_extracted_items_is_derived ON extracted_items (is_derived);")
            conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_extracted_items_split_mode ON extracted_items (split_mode);")

            # Migraciones para structured_symbols (Fase 1 Piping Symbol Recognition)
            conn.exec_driver_sql("ALTER TABLE structured_symbols ADD COLUMN IF NOT EXISTS source_render_mode VARCHAR(20) DEFAULT 'raster';")
            conn.exec_driver_sql("ALTER TABLE structured_symbols ADD COLUMN IF NOT EXISTS layout_context VARCHAR(30) DEFAULT 'inside_table';")
            conn.exec_driver_sql("ALTER TABLE structured_symbols ADD COLUMN IF NOT EXISTS context_association_mode VARCHAR(30) DEFAULT 'row_band';")
            conn.exec_driver_sql("ALTER TABLE structured_symbols ADD COLUMN IF NOT EXISTS standard_reference VARCHAR(150);")
            conn.exec_driver_sql("ALTER TABLE structured_symbols ADD COLUMN IF NOT EXISTS canonical_symbol_family VARCHAR(50) DEFAULT 'valves';")
            conn.exec_driver_sql("ALTER TABLE structured_symbols ADD COLUMN IF NOT EXISTS visual_variant_group_id VARCHAR(36);")
            conn.exec_driver_sql("ALTER TABLE structured_symbols ADD COLUMN IF NOT EXISTS estimated_physical_size_mm JSON DEFAULT '{}'::json;")
            conn.exec_driver_sql("ALTER TABLE structured_symbols ADD COLUMN IF NOT EXISTS reused_for_matching_count INTEGER DEFAULT 0;")
            conn.exec_driver_sql("ALTER TABLE structured_symbols ADD COLUMN IF NOT EXISTS false_positive_count INTEGER DEFAULT 0;")
            conn.exec_driver_sql("ALTER TABLE structured_symbols ADD COLUMN IF NOT EXISTS human_validation_notes TEXT;")
            conn.exec_driver_sql("ALTER TABLE structured_symbols ADD COLUMN IF NOT EXISTS source_table_id VARCHAR(36);")
            conn.exec_driver_sql("ALTER TABLE structured_symbols ADD COLUMN IF NOT EXISTS row_index INTEGER;")
            conn.exec_driver_sql("ALTER TABLE structured_symbols ADD COLUMN IF NOT EXISTS col_index INTEGER;")
            conn.exec_driver_sql("ALTER TABLE structured_symbols ADD COLUMN IF NOT EXISTS cell_bbox JSON;")
            conn.exec_driver_sql("ALTER TABLE structured_symbols ADD COLUMN IF NOT EXISTS row_bbox JSON;")
            conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_structured_symbols_source_table_id ON structured_symbols (source_table_id);")
            conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_structured_symbols_source_render_mode ON structured_symbols (source_render_mode);")
            conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_structured_symbols_layout_context ON structured_symbols (layout_context);")
            conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_structured_symbols_context_association_mode ON structured_symbols (context_association_mode);")
            conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_structured_symbols_canonical_symbol_family ON structured_symbols (canonical_symbol_family);")
            conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_structured_symbols_visual_variant_group_id ON structured_symbols (visual_variant_group_id);")

            # Migraciones para extracted_table_cells (Soporte explícito de celdas con simbología)
            conn.exec_driver_sql("ALTER TABLE extracted_table_cells ADD COLUMN IF NOT EXISTS cell_type VARCHAR(30) DEFAULT 'text_cell';")
            conn.exec_driver_sql("ALTER TABLE extracted_table_cells ADD COLUMN IF NOT EXISTS symbol_id VARCHAR(36);")
            conn.exec_driver_sql("ALTER TABLE extracted_table_cells ADD COLUMN IF NOT EXISTS has_symbol BOOLEAN DEFAULT FALSE;")
            conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_extracted_table_cells_symbol_id ON extracted_table_cells (symbol_id);")
            conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_extracted_table_cells_cell_type ON extracted_table_cells (cell_type);")

            # Migraciones para rule_documents (Conteo explícito de símbolos)
            conn.exec_driver_sql("ALTER TABLE rule_documents ADD COLUMN IF NOT EXISTS symbols_count INTEGER DEFAULT 0;")
            
            # Sincronizar tabla de control de versiones de Alembic
            conn.exec_driver_sql("UPDATE alembic_version SET version_num = '0019_piping_symbol_dual' WHERE version_num = '0018_visual_split_crop_lineage';")
            conn.exec_driver_sql("INSERT INTO alembic_version (version_num) SELECT '0019_piping_symbol_dual' WHERE NOT EXISTS (SELECT 1 FROM alembic_version);")
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
    expose_headers=["Content-Disposition", "Content-Length", "X-Report-SHA256"],
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
