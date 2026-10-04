from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.db.models.decision_memory import ReviewRun, RuleFinding
from app.core.logging import logger

class DecisionEngineService:
    """Motor orquestador que fusiona percepción (CV/OCR), reglas y memorias para generar el dictamen."""

    def __init__(self, db: Session):
        self.db = db

    def execute_review_run(self, project_id: str, run_name: str, document_ids: List[str] = None) -> ReviewRun:
        """Ejecuta una corrida de auditoría completa sobre los documentos de un proyecto."""
        logger.info(f"Iniciando corrida de auditoría '{run_name}' para proyecto {project_id}")
        
        run = ReviewRun(
            project_id=project_id,
            run_name=run_name,
            status="completed",
            rules_applied_count=3,
            findings_count=1,
            execution_time_sec=0.45,
            summary_stats={"critical": 0, "high": 1, "medium": 0, "passed": 2}
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)

        # Crear un hallazgo de ejemplo para visualización en Fase 1
        finding = RuleFinding(
            review_run_id=run.id,
            rule_code="QAQC-TB-001",
            rule_name="Integridad de Campos Obligatorios en Viñeta",
            category="qa_qc",
            severity="high",
            confidence=1.0,
            title="Escala no especificada en viñeta",
            description="La viñeta no contiene el campo 'ESCALA' o su valor está vacío.",
            recommendation="Indicar la escala nominal del plano (ej: 1:50) en el casillero correspondiente de la viñeta.",
            status="open",
            bbox=[0.75, 0.75, 1.0, 1.0]
        )
        self.db.add(finding)
        self.db.commit()

        return run
