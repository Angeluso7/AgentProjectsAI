from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.db.models.decision_memory import HumanFeedback
from app.core.logging import logger

class ActiveLearningService:
    """Servicio para seleccionar y estructurar datos inciertos o corregidos para reentrenamiento."""

    def __init__(self, db: Session):
        self.db = db

    def get_pending_annotation_queue(self) -> List[Dict[str, Any]]:
        """Recupera casos pendientes de etiquetado o con feedback correctivo humano."""
        feedbacks = self.db.query(HumanFeedback).filter(HumanFeedback.sent_to_active_learning == True).all()
        return [
            {
                "feedback_id": fb.id,
                "finding_id": fb.finding_id,
                "action": fb.action,
                "corrected_bbox": fb.corrected_bbox,
                "corrected_class": fb.corrected_class,
                "created_at": fb.created_at
            }
            for fb in feedbacks
        ]
