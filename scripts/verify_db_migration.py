import sys
import os

from app.db.session import SessionLocal
from app.db.repositories.intake_extraction_repository import IntakeExtractionRepository
from app.services.intake.ai_extractor import AiDocumentExtractorService

def main():
    db = SessionLocal()
    try:
        repo = IntakeExtractionRepository(db)
        org = repo.get_or_create_default_org()
        
        # 1. Crear sesión de extracción
        ext = repo.create_extraction_session(
            title="Prueba de Extracción con Migración 0018",
            document_type="plano",
            authority="SEC",
            discipline="eléctrica",
            extraction_mode="ai_document"
        )
        print(f"Created extraction: {ext.id}")
        
        # 2. Insertar ExtractedItem
        parent = repo.add_extracted_item(
            extraction_id=ext.id,
            item_type="rule",
            title="Regla Principal Tablero General T-01",
            code_or_number="REG-TG-01",
            description="Canalizaciones y protecciones de alimentadores.",
            bbox_normalized=[0.1, 0.1, 0.9, 0.9],
            page_number=1,
            is_derived=False,
            split_mode=None
        )
        print(f"Created parent item in DB: id={parent.id}, parent_item_id={parent.parent_item_id}, is_derived={parent.is_derived}, split_mode={parent.split_mode}")
        
        # 3. Probar Split
        service = AiDocumentExtractorService(db)
        child = service.split_extracted_item(
            extraction_id=ext.id,
            item_id=parent.id,
            bbox=[0.2, 0.2, 0.5, 0.5],
            title_hint="Subregla de Interruptor Diferencial",
            discipline="eléctrica"
        )
        print(f"Created child item via Visual Split: id={child.id}, parent_item_id={child.parent_item_id}, is_derived={child.is_derived}, split_mode={child.split_mode}")
        
        # 4. Probar Crop
        cropped = service.crop_extracted_item(
            extraction_id=ext.id,
            item_id=parent.id,
            bbox=[0.15, 0.15, 0.85, 0.85],
            user_id="verifier_admin"
        )
        history_len = len(cropped.metadata_payload.get("previous_crop_history", []))
        print(f"Updated parent item via Crop: id={cropped.id}, bbox={cropped.bbox_normalized}, split_mode={cropped.split_mode}, previous_crop_history_count={history_len}")
        
        print("\n>>> ALL DB INSERTIONS, SPLIT AND CROP OPERATIONS COMPLETED WITH ZERO ERRORS! <<<")
    finally:
        db.close()

if __name__ == "__main__":
    main()
