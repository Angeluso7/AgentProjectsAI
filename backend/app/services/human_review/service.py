from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from app.db.repositories.review_repository import ReviewRepository
from app.schemas.review import HumanFeedbackCreate, HumanFeedbackRead

class HumanReviewService:
    """Servicio de triage y supervisión experta (Human-in-the-Loop)."""

    def __init__(self, db: Session):
        self.repo = ReviewRepository(db)

    def submit_feedback(self, finding_id: str, feedback_in: HumanFeedbackCreate, user_id: Optional[str] = None) -> HumanFeedbackRead:
        """Registra la corrección o validación humana sobre un hallazgo."""
        feedback = self.repo.add_feedback(finding_id, feedback_in, user_id)
        return HumanFeedbackRead.model_validate(feedback)
