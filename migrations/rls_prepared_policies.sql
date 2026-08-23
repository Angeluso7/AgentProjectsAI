-- ============================================================================
-- BLUEPRINT: PostgreSQL Row-Level Security (RLS) - Prepared / Defense in Depth
-- ============================================================================
-- Requisitos Críticos de Seguridad para Entornos PostgreSQL 15+:
-- 1. ENABLE ROW LEVEL SECURITY en todas las tablas directas y heredadas.
-- 2. FORCE ROW LEVEL SECURITY para que aplique incluso al owner de la tabla.
-- 3. Políticas simétricas USING (SELECT/UPDATE/DELETE) y WITH CHECK (INSERT/UPDATE).
-- 4. Rol de aplicación no privilegiado (app_user) con NOBYPASSRLS y NOSUPERUSER.
-- ============================================================================

-- 1. Creación/Aseguramiento del Rol de Aplicación (NOBYPASSRLS)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_user') THEN
        CREATE ROLE app_user WITH LOGIN PASSWORD 'app_user_dev_pass' NOBYPASSRLS NOSUPERUSER NOCREATEDB NOCREATEROLE;
    ELSE
        ALTER ROLE app_user NOBYPASSRLS NOSUPERUSER;
    END IF;
END
$$;

-- Otorgar permisos DML al rol app_user sobre el esquema public
GRANT USAGE ON SCHEMA public TO app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO app_user;

-- 2. Función auxiliar de contexto (retorna NULL si no está seteado -> Fail-Closed)
CREATE OR REPLACE FUNCTION get_current_organization_id() RETURNS TEXT AS $$
BEGIN
    RETURN NULLIF(current_setting('app.current_organization_id', true), '');
END;
$$ LANGUAGE plpgsql STABLE SECURITY DEFINER;

-- ----------------------------------------------------------------------------
-- 3. TABLAS DIRECTAS (con columna organization_id directa)
-- ----------------------------------------------------------------------------

-- A. projects
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE projects FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_projects ON projects;
CREATE POLICY tenant_isolation_projects ON projects
    FOR ALL TO app_user
    USING (organization_id = get_current_organization_id())
    WITH CHECK (organization_id = get_current_organization_id());

-- B. source_assets
ALTER TABLE source_assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE source_assets FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_source_assets ON source_assets;
CREATE POLICY tenant_isolation_source_assets ON source_assets
    FOR ALL TO app_user
    USING (organization_id = get_current_organization_id())
    WITH CHECK (organization_id = get_current_organization_id());

-- C. documents
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_documents ON documents;
CREATE POLICY tenant_isolation_documents ON documents
    FOR ALL TO app_user
    USING (organization_id = get_current_organization_id())
    WITH CHECK (organization_id = get_current_organization_id());

-- D. processing_jobs
ALTER TABLE processing_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE processing_jobs FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_processing_jobs ON processing_jobs;
CREATE POLICY tenant_isolation_processing_jobs ON processing_jobs
    FOR ALL TO app_user
    USING (organization_id = get_current_organization_id())
    WITH CHECK (organization_id = get_current_organization_id());

-- E. review_pipeline_runs
ALTER TABLE review_pipeline_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE review_pipeline_runs FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_review_pipeline_runs ON review_pipeline_runs;
CREATE POLICY tenant_isolation_review_pipeline_runs ON review_pipeline_runs
    FOR ALL TO app_user
    USING (organization_id = get_current_organization_id())
    WITH CHECK (organization_id = get_current_organization_id());

-- F. review_tasks
ALTER TABLE review_tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE review_tasks FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_review_tasks ON review_tasks;
CREATE POLICY tenant_isolation_review_tasks ON review_tasks
    FOR ALL TO app_user
    USING (organization_id = get_current_organization_id())
    WITH CHECK (organization_id = get_current_organization_id());

-- G. decision_traces
ALTER TABLE decision_traces ENABLE ROW LEVEL SECURITY;
ALTER TABLE decision_traces FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_decision_traces ON decision_traces;
CREATE POLICY tenant_isolation_decision_traces ON decision_traces
    FOR ALL TO app_user
    USING (organization_id = get_current_organization_id())
    WITH CHECK (organization_id = get_current_organization_id());

-- H. review_runs
ALTER TABLE review_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE review_runs FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_review_runs ON review_runs;
CREATE POLICY tenant_isolation_review_runs ON review_runs
    FOR ALL TO app_user
    USING (organization_id = get_current_organization_id())
    WITH CHECK (organization_id = get_current_organization_id());

-- I. rule_findings
ALTER TABLE rule_findings ENABLE ROW LEVEL SECURITY;
ALTER TABLE rule_findings FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_rule_findings ON rule_findings;
CREATE POLICY tenant_isolation_rule_findings ON rule_findings
    FOR ALL TO app_user
    USING (organization_id = get_current_organization_id())
    WITH CHECK (organization_id = get_current_organization_id());

-- J. audit_reports
ALTER TABLE audit_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_reports FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_audit_reports ON audit_reports;
CREATE POLICY tenant_isolation_audit_reports ON audit_reports
    FOR ALL TO app_user
    USING (organization_id = get_current_organization_id())
    WITH CHECK (organization_id = get_current_organization_id());

-- K. evidence_manifests
ALTER TABLE evidence_manifests ENABLE ROW LEVEL SECURITY;
ALTER TABLE evidence_manifests FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_evidence_manifests ON evidence_manifests;
CREATE POLICY tenant_isolation_evidence_manifests ON evidence_manifests
    FOR ALL TO app_user
    USING (organization_id = get_current_organization_id())
    WITH CHECK (organization_id = get_current_organization_id());

-- L. audit_logs
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_audit_logs ON audit_logs;
CREATE POLICY tenant_isolation_audit_logs ON audit_logs
    FOR ALL TO app_user
    USING (organization_id = get_current_organization_id())
    WITH CHECK (organization_id = get_current_organization_id());

-- ----------------------------------------------------------------------------
-- 4. TABLAS HEREDADAS (con JOIN a documents / pipeline_runs / rule_findings)
-- ----------------------------------------------------------------------------

-- A. document_sheets (vía documents.id)
ALTER TABLE document_sheets ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_sheets FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_document_sheets ON document_sheets;
CREATE POLICY tenant_isolation_document_sheets ON document_sheets
    FOR ALL TO app_user
    USING (document_id IN (SELECT id FROM documents WHERE organization_id = get_current_organization_id()))
    WITH CHECK (document_id IN (SELECT id FROM documents WHERE organization_id = get_current_organization_id()));

-- B. sheet_regions (vía document_sheets -> documents.id)
ALTER TABLE sheet_regions ENABLE ROW LEVEL SECURITY;
ALTER TABLE sheet_regions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_sheet_regions ON sheet_regions;
CREATE POLICY tenant_isolation_sheet_regions ON sheet_regions
    FOR ALL TO app_user
    USING (sheet_id IN (
        SELECT s.id FROM document_sheets s 
        JOIN documents d ON s.document_id = d.id 
        WHERE d.organization_id = get_current_organization_id()
    ))
    WITH CHECK (sheet_id IN (
        SELECT s.id FROM document_sheets s 
        JOIN documents d ON s.document_id = d.id 
        WHERE d.organization_id = get_current_organization_id()
    ));

-- C. extracted_texts (vía document_sheets -> documents.id)
ALTER TABLE extracted_texts ENABLE ROW LEVEL SECURITY;
ALTER TABLE extracted_texts FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_extracted_texts ON extracted_texts;
CREATE POLICY tenant_isolation_extracted_texts ON extracted_texts
    FOR ALL TO app_user
    USING (sheet_id IN (
        SELECT s.id FROM document_sheets s 
        JOIN documents d ON s.document_id = d.id 
        WHERE d.organization_id = get_current_organization_id()
    ))
    WITH CHECK (sheet_id IN (
        SELECT s.id FROM document_sheets s 
        JOIN documents d ON s.document_id = d.id 
        WHERE d.organization_id = get_current_organization_id()
    ));

-- D. title_block_extractions (vía document_sheets -> documents.id)
ALTER TABLE title_block_extractions ENABLE ROW LEVEL SECURITY;
ALTER TABLE title_block_extractions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_title_block_extractions ON title_block_extractions;
CREATE POLICY tenant_isolation_title_block_extractions ON title_block_extractions
    FOR ALL TO app_user
    USING (sheet_id IN (
        SELECT s.id FROM document_sheets s 
        JOIN documents d ON s.document_id = d.id 
        WHERE d.organization_id = get_current_organization_id()
    ))
    WITH CHECK (sheet_id IN (
        SELECT s.id FROM document_sheets s 
        JOIN documents d ON s.document_id = d.id 
        WHERE d.organization_id = get_current_organization_id()
    ));

-- E. extracted_tables (vía document_sheets -> documents.id)
ALTER TABLE extracted_tables ENABLE ROW LEVEL SECURITY;
ALTER TABLE extracted_tables FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_extracted_tables ON extracted_tables;
CREATE POLICY tenant_isolation_extracted_tables ON extracted_tables
    FOR ALL TO app_user
    USING (sheet_id IN (
        SELECT s.id FROM document_sheets s 
        JOIN documents d ON s.document_id = d.id 
        WHERE d.organization_id = get_current_organization_id()
    ))
    WITH CHECK (sheet_id IN (
        SELECT s.id FROM document_sheets s 
        JOIN documents d ON s.document_id = d.id 
        WHERE d.organization_id = get_current_organization_id()
    ));

-- F. extracted_table_cells (vía extracted_tables -> document_sheets -> documents.id)
ALTER TABLE extracted_table_cells ENABLE ROW LEVEL SECURITY;
ALTER TABLE extracted_table_cells FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_extracted_table_cells ON extracted_table_cells;
CREATE POLICY tenant_isolation_extracted_table_cells ON extracted_table_cells
    FOR ALL TO app_user
    USING (table_id IN (
        SELECT t.id FROM extracted_tables t
        JOIN document_sheets s ON t.sheet_id = s.id
        JOIN documents d ON s.document_id = d.id
        WHERE d.organization_id = get_current_organization_id()
    ))
    WITH CHECK (table_id IN (
        SELECT t.id FROM extracted_tables t
        JOIN document_sheets s ON t.sheet_id = s.id
        JOIN documents d ON s.document_id = d.id
        WHERE d.organization_id = get_current_organization_id()
    ));

-- G. detected_symbols (vía document_sheets -> documents.id)
ALTER TABLE detected_symbols ENABLE ROW LEVEL SECURITY;
ALTER TABLE detected_symbols FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_detected_symbols ON detected_symbols;
CREATE POLICY tenant_isolation_detected_symbols ON detected_symbols
    FOR ALL TO app_user
    USING (sheet_id IN (
        SELECT s.id FROM document_sheets s 
        JOIN documents d ON s.document_id = d.id 
        WHERE d.organization_id = get_current_organization_id()
    ))
    WITH CHECK (sheet_id IN (
        SELECT s.id FROM document_sheets s 
        JOIN documents d ON s.document_id = d.id 
        WHERE d.organization_id = get_current_organization_id()
    ));

-- H. visual_evidences (vía document_sheets -> documents.id)
ALTER TABLE visual_evidences ENABLE ROW LEVEL SECURITY;
ALTER TABLE visual_evidences FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_visual_evidences ON visual_evidences;
CREATE POLICY tenant_isolation_visual_evidences ON visual_evidences
    FOR ALL TO app_user
    USING (sheet_id IN (
        SELECT s.id FROM document_sheets s 
        JOIN documents d ON s.document_id = d.id 
        WHERE d.organization_id = get_current_organization_id()
    ))
    WITH CHECK (sheet_id IN (
        SELECT s.id FROM document_sheets s 
        JOIN documents d ON s.document_id = d.id 
        WHERE d.organization_id = get_current_organization_id()
    ));

-- I. pipeline_stage_runs (vía review_pipeline_runs.id)
ALTER TABLE pipeline_stage_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE pipeline_stage_runs FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_pipeline_stage_runs ON pipeline_stage_runs;
CREATE POLICY tenant_isolation_pipeline_stage_runs ON pipeline_stage_runs
    FOR ALL TO app_user
    USING (pipeline_run_id IN (SELECT id FROM review_pipeline_runs WHERE organization_id = get_current_organization_id()))
    WITH CHECK (pipeline_run_id IN (SELECT id FROM review_pipeline_runs WHERE organization_id = get_current_organization_id()));

-- J. rule_executions (vía documents.id)
ALTER TABLE rule_executions ENABLE ROW LEVEL SECURITY;
ALTER TABLE rule_executions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_rule_executions ON rule_executions;
CREATE POLICY tenant_isolation_rule_executions ON rule_executions
    FOR ALL TO app_user
    USING (document_id IN (SELECT id FROM documents WHERE organization_id = get_current_organization_id()))
    WITH CHECK (document_id IN (SELECT id FROM documents WHERE organization_id = get_current_organization_id()));

-- K. finding_resolutions (vía rule_findings.id)
ALTER TABLE finding_resolutions ENABLE ROW LEVEL SECURITY;
ALTER TABLE finding_resolutions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_finding_resolutions ON finding_resolutions;
CREATE POLICY tenant_isolation_finding_resolutions ON finding_resolutions
    FOR ALL TO app_user
    USING (finding_id IN (SELECT id FROM rule_findings WHERE organization_id = get_current_organization_id()))
    WITH CHECK (finding_id IN (SELECT id FROM rule_findings WHERE organization_id = get_current_organization_id()));

-- L. finding_evidences (vía rule_findings.id)
ALTER TABLE finding_evidences ENABLE ROW LEVEL SECURITY;
ALTER TABLE finding_evidences FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_finding_evidences ON finding_evidences;
CREATE POLICY tenant_isolation_finding_evidences ON finding_evidences
    FOR ALL TO app_user
    USING (finding_id IN (SELECT id FROM rule_findings WHERE organization_id = get_current_organization_id()))
    WITH CHECK (finding_id IN (SELECT id FROM rule_findings WHERE organization_id = get_current_organization_id()));
