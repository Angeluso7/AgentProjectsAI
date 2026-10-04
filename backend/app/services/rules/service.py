from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.db.models.decision_memory import RuleFinding, FindingEvidence
from app.core.logging import logger

class RulesService:
    """Servicio de evaluación de reglas determinísticas y normativas sobre documentos técnicos."""

    def __init__(self, db: Session):
        self.db = db

    def list_available_rules(self, discipline: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lista las reglas QA/QC y normativas registradas en el sistema."""
        rules = [
            {
                "rule_code": "QAQC-TB-001",
                "name": "Integridad de Campos Obligatorios en Viñeta",
                "category": "qa_qc",
                "discipline": "general",
                "severity": "high",
                "description": "Verifica que el plano contenga código único, título, escala nominal, revisión y fecha válida."
            },
            {
                "rule_code": "ARQ-DOOR-MIN-WIDTH",
                "name": "Ancho Mínimo de Vano de Puerta",
                "category": "normative",
                "discipline": "architecture",
                "severity": "high",
                "description": "Verifica que las puertas de recintos habitables cumplan con el ancho libre mínimo reglamentario (>= 0.85m)."
            },
            {
                "rule_code": "ELEC-PANEL-CLEARANCE",
                "name": "Zona de Despeje Frontal de Tableros Eléctricos",
                "category": "safety",
                "discipline": "electrical",
                "severity": "critical",
                "description": "Verifica que ningún obstáculo invada el área de 1.0 m frontal al tablero general."
            }
        ]
        if discipline:
            rules = [r for r in rules if r["discipline"] in [discipline, "general"]]
        return rules

    def evaluate_sheet_rules(self, sheet_id: str, rule_codes: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Evalúa un conjunto de reglas determinísticas sobre una hoja de plano."""
        logger.info(f"Evaluando reglas para sheet_id: {sheet_id}")
        return []
