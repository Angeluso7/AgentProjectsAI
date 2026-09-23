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
    ReviewRun,
    ReviewRunDocument,
    ReviewRunStep,
    SymbolInventoryGroup,
    ReviewReport
)
from app.db.models.document_memory import (
    Document,
    DocumentSheet,
    DetectedSymbol
)
from app.db.models.template_memory import SymbolTemplate
from app.db.models.symbol_catalog import SymbolTemplateVersion
from app.core.security import create_access_token
from app.services.symbols.symbol_inventory_service import SymbolInventoryService
from app.services.review.export_service import ReviewExportService
from app.services.symbols.geometric_validator import (
    compute_symbol_crop_bbox,
    compute_occurrence_context_crop_bbox
)

try:
    import openpyxl
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False


@pytest.fixture
def inventory_test_env():
    db: Session = SessionLocal()
    suffix = str(uuid.uuid4())[:8]

    org = Organization(id=f"org-inv-{suffix}", name=f"Org Inv {suffix}", slug=f"org-inv-{suffix}")
    user = User(
        id=f"user-inv-{suffix}",
        email=f"auditor-inv-{suffix}@test.com",
        display_name=f"Auditor Inv {suffix}",
        password_hash="fake",
        is_active=True
    )
    db.add_all([org, user])
    db.commit()

    mem = OrganizationMembership(
        organization_id=org.id,
        user_id=user.id,
        role="admin"
    )
    db.add(mem)

    project = Project(
        id=f"prj-inv-{suffix}",
        organization_id=org.id,
        code=f"PRJ-INV-{suffix}",
        name=f"Proyecto Inv {suffix}",
        status="active"
    )
    db.add(project)
    db.commit()

    disc = ReviewDiscipline(
        id=f"disc-piping-{suffix}",
        code="PIPING",
        name="Cañerías / Piping",
        order_index=1,
        is_active=True
    )
    topic = ReviewTopic(
        id=f"topic-pid-{suffix}",
        discipline_id=disc.id,
        code="PID_SYMBOLS",
        name="Simbología P&ID",
        order_index=1,
        is_active=True
    )
    db.add_all([disc, topic])
    db.commit()

    # Documentos
    doc_legend = Document(
        id=f"doc-leg-{suffix}",
        organization_id=org.id,
        project_id=project.id,
        filename="000-LEGEND.pdf",
        file_path=f"/storage/docs/000-LEGEND-{suffix}.pdf",
        file_hash_sha256=f"hash-leg-{suffix}",
        file_size_bytes=102400,
        page_count=1,
        status="ready"
    )
    doc_pid = Document(
        id=f"doc-pid-{suffix}",
        organization_id=org.id,
        project_id=project.id,
        filename="001-PID-AREA-100.pdf",
        file_path=f"/storage/docs/001-PID-{suffix}.pdf",
        file_hash_sha256=f"hash-pid-{suffix}",
        file_size_bytes=204800,
        page_count=1,
        status="ready"
    )
    db.add_all([doc_legend, doc_pid])
    db.commit()

    sheet_leg = DocumentSheet(
        id=f"sheet-leg-{suffix}",
        document_id=doc_legend.id,
        sheet_number=1,
        title="Leyenda Simbología",
        width_px=2400,
        height_px=1800,
        dpi=150
    )
    sheet_pid = DocumentSheet(
        id=f"sheet-pid-{suffix}",
        document_id=doc_pid.id,
        sheet_number=1,
        title="P&ID Hoja 1",
        width_px=2400,
        height_px=1800,
        dpi=150
    )
    db.add_all([sheet_leg, sheet_pid])
    db.commit()

    # Plantilla de Catálogo (para símbolo reconocido)
    tmpl = SymbolTemplate(
        id=f"tmpl-valve-{suffix}",
        organization_id=org.id,
        symbol_class="gate_valve",
        display_name="Válvula Compuerta Manual",
        canonical_code="SYM-GATE_VALVE",
        canonical_name="Válvula Compuerta Manual",
        technical_function="Aislamiento on/off de línea de proceso",
        standard_reference="ISA-5.1 / PIP PNC00001",
        status="active"
    )
    db.add(tmpl)
    db.commit()

    tmpl_ver = SymbolTemplateVersion(
        id=f"ver-valve-{suffix}",
        symbol_template_id=tmpl.id,
        version_number=1,
        approval_status="approved"
    )
    db.add(tmpl_ver)
    db.commit()

    # Corrida ReviewRun
    run = ReviewRun(
        id=f"run-inv-{suffix}",
        organization_id=org.id,
        project_id=project.id,
        discipline_id=disc.id,
        topic_id=topic.id,
        execution_mode="production",
        run_name=f"Auditoría Simbología {suffix}",
        status="succeeded",
        requested_by=user.email,
        summary_stats={"passed": 5, "failed": 1, "warning": 0, "not_evaluable": 0}
    )
    db.add(run)
    db.commit()

    rd1 = ReviewRunDocument(
        id=f"rd1-{suffix}",
        review_run_id=run.id,
        document_id=doc_legend.id,
        inclusion_reason="legend",
        document_role="legend",
        status="included"
    )
    rd2 = ReviewRunDocument(
        id=f"rd2-{suffix}",
        review_run_id=run.id,
        document_id=doc_pid.id,
        inclusion_reason="pid",
        document_role="pid",
        status="included"
    )
    db.add_all([rd1, rd2])
    db.commit()

    # Símbolos detectados
    # 1. Reconocido productivo (2 ocurrencias: 1 en leyenda, 1 en PID)
    s1 = DetectedSymbol(
        id=f"sym1-{suffix}",
        document_id=doc_legend.id,
        sheet_id=sheet_leg.id,
        symbol_type="gate_valve",
        classification="symbol",
        matched_template_id=tmpl.id,
        matched_template_version_id=tmpl_ver.id,
        matching_status="matched",
        geometric_confidence=0.96,
        bbox=[240, 360, 360, 450],
        bbox_normalized=[0.10, 0.20, 0.15, 0.25],
        inner_drawing_bbox=[0.105, 0.205, 0.145, 0.245],
        detected_tag_or_code="V-101"
    )
    s2 = DetectedSymbol(
        id=f"sym2-{suffix}",
        document_id=doc_pid.id,
        sheet_id=sheet_pid.id,
        symbol_type="gate_valve",
        classification="symbol",
        matched_template_id=tmpl.id,
        matched_template_version_id=tmpl_ver.id,
        matching_status="matched",
        geometric_confidence=0.94,
        bbox=[720, 720, 840, 810],
        bbox_normalized=[0.30, 0.40, 0.35, 0.45],
        inner_drawing_bbox=[0.305, 0.405, 0.345, 0.445],
        detected_tag_or_code="V-102"
    )

    # 2. Desconocido (unknown_symbol) con geometría vectorial válida
    s3 = DetectedSymbol(
        id=f"sym3-{suffix}",
        document_id=doc_pid.id,
        sheet_id=sheet_pid.id,
        symbol_type="custom_regulator",
        classification="symbol",
        matched_template_id=None,
        matched_template_version_id=None,
        matching_status="unmatched",
        geometric_confidence=0.91,
        bbox=[1200, 1080, 1320, 1170],
        bbox_normalized=[0.50, 0.60, 0.55, 0.65],
        inner_drawing_bbox=[0.505, 0.605, 0.545, 0.645],
        detected_tag_or_code="PCV-201"
    )
    s4 = DetectedSymbol(
        id=f"sym4-{suffix}",
        document_id=doc_pid.id,
        sheet_id=sheet_pid.id,
        symbol_type="custom_regulator",
        classification="symbol",
        matched_template_id=None,
        matched_template_version_id=None,
        matching_status="unmatched",
        geometric_confidence=0.89,
        bbox=[1680, 1260, 1800, 1350],
        bbox_normalized=[0.70, 0.70, 0.75, 0.75],
        inner_drawing_bbox=[0.705, 0.705, 0.745, 0.745],
        detected_tag_or_code="PCV-202"
    )

    # 3. Figura excluida
    s5 = DetectedSymbol(
        id=f"sym5-{suffix}",
        document_id=doc_legend.id,
        sheet_id=sheet_leg.id,
        symbol_type="flow_diagram_box",
        classification="figure",
        matching_status="excluded",
        geometric_confidence=0.99,
        bbox=[1920, 180, 2280, 450],
        bbox_normalized=[0.80, 0.10, 0.95, 0.25]
    )

    db.add_all([s1, s2, s3, s4, s5])
    db.commit()

    token = create_access_token(subject=user.id, email=user.email, extra_claims={"organization_id": org.id})

    yield {
        "db": db,
        "org": org,
        "user": user,
        "project": project,
        "run": run,
        "tmpl": tmpl,
        "tmpl_ver": tmpl_ver,
        "symbols": [s1, s2, s3, s4, s5],
        "token": token
    }

    db.close()


def test_symbol_inventory_double_crops_invariants(inventory_test_env):
    """
    Invariante Fundamental:
    A. symbol_crop: inner_drawing_bbox + 3 mm
    B. occurrence_context_crop: symbol_crop_bbox + 15 mm, limitado a [0, 0, 1, 1]
    """
    sym = inventory_test_env["symbols"][0]
    pw, ph = 841.0, 595.0

    SymbolInventoryService.ensure_crops_for_symbol(sym, None, pw, ph)

    assert sym.symbol_crop_bbox is not None
    assert len(sym.symbol_crop_bbox) == 4
    assert sym.occurrence_context_crop_bbox is not None
    assert len(sym.occurrence_context_crop_bbox) == 4

    # El crop de contexto (15 mm) debe envolver estrictamente al crop de símbolo (3 mm)
    sc = sym.symbol_crop_bbox
    cc = sym.occurrence_context_crop_bbox

    assert cc[0] <= sc[0]
    assert cc[1] <= sc[1]
    assert cc[2] >= sc[2]
    assert cc[3] >= sc[3]

    # Límites estrictos dentro de la página [0, 0, 1, 1]
    assert cc[0] >= 0.0 and cc[1] >= 0.0
    assert cc[2] <= 1.0 and cc[3] <= 1.0


def test_symbol_inventory_grouping_and_unknowns(inventory_test_env):
    """
    Valida:
    1. Agrupación por template para símbolos catalogados (recognized_production).
    2. Agrupación por firma para símbolos desconocidos (unknown_symbol con U-001).
    3. Exclusión de figuras fuera del conteo canónico (figure_excluded).
    4. Conteo por documento y hoja.
    """
    db = inventory_test_env["db"]
    run = inventory_test_env["run"]

    groups, metrics = SymbolInventoryService.build_run_inventory(db, run, force_rebuild=True)

    assert len(groups) >= 3  # gate_valve, custom_regulator (U-001), figure_excluded

    prod_group = next(g for g in groups if g.catalog_status == "recognized_production")
    assert prod_group.display_code == "SYM-GATE_VALVE"
    assert prod_group.total_occurrences == 2
    assert "000-LEGEND.pdf" in prod_group.occurrences_by_document
    assert "001-PID-AREA-100.pdf" in prod_group.occurrences_by_document

    unk_group = next(g for g in groups if g.catalog_status == "unknown_symbol")
    assert unk_group.display_code.startswith("U-")
    assert unk_group.total_occurrences == 2
    assert unk_group.requires_human_review is True

    fig_group = next(g for g in groups if g.catalog_status == "figure_excluded")
    assert fig_group.display_code.startswith("FIG-")
    assert fig_group.total_occurrences == 1

    # Validar métricas consolidadas
    assert metrics["valid_symbol_occurrences"] == 4  # 2 gate valves + 2 custom regulators
    assert metrics["figures_excluded"] == 1
    assert metrics["recognized_production"] == 2
    assert metrics["unknown"] == 2
    assert metrics["production_coverage"] == 0.5  # 2/4 = 50%
    assert metrics["unknown_rate"] == 0.5         # 2/4 = 50%


def test_grouped_unknown_findings_rule_of_business(inventory_test_env):
    """
    Regla de Negocio 6: NO crear un hallazgo individual por cada ocurrencia desconocida.
    Debe crearse UN solo hallazgo agrupado por familia desconocida U-001.
    """
    db = inventory_test_env["db"]
    run = inventory_test_env["run"]

    groups, _ = SymbolInventoryService.build_run_inventory(db, run, force_rebuild=False)
    unknown_groups = [g for g in groups if g.catalog_status == "unknown_symbol"]

    findings = SymbolInventoryService.create_grouped_unknown_findings(db, run, unknown_groups)

    assert len(findings) == 1  # Exactamente 1 hallazgo agrupado para U-001
    finding = findings[0]
    assert "U-001" in finding.title or "U-" in finding.title
    assert finding.evidence_refs["total_occurrences"] == 2
    assert len(finding.evidence_refs["occurrence_ids"]) == 2


def test_symbol_inventory_api_endpoints(inventory_test_env):
    """
    Verifica los endpoints:
    1. GET /api/v1/review/runs/{run_id}/symbol-inventory (Tabla 1)
    2. GET /api/v1/review/runs/{run_id}/symbol-inventory/groups/{group_id}/occurrences (Tabla 2)
    """
    run = inventory_test_env["run"]
    token = inventory_test_env["token"]
    client = TestClient(app)

    # 1. Tabla 1: Inventario Consolidado
    res_inv = client.get(
        f"/api/v1/review/runs/{run.id}/symbol-inventory",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res_inv.status_code == 200, res_inv.text
    data_inv = res_inv.json()

    assert "metrics" in data_inv
    assert "groups" in data_inv
    assert "excluded_groups" in data_inv
    assert data_inv["metrics"]["valid_symbol_occurrences"] == 4
    assert len(data_inv["groups"]) >= 2

    target_group = data_inv["groups"][0]
    group_id = target_group["id"]

    # 2. Tabla 2: Ocurrencias con Doble Crop
    res_occ = client.get(
        f"/api/v1/review/runs/{run.id}/symbol-inventory/groups/{group_id}/occurrences",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res_occ.status_code == 200, res_occ.text
    data_occ = res_occ.json()

    assert len(data_occ) == target_group["total_occurrences"]
    for occ in data_occ:
        assert occ["symbol_crop_bbox"] is not None
        assert occ["occurrence_context_crop_bbox"] is not None
        assert occ["context_margin_mm"] == 15.0
        assert occ["navigation_context"]["document_id"] is not None


def test_symbol_inventory_exports_pdf_and_xlsx(inventory_test_env):
    """
    Valida la incorporación de Tabla 1 y Tabla 2 en los reportes persistidos XLSX y PDF.
    """
    db = inventory_test_env["db"]
    run = inventory_test_env["run"]

    # 1. Export XLSX
    rep_xlsx = ReviewExportService.create_report(db, run.id, export_format="xlsx")
    assert rep_xlsx.status == "ready"
    assert os.path.exists(rep_xlsx.artifact_path)

    if OPENPYXL_AVAILABLE:
        wb = openpyxl.load_workbook(rep_xlsx.artifact_path)
        sheet_names = wb.sheetnames
        assert "Resumen de Inventario" in sheet_names
        assert "Ocurrencias y Localizaciones" in sheet_names

        ws_inv = wb["Resumen de Inventario"]
        assert ws_inv.max_row >= 3  # Headers + al menos 2 grupos

        ws_occ = wb["Ocurrencias y Localizaciones"]
        assert ws_occ.max_row >= 5  # Headers + 4 ocurrencias

    # 2. Export PDF
    rep_pdf = ReviewExportService.create_report(db, run.id, export_format="pdf")
    assert rep_pdf.status == "ready"
    assert os.path.exists(rep_pdf.artifact_path)
    assert len(rep_pdf.sha256) == 64
    with open(rep_pdf.artifact_path, "rb") as f:
        content = f.read()
        assert content.startswith(b"%PDF")
