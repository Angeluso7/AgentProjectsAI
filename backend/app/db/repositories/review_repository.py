from typing import Optional, List
from sqlalchemy.orm import Session
from app.db.models.decision_memory import ReviewRun, RuleFinding, FindingEvidence, HumanFeedback
from app.db.repositories.base import BaseRepository
from app.schemas.review import HumanFeedbackCreate

class ReviewRepository(BaseRepository[ReviewRun]):
    def __init__(self, db: Session):
        super().__init__(ReviewRun, db)

    def list_by_project(self, project_id: str) -> List[ReviewRun]:
        return self.db.query(ReviewRun).filter(ReviewRun.project_id == project_id).all()

    def get_finding(self, finding_id: str) -> Optional[RuleFinding]:
        return self.db.query(RuleFinding).filter(RuleFinding.id == finding_id).first()

    def list_findings(self, review_run_id: str) -> List[RuleFinding]:
        return self.db.query(RuleFinding).filter(RuleFinding.review_run_id == review_run_id).all()

    def add_feedback(self, finding_id: str, feedback_in: HumanFeedbackCreate, user_id: Optional[str] = None) -> HumanFeedback:
        finding = self.get_finding(finding_id)
        if not finding:
            raise ValueError(f"Finding {finding_id} not found")

        # Actualizar estado del hallazgo según acción
        if feedback_in.action == "accept_finding":
            finding.status = "accepted"
        elif feedback_in.action == "reject_false_positive":
            finding.status = "rejected_false_positive"
        elif feedback_in.action == "correct_detection":
            finding.status = "under_review"
            if feedback_in.corrected_bbox:
                finding.bbox = feedback_in.corrected_bbox

        feedback = HumanFeedback(
            finding_id=finding_id,
            user_id=user_id,
            action=feedback_in.action.value if hasattr(feedback_in.action, "value") else str(feedback_in.action),
            corrected_bbox=feedback_in.corrected_bbox,
            corrected_class=feedback_in.corrected_class,
            notes=feedback_in.notes,
            sent_to_active_learning=feedback_in.action in ["reject_false_positive", "correct_detection"]
        )
        self.db.add(feedback)
        self.db.commit()
        self.db.refresh(feedback)
        return feedback
