from typing import Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models.document_memory import Document, DocumentSheet
from app.db.models.normative_memory import NormativeDocument, NormativeClause
from app.db.models.template_memory import TitleBlockTemplate, SymbolLibrary, OntologyDictionary
from app.db.models.decision_memory import ReviewRun, RuleFinding, HumanFeedback

router = APIRouter()

@router.get("/stats")
def get_memories_stats(db: Session = Depends(get_db)):
    """Obtiene el estado y conteo de registros en las 4 memorias persistentes."""
    return {
        "document_memory": {
            "documents_count": db.query(Document).count(),
            "sheets_count": db.query(DocumentSheet).count()
        },
        "normative_memory": {
            "standards_count": db.query(NormativeDocument).count(),
            "clauses_count": db.query(NormativeClause).count()
        },
        "template_memory": {
            "title_block_templates_count": db.query(TitleBlockTemplate).count(),
            "symbol_libraries_count": db.query(SymbolLibrary).count(),
            "ontologies_count": db.query(OntologyDictionary).count()
        },
        "decision_memory": {
            "review_runs_count": db.query(ReviewRun).count(),
            "findings_count": db.query(RuleFinding).count(),
            "human_feedbacks_count": db.query(HumanFeedback).count()
        }
    }
