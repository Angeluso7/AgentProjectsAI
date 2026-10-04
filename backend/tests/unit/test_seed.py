import pytest
from scripts.seed_data import seed_database
from app.db.session import SessionLocal
from app.db.models import Project, KnowledgeAsset, NormativeDocument

def test_seed_database_idempotent():
    """Ejecuta el seed dos veces consecutivas para verificar que no falle ni duplique entidades clave."""
    # Primera ejecución
    seed_database()
    
    # Segunda ejecución (prueba de idempotencia)
    seed_database()
    
    db = SessionLocal()
    try:
        projects = db.query(Project).filter(Project.code == "PRJ-DEMO-001").all()
        assert len(projects) == 1, "Debe existir exactamente 1 proyecto con código PRJ-DEMO-001"

        assets = db.query(KnowledgeAsset).filter(KnowledgeAsset.code == "OGUC-CHILE-2024-ASSET").all()
        assert len(assets) == 1, "Debe existir exactamente 1 asset con código OGUC-CHILE-2024-ASSET"

        norms = db.query(NormativeDocument).filter(NormativeDocument.code == "OGUC-CHILE-2024").all()
        assert len(norms) == 1, "Debe existir exactamente 1 norma con código OGUC-CHILE-2024"
    finally:
        db.close()
