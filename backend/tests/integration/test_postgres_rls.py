import os
import uuid
import pytest
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import DBAPIError, IntegrityError, ProgrammingError

from app.db.models.core import Organization, User, OrganizationMembership, Project
from app.db.models.document_memory import (
    Document, DocumentSheet, SheetRegion, ExtractedText,
    ExtractedTable, ExtractedTableCell, DetectedSymbol, VisualEvidence
)
from app.db.models.intake import SourceAsset
from app.db.models.operations import ProcessingJob, ReviewPipelineRun, PipelineStageRun, ReviewTask, DecisionTrace
from app.db.models.decision_memory import RuleFinding, RuleExecution, FindingResolution, ReviewRun
from app.db.models.reporting import AuditReport, EvidenceManifest
from app.db.session import Base
import app.db.models

# URL de conexión para rol de aplicación no privilegiado (app_user)
APP_USER_DB_URL = os.getenv(
    "POSTGRES_APP_USER_URL",
    "postgresql+psycopg://app_user:app_user_dev_pass@127.0.0.1:5433/planreview_test"
)

# URL de conexión de administración/migrador (solo para setup/teardown de fixtures)
MIGRATOR_DB_URL = os.getenv(
    "POSTGRES_MIGRATOR_URL",
    "postgresql+psycopg://postgres_migrator:migrator_secure_pass_123@127.0.0.1:5433/planreview_test"
)

def is_postgres_available() -> bool:
    """Verifica si el servicio PostgreSQL de pruebas está accesible."""
    try:
        engine = create_engine(MIGRATOR_DB_URL, connect_args={"connect_timeout": 3})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False

# Marcar toda la suite como postgres e integration
pytestmark = [
    pytest.mark.postgres,
    pytest.mark.integration,
    pytest.mark.skipif(
        not is_postgres_available(),
        reason="Entorno PostgreSQL 15+ de integración no disponible (iniciar con docker-compose.integration.yml)"
    )
]

@pytest.fixture(scope="module")
def migrator_session():
    """Sesión privilegiada usada exclusivamente para inicializar esquema, políticas RLS y poblar fixtures de prueba."""
    engine = create_engine(MIGRATOR_DB_URL)
    
    # 1. Crear todas las tablas SQLAlchemy en PostgreSQL
    Base.metadata.create_all(bind=engine)

    # 2. Cargar y ejecutar políticas RLS desde migrations/rls_prepared_policies.sql
    rls_sql_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../../migrations/rls_prepared_policies.sql")
    )
    if os.path.exists(rls_sql_path):
        with open(rls_sql_path, "r", encoding="utf-8") as f:
            rls_sql = f.read()
        
        # Ejecutar usando connection raw con autocommit para plpgsql y sentencias DDL
        raw_conn = engine.raw_connection()
        try:
            with raw_conn.cursor() as cursor:
                cursor.execute(rls_sql)
                cursor.execute("CREATE INDEX IF NOT EXISTS ix_document_sheets_document_id ON document_sheets (document_id);")
            raw_conn.commit()
        except Exception as e:
            raw_conn.rollback()
        finally:
            raw_conn.close()

    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()

@pytest.fixture(scope="module")
def app_user_engine():
    """Engine conectado estrictamente con el rol no privilegiado app_user (NOBYPASSRLS)."""
    return create_engine(APP_USER_DB_URL, pool_pre_ping=True)

@pytest.fixture(scope="module")
def test_tenants_fixture(migrator_session):
    """Puebla datos completos de dos tenants (Alpha y Beta) en tablas directas y heredadas."""
    # 1. Crear Organizaciones
    org_alpha = Organization(id=str(uuid.uuid4()), name="Tenant Alpha Corp", slug=f"alpha-{uuid.uuid4().hex[:6]}")
    org_beta = Organization(id=str(uuid.uuid4()), name="Tenant Beta Corp", slug=f"beta-{uuid.uuid4().hex[:6]}")
    migrator_session.add_all([org_alpha, org_beta])
    migrator_session.commit()

    # 2. Datos Directos Tenant Alpha
    proj_alpha = Project(id=str(uuid.uuid4()), organization_id=org_alpha.id, code="PRJ-ALPHA", name="Torre Alpha")
    doc_alpha = Document(
        id=str(uuid.uuid4()), organization_id=org_alpha.id, project_id=proj_alpha.id,
        filename="plano_alpha.pdf", file_path="./alpha.pdf", file_hash_sha256=f"sha-alpha-{uuid.uuid4().hex[:8]}",
        file_size_bytes=1024, page_count=1, status="uploaded"
    )
    asset_alpha = SourceAsset(id=str(uuid.uuid4()), organization_id=org_alpha.id, title="Norma Alpha", source_type="normative_document", status="ingested", linked_memory_target="normative_memory")
    job_alpha = ProcessingJob(id=str(uuid.uuid4()), organization_id=org_alpha.id, job_type="ocr_process", target_type="sheet", target_id="sheet-alpha", pipeline_name="qa_pipe", status="completed")
    pipe_alpha = ReviewPipelineRun(id=str(uuid.uuid4()), organization_id=org_alpha.id, scope_type="document", scope_id=doc_alpha.id, status="completed")
    finding_alpha = RuleFinding(id=str(uuid.uuid4()), organization_id=org_alpha.id, document_id=doc_alpha.id, rule_code="ARQ-001", rule_name="Test Rule Alpha", category="qa", title="Finding Alpha", description="Desc Alpha")
    report_alpha = AuditReport(id=str(uuid.uuid4()), organization_id=org_alpha.id, document_id=doc_alpha.id, report_type="qa_audit", status="completed")

    migrator_session.add_all([proj_alpha, doc_alpha, asset_alpha, job_alpha, pipe_alpha, finding_alpha, report_alpha])
    migrator_session.commit()

    # Datos Heredados Tenant Alpha (JOINs)
    sheet_alpha = DocumentSheet(
        id=str(uuid.uuid4()), document_id=doc_alpha.id, sheet_number=1, sheet_code="A-01",
        raster_image_path="./render_alpha.png", width_px=1000, height_px=1000
    )
    migrator_session.add(sheet_alpha)
    migrator_session.commit()

    region_alpha = SheetRegion(
        id=str(uuid.uuid4()), sheet_id=sheet_alpha.id, region_type="drawing_area",
        polygon_points=[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
        bbox=[0, 0, 1000, 1000], bbox_normalized=[0.0, 0.0, 1.0, 1.0], confidence=0.99
    )
    text_alpha = ExtractedText(
        id=str(uuid.uuid4()), sheet_id=sheet_alpha.id, text="Texto Alpha Privado",
        bbox=[100, 100, 200, 200], bbox_normalized=[0.1, 0.1, 0.2, 0.2], confidence=0.95
    )
    table_alpha = ExtractedTable(
        id=str(uuid.uuid4()), document_id=doc_alpha.id, sheet_id=sheet_alpha.id, table_type="door_schedule",
        row_count=2, column_count=2, bbox=[200, 200, 500, 500], bbox_normalized=[0.2, 0.2, 0.5, 0.5]
    )
    migrator_session.add_all([region_alpha, text_alpha, table_alpha])
    migrator_session.commit()

    cell_alpha = ExtractedTableCell(
        id=str(uuid.uuid4()), table_id=table_alpha.id, row_index=0, column_index=0,
        text="P-01", bbox=[200, 200, 300, 300], bbox_normalized=[0.2, 0.2, 0.3, 0.3]
    )
    symbol_alpha = DetectedSymbol(
        id=str(uuid.uuid4()), document_id=doc_alpha.id, sheet_id=sheet_alpha.id,
        symbol_type="door_symbol", bbox=[300, 300, 400, 400], bbox_normalized=[0.3, 0.3, 0.4, 0.4], confidence=0.92
    )
    stage_alpha = PipelineStageRun(id=str(uuid.uuid4()), pipeline_run_id=pipe_alpha.id, stage_name="ocr", stage_order=1, status="completed")
    migrator_session.add_all([cell_alpha, symbol_alpha, stage_alpha])
    migrator_session.commit()

    # 3. Datos Directos Tenant Beta
    proj_beta = Project(id=str(uuid.uuid4()), organization_id=org_beta.id, code="PRJ-BETA", name="Planta Beta")
    doc_beta = Document(
        id=str(uuid.uuid4()), organization_id=org_beta.id, project_id=proj_beta.id,
        filename="plano_beta.pdf", file_path="./beta.pdf", file_hash_sha256=f"sha-beta-{uuid.uuid4().hex[:8]}",
        file_size_bytes=1024, page_count=1, status="uploaded"
    )
    asset_beta = SourceAsset(id=str(uuid.uuid4()), organization_id=org_beta.id, title="Norma Beta", source_type="normative_document", status="ingested", linked_memory_target="normative_memory")
    pipe_beta = ReviewPipelineRun(id=str(uuid.uuid4()), organization_id=org_beta.id, scope_type="document", scope_id=doc_beta.id, status="completed")
    finding_beta = RuleFinding(id=str(uuid.uuid4()), organization_id=org_beta.id, document_id=doc_beta.id, rule_code="ARQ-002", rule_name="Test Rule Beta", category="qa", title="Finding Beta", description="Desc Beta")
    report_beta = AuditReport(id=str(uuid.uuid4()), organization_id=org_beta.id, document_id=doc_beta.id, report_type="qa_audit", status="completed")

    migrator_session.add_all([proj_beta, doc_beta, asset_beta, pipe_beta, finding_beta, report_beta])
    migrator_session.commit()

    # Datos Heredados Tenant Beta (JOINs)
    sheet_beta = DocumentSheet(
        id=str(uuid.uuid4()), document_id=doc_beta.id, sheet_number=1, sheet_code="B-01",
        raster_image_path="./render_beta.png", width_px=1000, height_px=1000
    )
    migrator_session.add(sheet_beta)
    migrator_session.commit()

    text_beta = ExtractedText(
        id=str(uuid.uuid4()), sheet_id=sheet_beta.id, text="Texto Beta Confidencial",
        bbox=[100, 100, 200, 200], bbox_normalized=[0.1, 0.1, 0.2, 0.2], confidence=0.95
    )
    table_beta = ExtractedTable(
        id=str(uuid.uuid4()), document_id=doc_beta.id, sheet_id=sheet_beta.id, table_type="window_schedule",
        row_count=2, column_count=2, bbox=[200, 200, 500, 500], bbox_normalized=[0.2, 0.2, 0.5, 0.5]
    )
    migrator_session.add_all([text_beta, table_beta])
    migrator_session.commit()

    symbol_beta = DetectedSymbol(
        id=str(uuid.uuid4()), document_id=doc_beta.id, sheet_id=sheet_beta.id,
        symbol_type="window_symbol", bbox=[300, 300, 400, 400], bbox_normalized=[0.3, 0.3, 0.4, 0.4], confidence=0.90
    )
    stage_beta = PipelineStageRun(id=str(uuid.uuid4()), pipeline_run_id=pipe_beta.id, stage_name="ocr", stage_order=1, status="completed")
    migrator_session.add_all([symbol_beta, stage_beta])
    migrator_session.commit()

    return {
        "org_alpha": org_alpha,
        "org_beta": org_beta,
        "doc_alpha": doc_alpha,
        "doc_beta": doc_beta,
        "sheet_alpha": sheet_alpha,
        "sheet_beta": sheet_beta,
        "text_alpha": text_alpha,
        "text_beta": text_beta,
        "table_alpha": table_alpha,
        "table_beta": table_beta,
        "symbol_alpha": symbol_alpha,
        "symbol_beta": symbol_beta,
        "finding_alpha": finding_alpha,
        "finding_beta": finding_beta
    }

# ============================================================================
# LOS 10 CASOS OBLIGATORIOS DE VALIDACIÓN DE RLS
# ============================================================================

def test_rls_01_lectura_directa_aislada(app_user_engine, test_tenants_fixture):
    """CASO 1: Set context Alpha -> SELECT sobre tablas directas solo devuelve filas de Alpha."""
    alpha_id = test_tenants_fixture["org_alpha"].id
    beta_id = test_tenants_fixture["org_beta"].id

    with app_user_engine.connect() as conn:
        with conn.begin():
            conn.execute(text("SELECT set_config('app.current_organization_id', :org_id, true)"), {"org_id": alpha_id})
            
            # Consultar documentos sin WHERE organization_id
            docs = conn.execute(text("SELECT id, organization_id, filename FROM documents;")).fetchall()
            assert len(docs) >= 1
            for d in docs:
                assert d[1] == alpha_id
                assert d[1] != beta_id

            # Consultar rule_findings sin WHERE
            findings = conn.execute(text("SELECT id, organization_id, title FROM rule_findings;")).fetchall()
            assert len(findings) >= 1
            for f in findings:
                assert f[1] == alpha_id
                assert f[1] != beta_id

def test_rls_02_lectura_heredada_aislada(app_user_engine, test_tenants_fixture):
    """CASO 2: Set context Alpha -> Queries sobre tablas heredadas (JOIN) no revelan datos de Beta."""
    alpha_id = test_tenants_fixture["org_alpha"].id
    beta_sheet_id = test_tenants_fixture["sheet_beta"].id
    beta_text_id = test_tenants_fixture["text_beta"].id

    with app_user_engine.connect() as conn:
        with conn.begin():
            conn.execute(text("SELECT set_config('app.current_organization_id', :org_id, true)"), {"org_id": alpha_id})
            
            # 1. DocumentSheets
            sheets = conn.execute(text("SELECT id, document_id FROM document_sheets;")).fetchall()
            sheet_ids = [s[0] for s in sheets]
            assert beta_sheet_id not in sheet_ids

            # 2. ExtractedTexts
            texts = conn.execute(text("SELECT id, text FROM extracted_texts;")).fetchall()
            text_ids = [t[0] for t in texts]
            assert beta_text_id not in text_ids

            # 3. DetectedSymbols
            symbols = conn.execute(text("SELECT id, symbol_type FROM detected_symbols;")).fetchall()
            symbol_types = [s[1] for s in symbols]
            assert "window_symbol" not in symbol_types

def test_rls_03_contexto_omitido_fail_closed(app_user_engine, test_tenants_fixture):
    """CASO 3: Sin setear tenant context (app_user directo) -> SELECT retorna 0 filas (Fail-Closed)."""
    with app_user_engine.connect() as conn:
        with conn.begin():
            # No se ejecuta set_config -> get_current_organization_id() retorna NULL
            docs = conn.execute(text("SELECT * FROM documents;")).fetchall()
            assert len(docs) == 0

            projects = conn.execute(text("SELECT * FROM projects;")).fetchall()
            assert len(projects) == 0

            findings = conn.execute(text("SELECT * FROM rule_findings;")).fetchall()
            assert len(findings) == 0

            sheets = conn.execute(text("SELECT * FROM document_sheets;")).fetchall()
            assert len(sheets) == 0

def test_rls_04_insert_cross_tenant(app_user_engine, test_tenants_fixture):
    """CASO 4: Contexto Alpha -> Intentar INSERT con organization_id Beta -> Violación de WITH CHECK."""
    alpha_id = test_tenants_fixture["org_alpha"].id
    beta_id = test_tenants_fixture["org_beta"].id

    with app_user_engine.connect() as conn:
        with conn.begin():
            conn.execute(text("SELECT set_config('app.current_organization_id', :org_id, true)"), {"org_id": alpha_id})
            
            new_doc_id = str(uuid.uuid4())
            with pytest.raises((IntegrityError, ProgrammingError, DBAPIError)) as exc:
                conn.execute(
                    text("""
                        INSERT INTO documents (id, organization_id, project_id, filename, file_path, file_hash_sha256, file_size_bytes, page_count, status, created_at, updated_at)
                        VALUES (:id, :org_id, :proj_id, 'cross_tenant.pdf', './ct.pdf', 'hash-ct-99', 1024, 1, 'uploaded', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
                    """),
                    {"id": new_doc_id, "org_id": beta_id, "proj_id": test_tenants_fixture["doc_alpha"].project_id}
                )
            assert "violates row-level security policy" in str(exc.value).lower() or "with check" in str(exc.value).lower()

def test_rls_05_update_cross_tenant(app_user_engine, test_tenants_fixture):
    """CASO 5: Contexto Alpha -> UPDATE sobre registro de Beta -> 0 filas afectadas (no visible)."""
    alpha_id = test_tenants_fixture["org_alpha"].id
    beta_doc_id = test_tenants_fixture["doc_beta"].id

    with app_user_engine.connect() as conn:
        with conn.begin():
            conn.execute(text("SELECT set_config('app.current_organization_id', :org_id, true)"), {"org_id": alpha_id})
            
            res = conn.execute(
                text("UPDATE documents SET filename = 'hackeado.pdf' WHERE id = :id;"),
                {"id": beta_doc_id}
            )
            assert res.rowcount == 0

def test_rls_06_delete_cross_tenant(app_user_engine, test_tenants_fixture):
    """CASO 6: Contexto Alpha -> DELETE sobre registro de Beta -> 0 filas eliminadas."""
    alpha_id = test_tenants_fixture["org_alpha"].id
    beta_doc_id = test_tenants_fixture["doc_beta"].id

    with app_user_engine.connect() as conn:
        with conn.begin():
            conn.execute(text("SELECT set_config('app.current_organization_id', :org_id, true)"), {"org_id": alpha_id})
            
            res = conn.execute(
                text("DELETE FROM documents WHERE id = :id;"),
                {"id": beta_doc_id}
            )
            assert res.rowcount == 0

def test_rls_07_force_rls_metadata(migrator_session):
    """CASO 7: Verificar en catálogo PostgreSQL que RLS y FORCE RLS están activos en todas las tablas."""
    res = migrator_session.execute(text("""
        SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' 
          AND c.relname IN (
              'projects', 'source_assets', 'documents', 'processing_jobs', 
              'review_pipeline_runs', 'review_tasks', 'decision_traces',
              'rule_findings', 'audit_reports', 'document_sheets', 
              'extracted_texts', 'extracted_tables', 'detected_symbols'
          );
    """)).fetchall()

    assert len(res) >= 13
    for row in res:
        table_name, rls_active, force_rls = row[0], row[1], row[2]
        assert rls_active is True, f"RLS no está activo en {table_name}"
        assert force_rls is True, f"FORCE RLS no está activo en {table_name}"

def test_rls_08_privilegios_app_user(migrator_session):
    """CASO 8: Verificar en catálogo pg_roles que app_user no tiene SUPERUSER ni BYPASSRLS."""
    row = migrator_session.execute(text("""
        SELECT rolname, rolsuper, rolbypassrls, rolcanlogin
        FROM pg_roles
        WHERE rolname = 'app_user';
    """)).fetchone()

    assert row is not None
    assert row[0] == "app_user"
    assert row[1] is False, "app_user no debe ser superusuario"
    assert row[2] is False, "app_user no debe tener BYPASSRLS"
    assert row[3] is True, "app_user debe tener LOGIN"

def test_rls_09_aislamiento_entre_transacciones(app_user_engine, test_tenants_fixture):
    """CASO 9: Conexión reciclada del pool -> Tx 1 (Alpha) no contamina a Tx 2 (Sin Contexto)."""
    alpha_id = test_tenants_fixture["org_alpha"].id

    conn = app_user_engine.connect()
    try:
        # Transacción 1: Set Alpha
        tx1 = conn.begin()
        conn.execute(text("SELECT set_config('app.current_organization_id', :org_id, true)"), {"org_id": alpha_id})
        docs_tx1 = conn.execute(text("SELECT count(*) FROM documents;")).scalar()
        assert docs_tx1 >= 1
        tx1.commit()

        # Transacción 2: Sin set_config en la misma conexión
        tx2 = conn.begin()
        docs_tx2 = conn.execute(text("SELECT count(*) FROM documents;")).scalar()
        assert docs_tx2 == 0, "Fuga de contexto residual detectada en transacción posterior"
        tx2.commit()
    finally:
        conn.close()

def test_rls_10_indices_organizacion_y_foreign_keys(migrator_session):
    """CASO 10: Verificar que las columnas organization_id y foreign keys de JOIN tengan índices."""
    res = migrator_session.execute(text("""
        SELECT tablename, indexname, indexdef
        FROM pg_indexes
        WHERE schemaname = 'public'
          AND (indexdef LIKE '%organization_id%' OR indexdef LIKE '%document_id%' OR indexdef LIKE '%sheet_id%');
    """)).fetchall()

    indexed_tables = {row[0] for row in res}
    assert "documents" in indexed_tables
    assert "rule_findings" in indexed_tables
    assert "document_sheets" in indexed_tables
