from typing import Dict, Any, List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.services.active_learning.service import ActiveLearningService

router = APIRouter()

@router.get("/active-learning/queue")
def get_active_learning_queue(db: Session = Depends(get_db)):
    """Obtiene la lista de elementos en cola de active learning listos para etiquetado."""
    svc = ActiveLearningService(db)
    return {"queue": svc.get_pending_annotation_queue()}

@router.get("/models")
def list_models():
    """Lista los modelos registrados y versiones activas."""
    return {
        "models": [
            {"name": "yolo_symbols_architecture", "version": "v1.0.0", "status": "active", "mAP_50": 0.89},
            {"name": "title_block_detector", "version": "v1.2.0", "status": "active", "mAP_50": 0.94}
        ]
    }
