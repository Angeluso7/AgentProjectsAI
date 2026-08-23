from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from app.db.models.template_memory import OntologyDictionary
from app.core.logging import logger

class SemanticsService:
    """Servicio de normalización semántica a términos canónicos usando ontologías y diccionarios."""

    def __init__(self, db: Session):
        self.db = db

    def normalize_term(self, raw_term: str, domain: str = "architecture") -> Optional[str]:
        """Normaliza un texto o abreviatura a su término canónico."""
        cleaned = raw_term.strip().upper()
        ontologies = self.db.query(OntologyDictionary).filter(OntologyDictionary.domain == domain).all()
        for ont in ontologies:
            if cleaned == ont.canonical_term or cleaned in [s.upper() for s in ont.synonyms]:
                return ont.canonical_term
        return None
