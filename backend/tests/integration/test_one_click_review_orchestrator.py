import os
import uuid
import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import SessionLocal
from app.db.models.core import User, Organization, OrganizationMembership, Project
from app.db.models.decision_memory import (
    ReviewDiscipline,
    ReviewTopic,
    RuleDefinition,
    RuleApplicability,
    RuleExecutionDependency,
    ReviewRun,
    ReviewRunDocument,
    ReviewRunStep,
    RuleExecution,
    RuleFinding,
    ReviewReport
)
from app.db.models.document_memory import (
    Document,
    DocumentSheet,
    DetectedSymbol,
    ExtractedTable,
    ExtractedTableCell,
    TitleBlockExtraction
)
import json
from app.core.security import create_access_token
from app.db.models.template_memory import SymbolTemplate
from app.db.models.symbol_catalog import SymbolTemplateVersion
from app.services.review.taxonomy_service import TaxonomyService
from app.services.review.orchestrator import ReviewOrchestrator
from app.services.review.export_service import ReviewExportService


@pytest.fixture
def review_env():
    db: Session = SessionLocal()
    suffix = str(uuid.uuid4())[:8]

    org = Organization(id=f"org-{suffix}", name=f"Org {suffix}", slug=f"org-{suffix}")
    user = User(
        id=f"user-{suffix}",
        email=f"auditor-{suffix}@test.com",
        display_name=f"Auditor {suffix}",
        password_hash="fake",
        is_active=True
    )
    db.add_all([org, user])
    db.commit()

    mem = OrganizationMembership(
        organization_id=org.id,
        user_id=user.id,
        role="admin",
        status="active"
    )
    db.add(mem)
    db.commit()

    # Proyectos
    project_a = Project(
        id=f"prj-a-{suffix}",
        organization_id=org.id,
        name=f"Refinería Bío-Bío {suffix}",
        code=f"PRJ-A-{suffix[:4].upper()}",
        discipline="piping"
    )
    project_b = Project(
        id=f"prj-b-{suffix}",
        organization_id=org.id,
        name=f"Planta Concentradora {suffix}",
        code=f"PRJ-B-{suffix[:4].upper()}",
        discipline="piping"
    )
    db.add_all([project_a, project_b])
    db.commit()

    # Documentos
    doc_a = Document(
        id=f"doc-a-{suffix}",
        project_id=project_a.id,
        organization_id=org.id,
        filename="001-PID-PROCESO-01.pdf",
        file_path=f"/tmp/001-PID-PROCESO-01-{suffix}.pdf",
        file_hash_sha256=f"hash-a-{suffix}",
        file_size_bytes=102400,
        page_count=1,
        status="ready"
    )
    doc_b = Document(
        id=f"doc-b-{suffix}",
        project_id=project_b.id,
        organization_id=org.id,
        filename="002-PID-VENTILACION-01.pdf",
        file_path=f"/tmp/002-PID-VENTILACION-01-{suffix}.pdf",
        file_hash_sha256=f"hash-b-{suffix}",
        file_size_bytes=204800,
        page_count=1,
        status="ready"
    )
    db.add_all([doc_a, doc_b])
    db.commit()

    # Lámina en doc_a
    sheet_a = DocumentSheet(
        id=f"sheet-a-{suffix}",
        document_id=doc_a.id,
        sheet_number=1,
        title="DIAGRAMA P&ID LINEA 100",
        width_px=1189,
        height_px=841,
        width_mm=1189.0,
        height_mm=841.0
    )
    db.add(sheet_a)
    db.commit()

    # Viñeta técnica en sheet_a
    tb_a = TitleBlockExtraction(
        id=f"tb-a-{suffix}",
        sheet_id=sheet_a.id,
        sheet_code="PID-1001-REV0",
        sheet_title="DIAGRAMA P&ID REFINERIA",
        revision="0"
    )
    db.add(tb_a)

    # Plantilla canónica activa aprobada en catálogo de producción
    prod_template = SymbolTemplate(
        id=f"tmpl-gate-{suffix}",
        symbol_class="gate_valve",
        canonical_code=f"PIP-VALVE-GATE-{suffix[:4].upper()}",
        canonical_name="Gate Valve",
        display_name="Válvula de Compuerta Canónica ISA-5.1",
        discipline="piping",
        status="active",
        is_active_for_detection=True
    )
    db.add(prod_template)
    db.flush()

    prod_version = SymbolTemplateVersion(
        id=f"ver-gate-{suffix}",
        symbol_template_id=prod_template.id,
        version_number=1,
        approval_status="approved",
        source_kind="normative_document",
        approved_by="lead_auditor@test.com",
        approved_at=datetime.utcnow()
    )
    db.add(prod_version)

    # Símbolos en sheet_a
    sym_1 = DetectedSymbol(
        id=f"sym-1-{suffix}",
        document_id=doc_a.id,
        sheet_id=sheet_a.id,
        symbol_type="gate_valve",
        confidence=0.96,
        bbox=[100.0, 100.0, 140.0, 140.0],
        bbox_normalized=[0.08, 0.11, 0.12, 0.16],
        environment="production",
        matched_library_entry_id=prod_template.id,
        match_evidence={
            "tag_or_code": "V-101",
            "canonical_name": "gate_valve",
            "is_recognized": True
        }
    )
    # Símbolo desconocido para SYM-UNKNOWN-001
    sym_unknown = DetectedSymbol(
        id=f"sym-unk-{suffix}",
        document_id=doc_a.id,
        sheet_id=sheet_a.id,
        symbol_type="unknown_symbol",
        confidence=0.35,
        bbox=[200.0, 200.0, 240.0, 240.0],
        bbox_normalized=[0.16, 0.23, 0.20, 0.28],
        environment="production",
        match_evidence={
            "tag_or_code": "SYM-UNKNOWN-001",
            "canonical_name": "unknown_symbol",
            "is_recognized": False
        }
    )
    db.add_all([sym_1, sym_unknown])
    db.commit()

    # Sembrar taxonomía y reglas
    TaxonomyService.seed_taxonomy_and_rules(db)

    token = create_access_token(user.id, email=user.email, extra_claims={"role": "admin"})
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org.id}

    yield {
        "db": db,
        "client": client,
        "headers": headers,
        "org": org,
        "user": user,
        "project_a": project_a,
        "project_b": project_b,
        "doc_a": doc_a,
        "doc_b": doc_b,
        "sheet_a": sheet_a,
        "suffix": suffix
    }
    db.close()


@pytest.mark.postgres
def test_taxonomy_idempotent_seeding(review_env):
    """Verifica que la siembra de taxonomía y reglas sea estrictamente idempotente."""
    db: Session = review_env["db"]

    # Ejecutar 2da y 3ra siembra
    res2 = TaxonomyService.seed_taxonomy_and_rules(db)
    res3 = TaxonomyService.seed_taxonomy_and_rules(db)

    # No debe duplicar disciplinas ni temas
    disciplines = db.query(ReviewDiscipline).all()
    assert len(disciplines) >= 12
    codes = [d.code for d in disciplines]
    assert len(codes) == len(set(codes))

    topics = db.query(ReviewTopic).all()
    assert len(topics) >= 21
    topic_codes = [t.code for t in topics]
    assert len(topic_codes) == len(set(topic_codes))

    # Verificar existencia de PIPING y PID_SYMBOLS
    piping = db.query(ReviewDiscipline).filter(ReviewDiscipline.code == "PIPING").first()
    assert piping is not None

    pid_sym = db.query(ReviewTopic).filter(ReviewTopic.code == "PID_SYMBOLS").first()
    assert pid_sym is not None
    assert pid_sym.enabled_mvp is True


@pytest.mark.postgres
def test_scope_filtering_piping_and_pid_symbols(review_env):
    """
    Verifica que el alcance PIPING + PID_SYMBOLS filtre exactamente sus reglas aprobadas
    más las reglas transversales (GENERAL), y excluya otras disciplinas.
    """
    db: Session = review_env["db"]

    applicable = TaxonomyService.get_applicable_rules(db, "PIPING", "PID_SYMBOLS", mode="production")
    app_codes = [r["code"] for r in applicable]

    # Reglas esperadas en el MVP
    assert "SYM-UNKNOWN-001" in app_codes
    assert "SYM-AMBIGUOUS-001" in app_codes
    assert "SYM-LEGEND-CONSISTENCY-001" in app_codes
    assert "SYM-TAG-MISSING-001" in app_codes
    assert "GEN-DOC-001" in app_codes

    # No debe incluir reglas de arquitectura ni eléctricas
    assert "RULE_DOOR_COUNT_MATCH_V1" not in app_codes
    assert "RULE_WINDOW_COUNT_MATCH_V1" not in app_codes


@pytest.mark.postgres
def test_unapproved_topics_show_empty_scope(review_env):
    """
    Verifica que otros puntos de revisión (e.g. LINE_LIST_CONSISTENCY, ISOMETRIC_COMPLETENESS)
    no simulen evaluaciones y reporten 'No hay reglas aprobadas para este alcance'.
    """
    db: Session = review_env["db"]
    project_a = review_env["project_a"]
    doc_a = review_env["doc_a"]

    plan = ReviewOrchestrator.generate_review_plan(
        db=db,
        project_id=project_a.id,
        discipline_code="PIPING",
        topic_code="LINE_LIST_CONSISTENCY",
        document_ids=[doc_a.id],
        mode="production"
    )

    assert plan["can_execute"] is False
    assert plan["empty_reason"] == "No hay reglas aprobadas para este alcance"
    assert len(plan["applicable_rules"]) == 0


@pytest.mark.postgres
def test_production_vs_sandbox_rule_filtering(review_env):
    """
    Verifica que reglas no aprobadas (ej. proposed por IA) no se ejecuten en production,
    pero puedan ejecutarse en sandbox con advertencia visible.
    """
    db: Session = review_env["db"]
    piping = db.query(ReviewDiscipline).filter(ReviewDiscipline.code == "PIPING").first()
    pid_topic = db.query(ReviewTopic).filter(ReviewTopic.code == "PID_SYMBOLS").first()

    # Crear una regla experimental sugerida por IA
    test_rule = RuleDefinition(
        code=f"AI-EXPERIMENTAL-{uuid.uuid4().hex[:6].upper()}",
        name="Regla Experimental de Válvulas por IA",
        category="normative_compliance",
        discipline="piping",
        description="Regla propuesta por IA aún no auditada por humanos.",
        source_status="proposed",
        suggested_by_ai=True,
        execution_phase=6,
        priority=50,
        enabled=True
    )
    db.add(test_rule)
    db.commit()

    # Crear aplicabilidad en estado 'proposed'
    app_ai = RuleApplicability(
        rule_id=test_rule.id,
        discipline_id=piping.id,
        topic_id=pid_topic.id,
        role="primary",
        source="ai_suggested",
        approval_status="proposed",
        confidence=0.75
    )
    db.add(app_ai)
    db.commit()

    # En producción: NO debe figurar
    prod_rules = TaxonomyService.get_applicable_rules(db, "PIPING", "PID_SYMBOLS", mode="production")
    prod_codes = [r["code"] for r in prod_rules]
    assert test_rule.code not in prod_codes

    # En sandbox: DEBE figurar
    sandbox_rules = TaxonomyService.get_applicable_rules(db, "PIPING", "PID_SYMBOLS", mode="sandbox")
    sandbox_codes = [r["code"] for r in sandbox_rules]
    assert test_rule.code in sandbox_codes

    # Aprobación humana habilita la regla para producción
    app_ai.approval_status = "approved"
    test_rule.source_status = "approved"
    db.commit()

    prod_rules_after = TaxonomyService.get_applicable_rules(db, "PIPING", "PID_SYMBOLS", mode="production")
    prod_codes_after = [r["code"] for r in prod_rules_after]
    assert test_rule.code in prod_codes_after


@pytest.mark.postgres
def test_document_isolation_multi_project(review_env):
    """
    Verifica que nunca se puedan incluir ni evaluar documentos de otro proyecto.
    """
    db: Session = review_env["db"]
    project_a = review_env["project_a"]
    doc_b = review_env["doc_b"] # Pertenece a project_b

    plan = ReviewOrchestrator.generate_review_plan(
        db=db,
        project_id=project_a.id,
        discipline_code="PIPING",
        topic_code="PID_SYMBOLS",
        document_ids=[doc_b.id], # Intento de incluir documento de otro proyecto
        mode="production"
    )

    # doc_b debe ser filtrado/excluido de project_a
    included_ids = [d["document_id"] for d in plan["included_documents"]]
    assert doc_b.id not in included_ids


@pytest.mark.postgres
def test_topological_plan_and_phases_blueprint(review_env):
    """
    Verifica el plano topológico de fases 1 a 9 y la separación de
    preparación técnica (fases 1-4) de evaluación QA/QC (fases 5-8).
    """
    db: Session = review_env["db"]
    project_a = review_env["project_a"]
    doc_a = review_env["doc_a"]

    plan = ReviewOrchestrator.generate_review_plan(
        db=db,
        project_id=project_a.id,
        discipline_code="PIPING",
        topic_code="PID_SYMBOLS",
        document_ids=[doc_a.id],
        mode="production"
    )

    phases = plan["phases_blueprint"]
    assert len(phases) == 9

    # Fases 1 a 4 son de preparación de datos
    for p in phases[:4]:
        assert p["step_type"] in ["preparation", "extraction", "normalization"]
        assert p["rule_count"] == 0 # No ejecutan reglas QA/QC

    # Fases 5 a 8 evalúan reglas QA/QC
    qa_phases = phases[4:8]
    for p in qa_phases:
        assert p["step_type"] == "evaluation"

    # Fase 9 es consolidación y reporting
    assert phases[8]["step_type"] == "reporting"


@pytest.mark.postgres
def test_orchestration_execution_and_persisted_export(review_env):
    """
    Verifica la ejecución integral del flujo:
    - Pre-flight plan -> ReviewRun -> Steps (Fases 1 a 9) -> RuleExecutions -> RuleFindings
    - Generación y descarga de reporte persistido en JSON, XLSX y PDF con SHA-256.
    """
    db: Session = review_env["db"]
    project_a = review_env["project_a"]
    doc_a = review_env["doc_a"]

    # Ejecutar corrida
    run_result = ReviewOrchestrator.execute_review_run(
        db=db,
        project_id=project_a.id,
        discipline_code="PIPING",
        topic_code="PID_SYMBOLS",
        document_ids=[doc_a.id],
        mode="production",
        requested_by="lead_auditor@test.com"
    )

    run_id = run_result["review_run_id"]
    assert run_id is not None
    assert run_result["status"] == "completed"

    # Verificar steps en base de datos
    steps = db.query(ReviewRunStep).filter(ReviewRunStep.review_run_id == run_id).order_by(ReviewRunStep.phase).all()
    assert len(steps) == 9
    for s in steps:
        assert s.status in ["succeeded", "skipped"]

    # Verificar ejecuciones de reglas
    executions = db.query(RuleExecution).filter(RuleExecution.review_run_id == run_id).all()
    assert len(executions) >= 4
    ex_codes = [ex.rule.code for ex in executions]
    assert "SYM-UNKNOWN-001" in ex_codes

    # Como sym_unknown estaba en la lámina, SYM-UNKNOWN-001 debió fallar
    unknown_ex = next(ex for ex in executions if ex.rule.code == "SYM-UNKNOWN-001")
    assert unknown_ex.execution_status == "failed"

    # Verificar que se generó al menos un hallazgo con bbox
    findings = db.query(RuleFinding).filter(RuleFinding.review_run_id == run_id).all()
    assert len(findings) >= 1
    f1 = findings[0]
    assert f1.bbox is not None
    assert f1.navigation_context is not None
    assert f1.navigation_context.get("document_id") == doc_a.id

    # 8. Exportaciones persistidas (JSON, XLSX, PDF)
    rep_json = ReviewExportService.create_report(db, run_id, "json")
    assert rep_json.format == "json"
    assert os.path.exists(rep_json.artifact_path)
    assert len(rep_json.sha256) == 64

    rep_xlsx = ReviewExportService.create_report(db, run_id, "xlsx")
    assert rep_xlsx.format == "xlsx"
    assert os.path.exists(rep_xlsx.artifact_path)

    rep_pdf = ReviewExportService.create_report(db, run_id, "pdf")
    assert rep_pdf.format == "pdf"
    assert os.path.exists(rep_pdf.artifact_path)


@pytest.mark.postgres
def test_unmet_dependency_produces_structured_not_evaluable(review_env):
    """
    Verifica que el incumplimiento de una dependencia declarativa
    genere estado 'not_evaluable' estructurado con código RULE_DEPENDENCY_NOT_MET
    y recomendación explícita.
    """
    db: Session = review_env["db"]
    project_a = review_env["project_a"]
    doc_a = review_env["doc_a"]

    # Ejecutar corrida donde SYM-UNKNOWN-001 falla debido a la presencia del símbolo desconocido
    run_result = ReviewOrchestrator.execute_review_run(
        db=db,
        project_id=project_a.id,
        discipline_code="PIPING",
        topic_code="PID_SYMBOLS",
        document_ids=[doc_a.id],
        mode="production"
    )
    run_id = run_result["review_run_id"]

    executions = db.query(RuleExecution).filter(RuleExecution.review_run_id == run_id).all()

    # Las reglas dependientes de SYM-UNKNOWN-001 (ej: SYM-AMBIGUOUS-001)
    # deben marcarse not_evaluable con razón RULE_DEPENDENCY_NOT_MET
    dep_executions = [ex for ex in executions if ex.not_evaluable_reason_code == "RULE_DEPENDENCY_NOT_MET"]
    assert len(dep_executions) >= 1
    dep_ex = dep_executions[0]
    assert dep_ex.execution_status == "not_evaluable"
    assert "SYM-UNKNOWN-001" in dep_ex.not_evaluable_reason_message
    assert dep_ex.recommended_action is not None


@pytest.mark.postgres
def test_missing_approved_catalog_produces_not_evaluable(review_env):
    """
    Verifica que en modo production, si no existen plantillas activas aprobadas
    en el catálogo, las reglas de PID_SYMBOLS produzcan not_evaluable estructurado
    (MISSING_SYMBOL_CATALOG), en lugar de simular evaluaciones aprobadas o falladas.
    """
    db: Session = review_env["db"]
    org = review_env["org"]
    suffix = str(uuid.uuid4())[:8]

    # Crear proyecto aislado sin templates
    proj_empty = Project(
        id=f"prj-empty-{suffix}",
        organization_id=org.id,
        name=f"Proyecto Sin Catálogo {suffix}",
        code=f"PRJ-EMP-{suffix[:4].upper()}",
        discipline="piping"
    )
    db.add(proj_empty)
    doc_empty = Document(
        id=f"doc-empty-{suffix}",
        project_id=proj_empty.id,
        organization_id=org.id,
        filename="empty.pdf",
        file_path="/tmp/empty.pdf",
        file_hash_sha256=f"hash-emp-{suffix}",
        file_size_bytes=1000,
        page_count=1,
        status="ready"
    )
    db.add(doc_empty)
    db.commit()

    # Desactivar temporalmente plantillas activas para simular ausencia de catálogo
    tmpls = db.query(SymbolTemplate).filter(SymbolTemplate.status == "active").all()
    for t in tmpls:
        t.status = "draft"
    db.commit()

    try:
        # Pre-flight plan en production reporta limitación
        plan = ReviewOrchestrator.generate_review_plan(
            db=db,
            project_id=proj_empty.id,
            discipline_code="PIPING",
            topic_code="PID_SYMBOLS",
            document_ids=[doc_empty.id],
            mode="production"
        )
        assert any("Catálogo de Simbología productivo sin versiones aprobadas" in lim for lim in plan.get("limitations", []))

        # Ejecución en production
        run_res = ReviewOrchestrator.execute_review_run(
            db=db,
            project_id=proj_empty.id,
            discipline_code="PIPING",
            topic_code="PID_SYMBOLS",
            document_ids=[doc_empty.id],
            mode="production"
        )
        run_id = run_res["review_run_id"]
        executions = db.query(RuleExecution).filter(RuleExecution.review_run_id == run_id).all()
        sym_execs = [ex for ex in executions if ex.rule.code.startswith("SYM-")]
        assert len(sym_execs) >= 4
        for ex in sym_execs:
            assert ex.execution_status == "not_evaluable"
            assert ex.not_evaluable_reason_code == "MISSING_SYMBOL_CATALOG"
            assert "symbol_catalog_approved" in ex.missing_requirements
    finally:
        # Restaurar estado
        for t in tmpls:
            t.status = "active"
        db.commit()


@pytest.mark.postgres
def test_test_only_template_and_sandbox_semantics(review_env):
    """
    Verifica que:
    1. Una plantilla test_only funciona en sandbox generando hallazgos con aviso explícito.
    2. La misma plantilla test_only no crea match/hallazgo productivo en production.
    3. Un símbolo con environment='sandbox' no genera hallazgos productivos.
    4. Los reportes exportados dejan visible execution_mode y la marca de sandbox.
    """
    db: Session = review_env["db"]
    project_a = review_env["project_a"]
    doc_a = review_env["doc_a"]
    sheet_a = review_env["sheet_a"]
    suffix = str(uuid.uuid4())[:8]

    # 1. Crear plantilla test_only
    tmpl_test = SymbolTemplate(
        id=f"tmpl-test-{suffix}",
        symbol_class="special_test_valve",
        canonical_code=f"TEST-VALVE-{suffix[:4].upper()}",
        canonical_name="Test Only Valve",
        display_name="Plantilla Experimental",
        discipline="piping",
        status="test_only",
        category="test_only",
        is_active_for_detection=True
    )
    db.add(tmpl_test)
    db.flush()

    ver_test = SymbolTemplateVersion(
        id=f"ver-test-{suffix}",
        symbol_template_id=tmpl_test.id,
        version_number=1,
        approval_status="draft",
        source_kind="test_only"
    )
    db.add(ver_test)

    # Símbolo experimental en sandbox
    sym_sandbox = DetectedSymbol(
        id=f"sym-sbx-{suffix}",
        document_id=doc_a.id,
        sheet_id=sheet_a.id,
        symbol_type="special_test_valve",
        confidence=0.45,
        bbox=[300.0, 300.0, 350.0, 350.0],
        bbox_normalized=[0.25, 0.35, 0.29, 0.41],
        environment="sandbox",
        matched_library_entry_id=tmpl_test.id,
        match_evidence={"tag_or_code": "SYM-UNKNOWN-001", "is_recognized": False}
    )
    db.add(sym_sandbox)
    db.commit()

    # 2. Ejecución en SANDBOX
    run_sandbox = ReviewOrchestrator.execute_review_run(
        db=db,
        project_id=project_a.id,
        discipline_code="PIPING",
        topic_code="PID_SYMBOLS",
        document_ids=[doc_a.id],
        mode="sandbox"
    )
    sbx_run_id = run_sandbox["review_run_id"]
    sbx_findings = db.query(RuleFinding).filter(RuleFinding.review_run_id == sbx_run_id).all()
    assert len(sbx_findings) >= 1
    for f in sbx_findings:
        assert f.evidence_refs.get("execution_mode") == "sandbox"
        assert f.evidence_refs.get("is_exploratory") is True
        assert "Resultado exploratorio" in f.evidence_refs.get("warning", "")
        assert f.navigation_context.get("execution_mode") == "sandbox"
        assert f.navigation_context.get("is_exploratory") is True
        assert "[SANDBOX]" in f.title

    # 3. Export en Sandbox deja visible execution_mode y advertencia
    rep_json = ReviewExportService.create_report(db, sbx_run_id, "json")
    with open(rep_json.artifact_path, "r", encoding="utf-8") as jf:
        jdata = json.load(jf)
        assert jdata["execution_mode"] == "sandbox"
        assert any(find.get("is_exploratory") is True for find in jdata.get("findings", []))

    rep_pdf = ReviewExportService.create_report(db, sbx_run_id, "pdf")
    with open(rep_pdf.artifact_path, "rb") as pf:
        pdf_content = pf.read().decode("latin-1", errors="ignore")
        assert "SANDBOX" in pdf_content
        assert "Resultado exploratorio" in pdf_content

    rep_xlsx = ReviewExportService.create_report(db, sbx_run_id, "xlsx")
    assert rep_xlsx.format == "xlsx"

    # 4. En PRODUCTION: símbolo sandbox NO genera finding productivo
    # y la plantilla test_only no se usa para matching productivo
    run_prod = ReviewOrchestrator.execute_review_run(
        db=db,
        project_id=project_a.id,
        discipline_code="PIPING",
        topic_code="PID_SYMBOLS",
        document_ids=[doc_a.id],
        mode="production"
    )
    prod_run_id = run_prod["review_run_id"]
    prod_findings = db.query(RuleFinding).filter(RuleFinding.review_run_id == prod_run_id).all()
    for f in prod_findings:
        assert f.evidence_refs.get("execution_mode") == "production"
        assert f.evidence_refs.get("is_exploratory") is False
        # Ningún finding basado en sym_sandbox
        assert f.navigation_context.get("symbol_id") != sym_sandbox.id
        assert "[SANDBOX]" not in f.title
