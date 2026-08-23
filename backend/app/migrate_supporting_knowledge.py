from app.db.session import engine, Base
from sqlalchemy import text
from app.db.models.intake_extractions import SupportingKnowledgeItem

def run_migration():
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE extracted_items ADD COLUMN IF NOT EXISTS structured_matrix JSON DEFAULT '{}'"))
        conn.execute(text("ALTER TABLE extracted_items ADD COLUMN IF NOT EXISTS validated_at TIMESTAMP WITHOUT TIME ZONE"))
        conn.execute(text("ALTER TABLE extracted_items ADD COLUMN IF NOT EXISTS validated_by VARCHAR(100)"))
        print("Columns added to extracted_items successfully.")
    
    Base.metadata.create_all(bind=engine)
    print("Table supporting_knowledge_items created/checked successfully.")

if __name__ == "__main__":
    run_migration()
