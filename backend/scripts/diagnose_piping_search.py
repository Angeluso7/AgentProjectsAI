import json
from app.db.session import SessionLocal
from app.services.intake.ai_extractor import AiDocumentExtractorService

def main():
    db = SessionLocal()
    try:
        extractor = AiDocumentExtractorService(db=db)
        query = "Simbología piping ISA S5.1"
        diag = extractor.search_web_sources_with_diagnostics(
            search_prompt=query,
            discipline="Piping e Instrumentación",
            document_type="any_web_doc",
            max_results=10
        )
        print("=== DIAGNOSTICS JSON ===")
        print(json.dumps(diag["diagnostics"], indent=2, ensure_ascii=False))
        print("\n=== FINAL RESULTS DELIVERED TO UI ===")
        for idx, r in enumerate(diag["results"], 1):
            print(f"{idx}. [{r.get('estimated_type')}] {r.get('title')}")
            print(f"   URL: {r.get('url')}")
            print(f"   Dominio: {r.get('domain')} | Score: {r.get('relevance_score')} | Tier: {r.get('source_quality_tier')} | Autoridad: {r.get('authority')}")
            if r.get('is_curated_backup'):
                print(f"   [ETIQUETA: Respaldo Curado de Ingeniería]")
            print()
    finally:
        db.close()

if __name__ == "__main__":
    main()
