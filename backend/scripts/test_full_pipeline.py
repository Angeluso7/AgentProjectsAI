import os
import sys

# Ensure app is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.session import SessionLocal
from app.services.intake.ai_extractor import AiDocumentExtractorService
from app.db.models.intake_extractions import SourceExtraction, ExtractedItem
from app.db.models.document_memory import DocumentStructuralNode

def main():
    db = SessionLocal()
    pdf_path = "./data/intake_sources/388d7837-9c5d-45fb-b3eb-69909a915e43/2066f27abcfc_Doc_Piping.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"ERROR: PDF file not found at {pdf_path}")
        return

    print("=== INICIANDO EXTRACCIÓN MULTIMODAL COMPLETA SOBRE PDF REAL (80 PÁGINAS) ===")
    service = AiDocumentExtractorService(db)
    
    extraction = service.extract_document_with_ai(
        title="TUTORIAL NORMA ISA S5.1 Y DIAGRAMAS P&ID",
        document_type="norma",
        discipline="piping",
        authority="ISA (International Society of Automation)",
        file_path=pdf_path
    )
    
    print(f"\n[OK] Sesión de extracción creada con ID: {extraction.id}")
    print(f"Status: {extraction.status}")
    print(f"Total ítems generados: {extraction.total_items}")
    
    # Query items by candidate_type
    items = db.query(ExtractedItem).filter(ExtractedItem.extraction_id == extraction.id).all()
    
    by_candidate_type = {}
    by_item_type = {}
    with_crops = 0
    
    for it in items:
        ct = it.candidate_type or "none"
        itype = it.item_type or "none"
        by_candidate_type[ct] = by_candidate_type.get(ct, 0) + 1
        by_item_type[itype] = by_item_type.get(itype, 0) + 1
        if it.crop_image_path:
            with_crops += 1
            
    print("\n--- DISTRIBUCIÓN CUANTITATIVA POR TIPO DE CANDIDATO ---")
    for ct, count in sorted(by_candidate_type.items()):
        print(f"  * {ct}: {count}")
        
    print("\n--- DISTRIBUCIÓN POR ITEM_TYPE ---")
    for itype, count in sorted(by_item_type.items()):
        print(f"  * {itype}: {count}")
        
    print(f"\nTotal candidatos con recorte visual generado en disco (crop_image_path): {with_crops}")
    
    # Check crops in ./data/crops/extractions/
    crops_dir = "./data/crops/extractions"
    if os.path.exists(crops_dir):
        crops_files = os.listdir(crops_dir)
        print(f"Archivos de recorte reales existentes en {crops_dir}: {len(crops_files)}")
        print(f"Ejemplos de recortes: {crops_files[:5]}")
        
    # Check structural nodes in DB
    nodes_count = db.query(DocumentStructuralNode).count()
    print(f"\nTotal DocumentStructuralNodes en BD: {nodes_count}")
    
    db.close()

if __name__ == "__main__":
    main()
