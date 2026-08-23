"""
Script CLI idempotente para inicializar la base de datos con datos de ejemplo:
- 1 Proyecto de ejemplo
- 1 Documento y lámina de ejemplo en document_memory
- 1 KnowledgeAsset de ejemplo
- 1 Documento normativo (OGUC) con cláusula y criterio
- 1 Template de viñeta estándar (TitleBlockTemplate)
- 1 Corrida de auditoría con 1 hallazgo de ejemplo
"""
import sys
import os
import hashlib

# Asegurar path del backend (soporta ejecución en contenedor /app y local)
sys.path.insert(0, "/app")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.session import SessionLocal, engine, Base
from app.db.models import (
    Organization, User, OrganizationMembership,
    Project, ProjectVersion, Document, DocumentSheet, SheetRegion, ExtractedText,
    KnowledgeAsset, NormativeDocument, NormativeClause, NormativeCriterion,
    TitleBlockTemplate, OntologyDictionary, ReviewRun, RuleFinding
)
from app.core.security import hash_password
from app.services.knowledge.service import KnowledgeBaseService as KnowledgeService

def seed_database():
    print(">>> Inicializando esquemas de Base de Datos...")
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        # 0. Organización y Usuario Admin inicial (idempotente)
        org_slug = "org-principal"
        org = db.query(Organization).filter(Organization.slug == org_slug).first()
        if not org:
            print(">>> 0. Creando Organización y Usuario Administrador...")
            org = Organization(
                name="Organización Principal",
                slug=org_slug,
                status="active",
                settings={"plan": "enterprise"}
            )
            db.add(org)
            db.commit()
            db.refresh(org)
            print(f"    Organización creada: {org.name} ({org.slug})")
        else:
            print(f"    Organización ya existe: {org.slug}")

        admin_email = "admin@planreview.ai"
        user = db.query(User).filter(User.email == admin_email).first()
        if not user:
            user = User(
                email=admin_email,
                display_name="Administrador QA/QC",
                password_hash=hash_password("admin123456"),
                is_active=True,
                is_superuser=True
            )
            db.add(user)
            db.commit()
            db.refresh(user)

            membership = OrganizationMembership(
                organization_id=org.id,
                user_id=user.id,
                role="admin",
                status="active"
            )
            db.add(membership)
            db.commit()
            print(f"    Usuario Admin creado: {admin_email}")
        else:
            print(f"    Usuario Admin ya existe: {admin_email}")

        print(">>> 1. Sincronizando archivos semilla de conocimiento...")
        k_svc = KnowledgeService(db)
        k_counts = k_svc.sync_seed_knowledge()
        print(f"    Archivos procesados: {k_counts}")

        # 2. Knowledge Asset de ejemplo (idempotente)
        asset_code = "OGUC-CHILE-2024-ASSET"
        asset = db.query(KnowledgeAsset).filter(KnowledgeAsset.code == asset_code).first()
        if not asset:
            print(">>> 2. Creando KnowledgeAsset de ejemplo...")
            asset = KnowledgeAsset(
                code=asset_code,
                title="Manual Guía OGUC Edificación y Accesibilidad",
                asset_type="standard",
                discipline="architecture",
                version="2024.1",
                description="Guía técnica para la aplicación de anchos de vanos y alturas de recintos.",
                content_payload={
                    "authority": "MINVU",
                    "articles_covered": ["4.1.7", "4.1.8"],
                    "status": "official"
                }
            )
            db.add(asset)
            db.commit()
            print(f"    KnowledgeAsset creado: {asset_code}")
        else:
            print(f"    KnowledgeAsset ya existe: {asset_code}")

        # 3. Documento normativo de ejemplo (idempotente)
        norm_code = "OGUC-CHILE-2024"
        norm_doc = db.query(NormativeDocument).filter(NormativeDocument.code == norm_code).first()
        if not norm_doc:
            print(">>> 3. Creando NormativeDocument y criterios de ejemplo...")
            norm_doc = NormativeDocument(
                code=norm_code,
                title="Ordenanza General de Urbanismo y Construcciones (OGUC)",
                authority="MINVU",
                country="CL",
                discipline="architecture",
                version_year=2024
            )
            db.add(norm_doc)
            db.commit()
            db.refresh(norm_doc)

            clause = NormativeClause(
                document_id=norm_doc.id,
                clause_number="Art. 4.1.7",
                title="Ancho Mínimo de Puertas y Pasillos de Evacuación",
                content_text="Las puertas de recintos habitables deberán tener un ancho libre mínimo de 0.85 m.",
                summary="Ancho libre mínimo de puertas de 0.85 m.",
                scope_keywords=["puerta", "ancho libre", "vano"]
            )
            db.add(clause)
            db.commit()
            db.refresh(clause)

            criterion = NormativeCriterion(
                clause_id=clause.id,
                criterion_code="CRIT-OGUC-417-DOOR-MIN",
                name="Ancho libre mínimo de puerta habitable",
                target_entity="door",
                property_name="clear_width_m",
                operator="gte",
                threshold_value={"min": 0.85, "unit": "m"},
                severity="high"
            )
            db.add(criterion)
            db.commit()
            print(f"    NormativeDocument y criterio creados: {norm_code}")
        else:
            print(f"    NormativeDocument ya existe: {norm_code}")

        # 4. Template de viñeta de ejemplo (idempotente)
        tb_name = "Standard-A0-BottomRight"
        tb_tpl = db.query(TitleBlockTemplate).filter(TitleBlockTemplate.name == tb_name).first()
        if not tb_tpl:
            print(">>> 4. Creando TitleBlockTemplate de ejemplo...")
            tb_tpl = TitleBlockTemplate(
                name=tb_name,
                client_or_standard="ISO-5457-General",
                discipline="general",
                relative_position="bottom_right",
                expected_bbox=[0.72, 0.72, 0.99, 0.99],
                field_anchors={
                    "sheet_code": ["PLANO N°", "CODIGO", "LAMINA"],
                    "scale": ["ESCALA", "ESC."],
                    "revision": ["REV", "REVISION"]
                }
            )
            db.add(tb_tpl)
            db.commit()
            print(f"    TitleBlockTemplate creado: {tb_name}")
        else:
            print(f"    TitleBlockTemplate ya existe: {tb_name}")

        # 5. Proyecto de demostración (idempotente)
        demo_code = "PRJ-DEMO-001"
        project = db.query(Project).filter(Project.code == demo_code).first()
        if not project:
            print(">>> 5. Creando Proyecto de Demostración...")
            project = Project(
                organization_id=org.id,
                code=demo_code,
                name="Edificio Residencial Parque Central",
                description="Proyecto piloto para revisión automatizada de arquitectura e instalaciones.",
                client_name="Inmobiliaria Andina S.A.",
                discipline="architecture",
                settings={"min_confidence": 0.80, "target_standard": "OGUC-CHILE-2024"}
            )
            db.add(project)
            db.commit()
            db.refresh(project)

            v_a = ProjectVersion(
                project_id=project.id,
                version_tag="Rev A",
                description="Entrega inicial para revisión municipal",
                status="in_review"
            )
            db.add(v_a)
            db.commit()
            print(f"    Proyecto creado: {demo_code} (ID: {project.id})")
        else:
            print(f"    Proyecto ya existe: {demo_code}")

        # 6. Documento de ejemplo y lámina en document_memory (idempotente)
        sample_hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        document = db.query(Document).filter(Document.file_hash_sha256 == sample_hash).first()
        if not document:
            print(">>> 6. Creando Documento y Sheet de ejemplo en document_memory...")
            document = Document(
                organization_id=org.id,
                project_id=project.id,
                filename="PLANO_ARQUITECTURA_PLANTA_PISO_1.pdf",
                file_path="./data/raw/PLANO_ARQUITECTURA_PLANTA_PISO_1.pdf",
                file_hash_sha256=sample_hash,
                file_size_bytes=1048576,
                mime_type="application/pdf",
                status="ready",
                page_count=1
            )
            db.add(document)
            db.commit()
            db.refresh(document)

            sheet = DocumentSheet(
                document_id=document.id,
                sheet_number=1,
                sheet_code="ARQ-01",
                title="PLANTA PRIMER PISO Y ACCESOS",
                scale="1:50",
                revision="B",
                width_px=10500,
                height_px=7400,
                dpi=300,
                raster_image_path="./data/rendered/demo_sheet_1.png"
            )
            db.add(sheet)
            db.commit()
            db.refresh(sheet)

            # Insertar bloques OCR semilla sobre la lámina
            ocr_sample_1 = ExtractedText(
                sheet_id=sheet.id,
                text="PLANTA PRIMER PISO Y ACCESOS",
                clean_text="PLANTA PRIMER PISO Y ACCESOS",
                bbox=[7560.0, 5328.0, 9975.0, 5624.0],
                bbox_normalized=[0.72, 0.72, 0.95, 0.76],
                confidence=0.99,
                angle=0.0,
                source="vector_pdf"
            )
            ocr_sample_2 = ExtractedText(
                sheet_id=sheet.id,
                text="ESC. 1:50 - REV B",
                clean_text="ESC. 1:50 - REV B",
                bbox=[7560.0, 5772.0, 8925.0, 5994.0],
                bbox_normalized=[0.72, 0.78, 0.85, 0.81],
                confidence=0.97,
                angle=0.0,
                source="vector_pdf"
            )
            ocr_sample_3 = ExtractedText(
                sheet_id=sheet.id,
                text="PUERTA P-1 (ANCHO: 0.88m)",
                clean_text="PUERTA P-1 (ANCHO: 0.88m)",
                bbox=[2730.0, 2220.0, 3570.0, 2516.0],
                bbox_normalized=[0.26, 0.30, 0.34, 0.34],
                confidence=0.94,
                angle=0.0,
                source="vector_pdf"
            )
            db.add_all([ocr_sample_1, ocr_sample_2, ocr_sample_3])
            db.commit()
            print(f"    Documento creado con sheet ARQ-01 y 3 bloques OCR (Doc ID: {document.id})")
        else:
            print(f"    Documento ya existe (Doc ID: {document.id})")

        # 7. Corrida de revisión y hallazgo (idempotente)
        run_name = "Auditoría Inicial Rev A"
        review_run = db.query(ReviewRun).filter(
            ReviewRun.project_id == project.id,
            ReviewRun.run_name == run_name
        ).first()
        if not review_run:
            print(">>> 7. Creando ReviewRun y hallazgo demo en decision_memory...")
            review_run = ReviewRun(
                organization_id=org.id,
                project_id=project.id,
                run_name=run_name,
                status="completed",
                rules_applied_count=3,
                findings_count=1,
                execution_time_sec=0.45,
                summary_stats={"critical": 0, "high": 1, "medium": 0, "passed": 2}
            )
            db.add(review_run)
            db.commit()
            db.refresh(review_run)

        finding = db.query(RuleFinding).filter(RuleFinding.review_run_id == review_run.id).first()
        if not finding:
            sheet = db.query(DocumentSheet).join(Document).filter(Document.project_id == project.id).first()
            finding = RuleFinding(
                organization_id=org.id,
                review_run_id=review_run.id,
                document_id=document.id if document else sheet.document_id,
                sheet_id=sheet.id if sheet else None,
                rule_code="QAQC-TB-001",
                rule_name="Integridad de Campos Obligatorios en Viñeta",
                category="qa_qc",
                severity="high",
                confidence=1.0,
                title="Escala no especificada en viñeta",
                description="La viñeta no contiene el campo 'ESCALA' o su valor está vacío.",
                recommendation="Indicar la escala nominal del plano (ej: 1:50) en el casillero correspondiente de la viñeta.",
                status="open",
                bbox=[0.72, 0.72, 0.99, 0.99]
            )
            db.add(finding)
            db.commit()
            print(f"    Hallazgo demo creado (Finding ID: {finding.id})")
        else:
            print(f"    Hallazgo demo ya existe (Finding ID: {finding.id})")

        print("\n [OK] Seed completado con exito e idempotencia verificada.")
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
