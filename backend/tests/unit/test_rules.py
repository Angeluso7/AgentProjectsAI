import pytest
import uuid
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.db.session import Base, get_db
from app.main import app
from app.db.models.core import Project
from app.db.models.document_memory import (
    Document, DocumentSheet, SheetRegion, TitleBlockExtraction,
    ExtractedTable, ExtractedTableCell, DetectedSymbol
)
from app.db.models.decision_memory import RuleDefinition, RuleExecution, RuleFinding
from app.services.rules.engine import RuleEngine, RuleRegistry
from app.services.rules.contracts import RuleInput
from app.services.rules.implementations import (
    DoorCountMatchRule,
    WindowCountMatchRule,
    TitleBlockRequiredFieldsRule,
    TitleBlockScaleValidRule,
    NormativeMinDoorWidthRule
)

# Base de datos en memoria para pruebas unitarias
@pytest.fixture(autouse=True)
def seed_rules(db_session):
    RuleRegistry.seed_database_definitions(db_session)

def test_door_count_match_rule_pass():
    rule = DoorCountMatchRule()
    
    # Crear inputs simulados
    dummy_table = ExtractedTable(
        id=str(uuid.uuid4()),
        table_type="door_schedule",
        title="CUADRO DE PUERTAS",
        row_count=3,
        column_count=3
    )
    cell_header = ExtractedTableCell(table_id=dummy_table.id, row_index=0, column_index=1, text="CANTIDAD", is_header=True)
    cell_row1 = ExtractedTableCell(table_id=dummy_table.id, row_index=1, column_index=1, text="2", is_header=False)
    cell_row2 = ExtractedTableCell(table_id=dummy_table.id, row_index=2, column_index=1, text="1", is_header=False)
    
    symbols = [
        DetectedSymbol(id=str(uuid.uuid4()), symbol_type="door_symbol", discipline="architecture"),
        DetectedSymbol(id=str(uuid.uuid4()), symbol_type="door_symbol", discipline="architecture"),
        DetectedSymbol(id=str(uuid.uuid4()), symbol_type="door_symbol", discipline="architecture"),
    ]
    
    inputs = RuleInput(
        document_id="doc-1",
        sheet_id="sheet-1",
        tables=[dummy_table],
        cells_by_table={dummy_table.id: [cell_header, cell_row1, cell_row2]},
        symbols=symbols
    )
    
    res = rule.evaluate(inputs)
    assert res.status == "passed"
    assert res.observed_value == 3
    assert res.expected_value == 3
    assert res.delta == 0
    assert not res.requires_human_review

def test_door_count_mismatch_generates_finding():
    rule = DoorCountMatchRule()
    
    dummy_table = ExtractedTable(
        id=str(uuid.uuid4()),
        table_type="door_schedule",
        title="CUADRO DE PUERTAS",
        row_count=2,
        column_count=2
    )
    cell_header = ExtractedTableCell(table_id=dummy_table.id, row_index=0, column_index=1, text="CANT", is_header=True)
    cell_row1 = ExtractedTableCell(table_id=dummy_table.id, row_index=1, column_index=1, text="4", is_header=False)
    
    # 2 puertas detectadas vs 4 declaradas
    symbols = [
        DetectedSymbol(id=str(uuid.uuid4()), symbol_type="door_symbol", discipline="architecture"),
        DetectedSymbol(id=str(uuid.uuid4()), symbol_type="door_symbol", discipline="architecture"),
    ]
    
    inputs = RuleInput(
        document_id="doc-1",
        sheet_id="sheet-1",
        tables=[dummy_table],
        cells_by_table={dummy_table.id: [cell_header, cell_row1]},
        symbols=symbols
    )
    
    res = rule.evaluate(inputs)
    assert res.status == "failed"
    assert res.observed_value == 2
    assert res.expected_value == 4
    assert res.delta == -2
    assert res.requires_human_review is True
    assert res.review_task_type == "rule_finding_review"

def test_title_block_required_fields_and_scale():
    rule_fields = TitleBlockRequiredFieldsRule()
    rule_scale = TitleBlockScaleValidRule()
    
    # Viñeta incompleta sin scale_text
    tb_incomplete = TitleBlockExtraction(
        id=str(uuid.uuid4()),
        sheet_code="ARQ-01",
        revision="A",
        scale_text=None,
        match_score=0.90
    )
    
    inputs = RuleInput(document_id="doc-1", title_block=tb_incomplete)
    res_fields = rule_fields.evaluate(inputs)
    assert res_fields.status == "failed"
    assert "scale_text" in res_fields.delta

    # Viñeta completa con escala válida
    tb_complete = TitleBlockExtraction(
        id=str(uuid.uuid4()),
        sheet_code="ARQ-01",
        revision="A",
        scale_text="1:50",
        match_score=0.95
    )
    inputs_ok = RuleInput(document_id="doc-1", title_block=tb_complete)
    assert rule_fields.evaluate(inputs_ok).status == "passed"
    assert rule_scale.evaluate(inputs_ok).status == "passed"

def test_normative_min_door_width_rule():
    rule = NormativeMinDoorWidthRule()
    
    # 1. Puerta violando ancho mínimo (0.70 m < 0.80 m)
    sym_violating = DetectedSymbol(
        id=str(uuid.uuid4()),
        symbol_type="door_symbol",
        discipline="architecture",
        attributes={"width_m": 0.70}
    )
    inputs_fail = RuleInput(document_id="doc-1", symbols=[sym_violating])
    res_fail = rule.evaluate(inputs_fail)
    assert res_fail.status == "failed"
    assert res_fail.severity == "critical"
    assert res_fail.requires_human_review is True
    assert res_fail.review_task_type == "normative_rule_review"

    # 2. Puerta cumpliendo ancho mínimo (0.90 m >= 0.80 m)
    sym_ok = DetectedSymbol(
        id=str(uuid.uuid4()),
        symbol_type="door_symbol",
        discipline="architecture",
        attributes={"width_m": 0.90}
    )
    inputs_ok = RuleInput(document_id="doc-1", symbols=[sym_ok])
    assert rule.evaluate(inputs_ok).status == "passed"

def test_rule_engine_full_sheet_evaluation(db_session):
    # Crear proyecto, documento y lámina
    proj = Project(id=str(uuid.uuid4()), name="Hospital Regional", code="HOSP-01")
    db_session.add(proj)
    doc = Document(id=str(uuid.uuid4()), project_id=proj.id, filename="arquitectura.pdf")
    db_session.add(doc)
    sheet = DocumentSheet(id=str(uuid.uuid4()), document_id=doc.id, sheet_number=1, sheet_code="ARQ-01")
    db_session.add(sheet)
    
    # Agregar viñeta completa
    tb = TitleBlockExtraction(
        id=str(uuid.uuid4()),
        sheet_id=sheet.id,
        sheet_code="ARQ-01",
        revision="B",
        scale_text="1:100",
        discipline="architecture",
        match_score=0.96
    )
    db_session.add(tb)
    
    # Agregar cuadro de puertas y símbolos
    table = ExtractedTable(
        id=str(uuid.uuid4()),
        document_id=doc.id,
        sheet_id=sheet.id,
        table_type="door_schedule",
        title="CUADRO DE PUERTAS",
        row_count=2,
        column_count=2,
        confidence=0.90
    )
    db_session.add(table)
    c1 = ExtractedTableCell(id=str(uuid.uuid4()), table_id=table.id, row_index=0, column_index=1, text="CANTIDAD", is_header=True)
    c2 = ExtractedTableCell(id=str(uuid.uuid4()), table_id=table.id, row_index=1, column_index=1, text="3", is_header=False)
    db_session.add_all([c1, c2])
    
    # 2 puertas detectadas (mismatch de 1 puerta)
    s1 = DetectedSymbol(id=str(uuid.uuid4()), document_id=doc.id, sheet_id=sheet.id, symbol_type="door_symbol", discipline="architecture", attributes={"width_m": 0.85})
    s2 = DetectedSymbol(id=str(uuid.uuid4()), document_id=doc.id, sheet_id=sheet.id, symbol_type="door_symbol", discipline="architecture", attributes={"width_m": 0.85})
    db_session.add_all([s1, s2])
    db_session.commit()

    engine = RuleEngine(db_session)
    findings = engine.evaluate_sheet(sheet.id)
    
    # Debe haber al menos 1 finding (Door count mismatch de 2 vs 3)
    assert len(findings) >= 1
    mismatch_finding = next((f for f in findings if f.rule_code == "RULE_DOOR_COUNT_MATCH_V1"), None)
    assert mismatch_finding is not None
    assert mismatch_finding.status == "open"
    assert mismatch_finding.delta == -1
    assert mismatch_finding.review_task_id is not None

def test_api_async_rules_and_resolution(client, db_session):
    proj = Project(id=str(uuid.uuid4()), name="Mall Centro", code="MALL-01")
    db_session.add(proj)
    doc = Document(id=str(uuid.uuid4()), project_id=proj.id, filename="mall.pdf")
    db_session.add(doc)
    sheet = DocumentSheet(id=str(uuid.uuid4()), document_id=doc.id, sheet_number=1, sheet_code="ARQ-01")
    db_session.add(sheet)
    db_session.commit()

    # 1. Encolar evaluación asíncrona
    resp_async = client.post(f"/api/v1/rules/sheets/{sheet.id}/async")
    assert resp_async.status_code == 202
    data_async = resp_async.json()
    assert "job_id" in data_async
    assert data_async["status"] == "queued"

    # 2. Crear finding manual y resolverlo
    rule_def = db_session.query(RuleDefinition).first()
    finding = RuleFinding(
        id=str(uuid.uuid4()),
        document_id=doc.id,
        sheet_id=sheet.id,
        rule_id=rule_def.id if rule_def else None,
        rule_code="RULE_DOOR_COUNT_MATCH_V1",
        rule_name="Door Count Match",
        category="cross_reconciliation",
        severity="high",
        status="open",
        title="Discrepancia de Puertas",
        description="Falta 1 puerta en planta"
    )
    db_session.add(finding)
    db_session.commit()

    # 3. Resolver finding
    resp_resolve = client.post(
        f"/api/v1/findings/{finding.id}/resolve",
        json={"resolution_type": "confirmed", "resolved_by": "auditor_senior", "notes": "Discrepancia confirmada en terreno"}
    )
    assert resp_resolve.status_code == 200
    res_data = resp_resolve.json()
    assert res_data["status"] == "confirmed"
