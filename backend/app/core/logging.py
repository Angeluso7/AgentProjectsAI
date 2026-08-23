import logging
import sys
from app.core.settings import settings

def setup_logging():
    """Configura el logger estructurado para el backend."""
    log_level = logging.DEBUG if settings.DEBUG else logging.INFO
    
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Evitar duplicar handlers
    if not root_logger.handlers:
        root_logger.addHandler(handler)
        
    # Silenciar logs excesivos de terceros
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING if not settings.DB_ECHO else logging.INFO)

logger = logging.getLogger("plan_review")
