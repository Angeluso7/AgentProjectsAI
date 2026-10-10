import os
import json
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.models.document_memory import Document, DocumentSheet, DetectedSymbol
from app.db.models.symbol_catalog import SymbolUnknownResearchCase, SymbolReviewDecision
from app.services.ai.claude_client import ClaudeClient, ClaudeClientDisabledError, ClaudeClientError
from app.services.symbols.research_service import SymbolResearchService
from app.core.settings import settings


def test_claude_client_complete_vision_disabled():
    client = ClaudeClient(api_key="")
    assert not client.is_available()
    with pytest.raises(ClaudeClientDisabledError):
        client.complete_vision(
            system_prompt="Test",
            user_prompt="Analyze this",
            image_path="non_existent.png"
        )


def test_claude_client_complete_vision_missing_image(tmp_path):
    mock_anthropic = MagicMock()
    client = ClaudeClient(api_key="sk-ant-testkey123", client=mock_anthropic)
    assert client.is_available()

    non_existent = str(tmp_path / "does_not_exist.png")
    with pytest.raises(ClaudeClientError) as exc_info:
        client.complete_vision(
            system_prompt="System",
            user_prompt="Analyze",
            image_path=non_existent
        )
    assert "No se encontró la imagen" in str(exc_info.value)


def test_claude_client_complete_vision_success(tmp_path):
    # Crear archivo de imagen temporal
    img_file = tmp_path / "crop.png"
    img_file.write_bytes(b"\x89PNG\r\n\x1a\nfakeimagecontent")

    mock_anthropic = MagicMock()
    mock_block = MagicMock()
    mock_block.text = '{"proposed_name": "Gate Valve", "proposed_standard_reference": "PIP PNC00001", "confidence": 0.95, "reasoning": "Standard gate valve body with stem"}'
    mock_response = MagicMock()
    mock_response.content = [mock_block]
    mock_anthropic.messages.create.return_value = mock_response

    client = ClaudeClient(api_key="sk-ant-testkey123", client=mock_anthropic)
    result = client.complete_vision(
        system_prompt="System prompt",
        user_prompt="User prompt",
        image_path=str(img_file),
    )

    assert result == mock_block.text
    mock_anthropic.messages.create.assert_called_once()
    call_kwargs = mock_anthropic.messages.create.call_args[1]
    assert call_kwargs["system"] == "System prompt"
    assert len(call_kwargs["messages"]) == 1
    content_blocks = call_kwargs["messages"][0]["content"]
    assert content_blocks[0]["type"] == "image"
    assert content_blocks[0]["source"]["media_type"] == "image/png"
    assert content_blocks[1]["type"] == "text"
    assert content_blocks[1]["text"] == "User prompt"


def test_symbol_research_service_format_sheet_label():
    sheet = DocumentSheet(sheet_number=1, sheet_code="PID-001", title="Planta General")
    assert SymbolResearchService.format_sheet_label(sheet) == "Lámina PID-001"

    sheet2 = DocumentSheet(sheet_number=3, sheet_code="", title="Detalle")
    assert SymbolResearchService.format_sheet_label(sheet2) == "Lámina 03"

    sheet3 = DocumentSheet(sheet_number=None, sheet_code="", title="Diagrama Principal")
    assert SymbolResearchService.format_sheet_label(sheet3) == "Diagrama Principal"

    assert SymbolResearchService.format_sheet_label(None) == "Lámina no especificada"


def test_symbol_research_service_ai_research_disabled_claude(db_session: Session, tmp_path):
    # Imagen real en disco
    img_path = str(tmp_path / "crop_test.png")
    with open(img_path, "wb") as f:
        f.write(b"fake image data")

    occ = DetectedSymbol(
        document_id="doc-001",
        sheet_id="sheet-001",
        symbol_type="valve",
        discipline="piping",
        crop_image_path=img_path,
        detected_tag_or_code="FV-999"
    )
    db_session.add(occ)
    db_session.flush()

    case = SymbolUnknownResearchCase(
        symbol_occurrence_id=occ.id,
        status="unknown",
        search_query="Unknown piping symbol"
    )
    db_session.add(case)
    db_session.commit()

    # Cliente deshabilitado
    disabled_client = ClaudeClient(api_key="")
    updated_case = SymbolResearchService.run_ai_research(
        db=db_session,
        research_case_id=case.id,
        claude_client=disabled_client
    )

    assert updated_case.status == "research_exhausted"
    assert "IA no configurada" in updated_case.research_notes


def test_symbol_research_service_ai_research_unparseable_response(db_session: Session, tmp_path):
    img_path = str(tmp_path / "crop_test.png")
    with open(img_path, "wb") as f:
        f.write(b"fake image data")

    occ = DetectedSymbol(
        document_id="doc-001",
        sheet_id="sheet-001",
        symbol_type="valve",
        discipline="piping",
        crop_image_path=img_path
    )
    db_session.add(occ)
    db_session.flush()

    case = SymbolUnknownResearchCase(
        symbol_occurrence_id=occ.id,
        status="unknown"
    )
    db_session.add(case)
    db_session.commit()

    # Mock cliente que responde texto crudo sin JSON
    mock_client = MagicMock()
    mock_client.complete_vision.return_value = "No estoy seguro, parece una válvula pero no tengo certeza."

    updated_case = SymbolResearchService.run_ai_research(
        db=db_session,
        research_case_id=case.id,
        claude_client=mock_client
    )

    assert updated_case.status == "sources_found"
    assert "Respuesta IA no parseable" in updated_case.research_notes


def test_symbol_research_service_ai_research_success(db_session: Session, tmp_path):
    img_path = str(tmp_path / "crop_test.png")
    with open(img_path, "wb") as f:
        f.write(b"fake image data")

    occ = DetectedSymbol(
        document_id="doc-001",
        sheet_id="sheet-001",
        symbol_type="valve",
        discipline="piping",
        crop_image_path=img_path,
        detected_tag_or_code="HV-101"
    )
    db_session.add(occ)
    db_session.flush()

    case = SymbolUnknownResearchCase(
        symbol_occurrence_id=occ.id,
        status="unknown"
    )
    db_session.add(case)
    db_session.commit()

    # Mock cliente con respuesta JSON estructurada
    mock_client = MagicMock()
    mock_client.complete_vision.return_value = json.dumps({
        "proposed_name": "Butterfly Valve",
        "proposed_standard_reference": "PIP PNC00001",
        "confidence": 0.92,
        "reasoning": "Disco circular central atravesado por eje vertical característico de válvula mariposa."
    })

    updated_case = SymbolResearchService.run_ai_research(
        db=db_session,
        research_case_id=case.id,
        claude_client=mock_client
    )

    assert updated_case.status == "proposed_identity"
    assert updated_case.proposed_name == "Butterfly Valve"
    assert updated_case.proposed_standard_reference == "PIP PNC00001"
    assert "Confianza IA: 0.92" in updated_case.research_notes
    assert "válvula mariposa" in updated_case.research_notes


def test_symbol_research_service_dismiss_case(db_session: Session):
    occ = DetectedSymbol(
        document_id="doc-001",
        sheet_id="sheet-001",
        symbol_type="valve",
        discipline="piping",
    )
    db_session.add(occ)
    db_session.flush()

    case = SymbolUnknownResearchCase(
        symbol_occurrence_id=occ.id,
        status="sources_found",
        research_notes="Investigación inicial"
    )
    db_session.add(case)
    db_session.commit()

    dismissed = SymbolResearchService.dismiss_case(
        db=db_session,
        research_case_id=case.id,
        reviewer_id="reviewer_lead_01",
        rationale="Elemento gráfico fuera de disciplina de piping (logo del cliente)."
    )

    assert dismissed.status == "unresolved"
    assert "[Descartado por reviewer_lead_01]" in dismissed.research_notes
    assert "logo del cliente" in dismissed.research_notes

    # Verificar que se registró la decisión de auditoría
    decision = db_session.query(SymbolReviewDecision).filter(
        SymbolReviewDecision.subject_id == case.id,
        SymbolReviewDecision.decision == "dismiss"
    ).first()
    assert decision is not None
    assert decision.reviewer_id == "reviewer_lead_01"


def test_research_cases_api_endpoints(db_session: Session, tmp_path):
    # Crear documento, lámina y ocurrencia con recorte en disco
    crop_dir = os.path.join(settings.STORAGE_LOCAL_ROOT, "crops", "api_test")
    os.makedirs(crop_dir, exist_ok=True)
    crop_path = os.path.join(crop_dir, "sym_api.png")
    with open(crop_path, "wb") as f:
        f.write(b"fake image data")

    doc = Document(
        project_id="proj-101",
        filename="PID-AREA-100.pdf"
    )
    db_session.add(doc)
    db_session.flush()

    sheet = DocumentSheet(
        document_id=doc.id,
        sheet_number=1,
        sheet_code="01",
        title="Área 100"
    )
    db_session.add(sheet)
    db_session.flush()

    occ = DetectedSymbol(
        document_id=doc.id,
        sheet_id=sheet.id,
        symbol_type="valve",
        discipline="piping",
        crop_image_path=crop_path,
        detected_tag_or_code="XV-2001"
    )
    db_session.add(occ)
    db_session.flush()

    case = SymbolUnknownResearchCase(
        symbol_occurrence_id=occ.id,
        status="unknown",
        search_query="Unknown piping symbol"
    )
    db_session.add(case)
    db_session.commit()

    client = TestClient(app)

    # 1. GET /api/v1/symbol-catalog/research-cases
    resp = client.get("/api/v1/symbol-catalog/research-cases")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    item = next((x for x in data if x["id"] == case.id), None)
    assert item is not None
    assert item["status"] == "unknown"
    assert item["detected_tag_or_code"] == "XV-2001"
    assert item["document_filename"] == "PID-AREA-100.pdf"
    assert item["sheet_label"] == "Lámina 01"
    assert item["crop_image_url"] == "/data/crops/api_test/sym_api.png"

    # 2. GET /api/v1/symbol-catalog/research-cases/{case_id}
    resp_detail = client.get(f"/api/v1/symbol-catalog/research-cases/{case.id}")
    assert resp_detail.status_code == 200
    detail = resp_detail.json()
    assert detail["id"] == case.id
    assert detail["crop_image_url"] == "/data/crops/api_test/sym_api.png"

    # 3. POST /api/v1/symbol-catalog/research-cases/{case_id}/ai-research (sin API key -> research_exhausted, no 500)
    with patch.object(ClaudeClient, "is_available", return_value=False):
        resp_ai = client.post(f"/api/v1/symbol-catalog/research-cases/{case.id}/ai-research")
        assert resp_ai.status_code == 200
        ai_data = resp_ai.json()
        assert ai_data["status"] == "research_exhausted"
        assert "IA no configurada" in ai_data["research_notes"]

    # 4. POST /api/v1/symbol-catalog/research-cases/{case_id}/dismiss
    resp_dismiss = client.post(
        f"/api/v1/symbol-catalog/research-cases/{case.id}/dismiss",
        json={"reviewer_id": "auditor_lead", "rationale": "Símbolo duplicado"}
    )
    assert resp_dismiss.status_code == 200
    dismiss_data = resp_dismiss.json()
    assert dismiss_data["status"] == "unresolved"
    assert "Símbolo duplicado" in dismiss_data["research_notes"]


def test_symbol_research_service_promote_lifecycle(db_session: Session, tmp_path):
    import cv2
    import numpy as np

    crop_path = str(tmp_path / "valid_symbol_crop.png")
    img = np.ones((100, 100, 3), dtype=np.uint8) * 255
    cv2.circle(img, (50, 50), 20, (0, 0, 0), 2)
    cv2.imwrite(crop_path, img)

    occ = DetectedSymbol(
        document_id="doc-prom-01",
        sheet_id="sheet-prom-01",
        symbol_type="valve",
        discipline="piping",
        crop_image_path=crop_path,
        detected_tag_or_code="FV-555",
        geometric_evidence=True,
        geometric_confidence=0.95
    )
    db_session.add(occ)
    db_session.flush()

    case = SymbolUnknownResearchCase(
        symbol_occurrence_id=occ.id,
        status="proposed_identity",
        proposed_name="Gate Valve",
        proposed_standard_reference="PIP PNC00001",
        research_notes="Investigado por IA"
    )
    db_session.add(case)
    db_session.commit()

    # 1. Probar promote via Service
    res = SymbolResearchService.validate_and_promote(
        db=db_session,
        research_case_id=case.id,
        reviewer_id="lead_reviewer_01",
        canonical_code="PIP-VALVE-GATE-TEST-01",
        canonical_name="Gate Valve Test 01",
        category="valve",
        subcategory="gate_valve",
        discipline="piping",
        standard_reference="PIP PNC00001",
        evidence_kind="redacted_real",
        rationale="Aprobado en sesión de revisión HITL",
    )

    assert res["canonical_code"] == "PIP-VALVE-GATE-TEST-01"
    assert res["status"] == "active"
    assert res["template_id"] is not None
    assert res["template_version_id"] is not None

    db_session.refresh(case)
    assert case.status == "human_validated"
    assert case.proposed_name == "Gate Valve Test 01"

    # 2. Probar promote via Endpoint
    case2 = SymbolUnknownResearchCase(
        symbol_occurrence_id=occ.id,
        status="proposed_identity",
        proposed_name="Gate Valve 02",
        proposed_standard_reference="PIP PNC00001"
    )
    db_session.add(case2)
    db_session.commit()

    client = TestClient(app)
    resp_promo = client.post(
        f"/api/v1/symbol-catalog/research-cases/{case2.id}/promote",
        json={
            "reviewer_id": "auditor_lead",
            "canonical_code": "PIP-VALVE-GATE-TEST-02",
            "canonical_name": "Gate Valve Test 02",
            "category": "valve",
            "subcategory": "gate_valve",
            "discipline": "piping",
            "standard_reference": "PIP PNC00001",
            "evidence_kind": "redacted_real",
            "rationale": "Promoción vía API"
        }
    )
    assert resp_promo.status_code == 200
    promo_data = resp_promo.json()
    assert promo_data["canonical_code"] == "PIP-VALVE-GATE-TEST-02"
    assert promo_data["research_case"]["status"] == "human_validated"
    assert promo_data["template_id"] is not None

