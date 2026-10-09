import os
import pytest
from unittest.mock import MagicMock
from sqlalchemy.orm import Session

from app.db.models.decision_memory import ReviewRun, SymbolInventoryGroup
from app.db.models.document_memory import DocumentSheet, DetectedSymbol
from app.services.symbols.symbol_inventory_service import SymbolInventoryService
from app.schemas.review_orchestration import SymbolInventoryResponse
from app.core.settings import settings


def test_simplify_symbol_description():
    # Válvulas conocidas
    desc_gate = SymbolInventoryService.simplify_symbol_description("Gate Valve", "Válvula de compuerta 2 pulg", "V-001")
    assert "Válvula de compuerta" in desc_gate
    assert "bloquea o permite el paso total" in desc_gate

    desc_check = SymbolInventoryService.simplify_symbol_description("Check Valve", "Válvula de retención", "V-002")
    assert "Válvula check" in desc_check

    desc_relief = SymbolInventoryService.simplify_symbol_description("PSV", "Válvula de seguridad", "PSV-101")
    assert "seguridad o alivio" in desc_relief

    # Desconocido
    desc_unknown = SymbolInventoryService.simplify_symbol_description("Unknown", "No reconocido", "U-001")
    assert "no identificado" in desc_unknown


def test_resolve_crop_url(tmp_path):
    # None / vacío
    assert SymbolInventoryService.resolve_crop_url(None) is None
    assert SymbolInventoryService.resolve_crop_url("") is None
    assert SymbolInventoryService.resolve_crop_url("   ") is None

    # Archivo que no existe
    assert SymbolInventoryService.resolve_crop_url("/non/existent/path/sym.png") is None

    # Archivo que existe dentro de STORAGE_LOCAL_ROOT
    crop_dir = os.path.join(settings.STORAGE_LOCAL_ROOT, "crops", "test_sheet")
    os.makedirs(crop_dir, exist_ok=True)
    crop_file = os.path.join(crop_dir, "sym_test1.png")
    with open(crop_file, "wb") as f:
        f.write(b"fake image data")

    try:
        url = SymbolInventoryService.resolve_crop_url(crop_file)
        assert url is not None
        assert url.startswith("/data/")
        assert "sym_test1.png" in url

        # Con prefijo /data/ directo
        assert SymbolInventoryService.resolve_crop_url("/data/crops/test_sheet/sym_test1.png") == "/data/crops/test_sheet/sym_test1.png"
    finally:
        if os.path.exists(crop_file):
            os.remove(crop_file)


def test_generate_executive_summary(db_session: Session):
    # Crear corrida simulada
    run = ReviewRun(
        id="test-run-exec-1",
        project_id="test-proj-1",
        run_name="Corrida Prueba Executive",
        status="completed"
    )

    sheet1 = DocumentSheet(
        id="sheet-uuid-1",
        document_id="doc-uuid-1",
        sheet_number=1,
        sheet_code="01",
        title="P&ID Area 100"
    )
    sheet2 = DocumentSheet(
        id="sheet-uuid-2",
        document_id="doc-uuid-1",
        sheet_number=2,
        sheet_code="02",
        title="P&ID Area 200"
    )
    db_session.add_all([sheet1, sheet2])
    db_session.commit()

    # Grupo 1: Compuerta detectada en Lámina 01 y 02 (total 3)
    g1 = SymbolInventoryGroup(
        id="group-1",
        review_run_id=run.id,
        grouping_key="gate_valve_group",
        grouping_method="template_match",
        display_code="V-001",
        canonical_name="Gate Valve",
        catalog_status="recognized_production",
        total_occurrences=3,
        occurrences_by_sheet={"sheet-uuid-1": 2, "sheet-uuid-2": 1},
        representative_occurrence_id="sym-exec-1"
    )

    # Ocurrencias con tags para Grupo 1
    sym1 = DetectedSymbol(
        id="sym-exec-1",
        document_id="doc-uuid-1",
        sheet_id="sheet-uuid-1",
        symbol_type="valve",
        inventory_group_id="group-1",
        detected_tag_or_code="HV-101",
        crop_image_path=None
    )
    sym2 = DetectedSymbol(
        id="sym-exec-2",
        document_id="doc-uuid-1",
        sheet_id="sheet-uuid-2",
        symbol_type="valve",
        inventory_group_id="group-1",
        detected_tag_or_code="HV-102",
        crop_image_path=None
    )
    sym3 = DetectedSymbol(
        id="sym-exec-3",
        document_id="doc-uuid-1",
        sheet_id="sheet-uuid-1",
        symbol_type="valve",
        inventory_group_id="group-1",
        detected_tag_or_code="HV-101",  # duplicado intencional para verificar deduplicación
        crop_image_path=None
    )

    # Grupo 2: Símbolo desconocido detectado en Lámina 01 (total 1)
    g2 = SymbolInventoryGroup(
        id="group-2",
        review_run_id=run.id,
        grouping_key="unknown_group",
        grouping_method="geometric_cluster",
        display_code="U-001",
        canonical_name="Unknown Symbol",
        catalog_status="unknown_symbol",
        total_occurrences=1,
        occurrences_by_sheet={"sheet-uuid-1": 1}
    )

    # Grupo 3: Símbolo detectado pero sin lámina identificable (total 2)
    g3 = SymbolInventoryGroup(
        id="group-3",
        review_run_id=run.id,
        grouping_key="unlocated_group",
        grouping_method="geometric_cluster",
        display_code="V-002",
        canonical_name="Ball Valve",
        catalog_status="recognized_production",
        total_occurrences=2,
        occurrences_by_sheet={}
    )

    db_session.add_all([g1, g2, g3, sym1, sym2, sym3])
    db_session.commit()

    summary_rows = SymbolInventoryService.generate_executive_summary(db_session, run, [g1, g2, g3])

    assert len(summary_rows) >= 3
    # El primer item debe ser el de mayor frecuencia (V-001, cantidad 3)
    row_v1 = summary_rows[0]
    assert row_v1["item_index"] == 1
    assert row_v1["symbol_code"] == "V-001"
    assert row_v1["found"] is True
    assert row_v1["quantity"] == 3
    assert "Lámina 01" in row_v1["sheets_display"]
    assert "Lámina 02" in row_v1["sheets_display"]
    # Validar tags deduplicados y crop_image_url
    assert row_v1["tags"] == ["HV-101", "HV-102"]
    assert row_v1["crop_image_url"] is None

    row_v2 = [r for r in summary_rows if r["symbol_code"] == "V-002"][0]
    assert row_v2["found"] is True
    assert row_v2["quantity"] == 2
    assert row_v2["sheets_display"] == "Ubicación no determinada"
    assert row_v2["tags"] == []

    # Debe haber items faltantes/esperados con found=False y quantity=0
    missing = [r for r in summary_rows if r["found"] is False]
    assert len(missing) > 0
    for m in missing:
        assert m["quantity"] == 0
        assert m["sheets_display"] == "-"
        assert m["tags"] == []
        assert m["crop_image_url"] is None

    # Validar que formatea en SymbolInventoryResponse sin fallar por extra kwargs (extra='forbid')
    formatted = SymbolInventoryService.format_run_inventory(db_session, run)
    parsed = SymbolInventoryResponse.model_validate(formatted)
    assert len(parsed.executive_summary) == len(summary_rows)
    assert parsed.executive_summary[0].item_index == 1
    assert parsed.executive_summary[0].found is True
    assert parsed.executive_summary[0].tags == ["HV-101", "HV-102"]

