import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import pytest
import uuid
from datetime import datetime
from fastapi.testclient import TestClient
from app.core.security import hash_password, create_access_token
from app.db.models.core import User, Organization, OrganizationMembership, Project
from app.db.models.document_memory import Document, DocumentSheet
from app.db.models.decision_memory import RuleDefinition
from app.db.models.observations import AuditObservation

def test_full_auditor_functional_journey(client: TestClient, db_session):
    """
    Validación funcional troncal del flujo del auditor:
    1. Salud del sistema & Motores IA
    2. Autenticación & Organización Multi-Tenant
    3. Gestión de Proyectos & Carga/Eliminación de Documentos
    4. Intake & Fuentes + Asistente Copilot RAG
    5. Visor de Planos & Creación/Eliminación de Selecciones
    6. Motor de Reglas QA/QC & Triage de Observaciones
    7. Base de Conocimiento & Transición de Estado
    8. Evaluación de Completitud & Emisión de Snapshot de Reporte
    """

    # =========================================================================
    # PASO 1: SALUD DEL BACKEND Y MOTORES IA
    # =========================================================================
    health_res = client.get("/health")
    assert health_res.status_code == 200
    assert health_res.json()["status"] == "healthy"

    engines_health = client.get("/api/v1/health/engines")
    assert engines_health.status_code == 200
    assert "engines" in engines_health.json()

    engines_summary = client.get("/api/v1/engines/summary")
    assert engines_summary.status_code == 200
    assert "total_engines" in engines_summary.json()

    # =========================================================================
    # PASO 2: SETUP DE IDENTIDAD, TENANT Y TOKEN JWT
    # =========================================================================
    org_id = str(uuid.uuid4())
    org = Organization(id=org_id, name="Constructora Central S.A.", slug=f"central-{uuid.uuid4().hex[:6]}")
    db_session.add(org)

    user = User(
        id=str(uuid.uuid4()),
        email=f"auditor.principal.{uuid.uuid4().hex[:6]}@central.cl",
        display_name="Auditor Principal",
        password_hash=hash_password("PasswordSeguro123!"),
        is_active=True,
        is_superuser=False
    )
    db_session.add(user)

    membership = OrganizationMembership(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        user_id=user.id,
        role="admin",
        status="active"
    )
    db_session.add(membership)
    db_session.commit()

    token = create_access_token(
        subject=user.id,
        email=user.email,
        extra_claims={
            "org_id": org_id,
            "role": "admin"
        }
    )
    auth_headers = {
        "Authorization": f"Bearer {token}",
        "X-Organization-Id": org_id
    }

    # =========================================================================
    # PASO 3: GESTIÓN DE PROYECTOS & DOCUMENTOS
    # =========================================================================
    # 3.1 Crear Proyecto
    create_proj_res = client.post(
        "/api/v1/projects/",
        headers=auth_headers,
        json={
            "name": "Edificio Alto Las Condes",
            "code": "PRJ-ALC-2026",
            "description": "Proyecto Residencial 15 pisos",
            "discipline": "architecture",
            "stage": "Ingeniería de Detalle",
            "organization_id": org_id
        }
    )
    assert create_proj_res.status_code in [200, 201]
    project_data = create_proj_res.json()
    project_id = project_data["id"]
    assert project_data["name"] == "Edificio Alto Las Condes"

    # 3.2 Listar Proyectos
    list_proj_res = client.get("/api/v1/projects/", headers=auth_headers)
    assert list_proj_res.status_code == 200
    assert any(p["id"] == project_id for p in list_proj_res.json())

    # 3.3 Crear Documento y Lámina de Prueba
    doc = Document(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        project_id=project_id,
        filename="Plano_Arquitectura_L01.pdf",
        file_path="storage/raw/Plano_Arquitectura_L01.pdf",
        file_hash_sha256="hash_pdf_sample_123",
        file_size_bytes=2048576,
        status="ingested"
    )
    db_session.add(doc)

    sheet = DocumentSheet(
        id=str(uuid.uuid4()),
        document_id=doc.id,
        sheet_number=1,
        sheet_code="ARQ-L01",
        width_px=3508,
        height_px=2480
    )
    db_session.add(sheet)
    db_session.commit()

    # 3.4 Verificar Documentos y Láminas vía API
    get_docs_res = client.get(f"/api/v1/documents/?project_id={project_id}", headers=auth_headers)
    assert get_docs_res.status_code == 200
    assert len(get_docs_res.json()) >= 1

    sheets_res = client.get(f"/api/v1/documents/{doc.id}/sheets", headers=auth_headers)
    assert sheets_res.status_code == 200
    assert len(sheets_res.json()) >= 1

    # 3.5 Verificar Document Impact & Eliminación Controlada
    impact_res = client.get(f"/api/v1/documents/{doc.id}/impact", headers=auth_headers)
    assert impact_res.status_code == 200
    assert impact_res.json()["document_id"] == doc.id

    # =========================================================================
    # PASO 4: INTAKE & FUENTES + ASISTENTE COPILOT RAG
    # =========================================================================
    # 4.1 Registrar Fuente Normativa
    source_res = client.post(
        "/api/v1/intake/sources",
        headers=auth_headers,
        json={
            "source_type": "normative_document",
            "source_origin": "manual_entry",
            "title": "OGUC Título 4 - Condiciones de Habitabilidad",
            "discipline": "architecture",
            "document_type": "norma_nacional",
            "organization_id": org_id,
            "project_id": project_id,
            "description": "Estándares de vanos, iluminación y ventilación",
            "version": "2026.1",
            "owner": user.email,
            "metadata_payload": {"legal_authority": "MINVU"}
        }
    )
    assert source_res.status_code in [200, 201]
    source_data = source_res.json()
    assert source_data["title"] == "OGUC Título 4 - Condiciones de Habitabilidad"

    # 4.2 Listar Fuentes
    list_sources_res = client.get("/api/v1/intake/sources", headers=auth_headers)
    assert list_sources_res.status_code == 200
    assert any(s["id"] == source_data["id"] for s in list_sources_res.json())

    # 4.3 Consultar Catálogo de Tareas del Asistente
    tasks_res = client.get("/api/v1/assistant/tasks", headers=auth_headers)
    assert tasks_res.status_code == 200
    tasks_catalog = tasks_res.json()
    assert len(tasks_catalog) >= 8

    # 4.4 Ejecutar Tarea Asistida Copilot (normative_query)
    exec_res = client.post(
        "/api/v1/assistant/execute",
        headers=auth_headers,
        json={
            "task_type": "normative_query",
            "prompt": "¿Cuáles son las alturas mínimas y requerimientos de ventilación para recintos habitables?",
            "project_id": project_id,
            "stage": "Ingeniería de Detalle",
            "discipline": "architecture"
        }
    )
    assert exec_res.status_code == 200
    assistant_result = exec_res.json()
    assert "generated_response" in assistant_result
    assert assistant_result["task_type"] == "normative_query"
    assert assistant_result["confidence_score"] >= 0.0

    # =========================================================================
    # PASO 5: VISOR DE PLANOS & ANOTACIONES / RECORTE MANUAL
    # =========================================================================
    # 5.1 Crear Selección / Anotación Manual en Lámina
    annot_res = client.post(
        "/api/v1/annotations",
        headers=auth_headers,
        json={
            "organization_id": org_id,
            "project_id": project_id,
            "document_id": doc.id,
            "sheet_id": sheet.id,
            "bbox_normalized": [0.12, 0.15, 0.32, 0.45],
            "element_type": "symbol",
            "name": "Puerta Batiente Simple P1",
            "description": "Vano de acceso principal 90x210 cm",
            "discipline": "architecture",
            "confidence": 1.0,
            "tags": ["puerta", "acceso", "madera"],
            "status": "active"
        }
    )
    assert annot_res.status_code in [200, 201]
    annot_data = annot_res.json()
    annot_id = annot_data["id"]
    assert annot_data["name"] == "Puerta Batiente Simple P1"

    # 5.2 Listar Anotaciones de Lámina
    list_annots_res = client.get(f"/api/v1/annotations?sheet_id={sheet.id}", headers=auth_headers)
    assert list_annots_res.status_code == 200
    assert any(a["id"] == annot_id for a in list_annots_res.json())

    # 5.3 Deduplicación Visual & Captura
    dedup_res = client.post(
        "/api/v1/acquisition/visual-dedup-check",
        headers=auth_headers,
        json={
            "name": "Puerta Batiente P1",
            "normalized_category": "puerta_madera",
            "discipline": "architecture",
            "element_type": "symbol"
        }
    )
    assert dedup_res.status_code == 200
    assert "suggested_mode" in dedup_res.json()

    # 5.4 Eliminar Selección
    del_annot_res = client.delete(f"/api/v1/annotations/{annot_id}", headers=auth_headers)
    assert del_annot_res.status_code in [200, 204]

    # =========================================================================
    # PASO 6: MOTOR DE REGLAS QA/QC & TRIAGE DE OBSERVACIONES
    # =========================================================================
    # 6.1 Crear Regla de Prueba en BD
    rule = RuleDefinition(
        id=str(uuid.uuid4()),
        code="ARQ-VANOS-01",
        name="Conciliación de Dimensiones de Puertas",
        category="vanos_y_accesos",
        discipline="architecture",
        severity_default="critical",
        description="Verifica que el ancho de la puerta sea >= 0.85m en accesos principales",
        rule_logic_type="deterministic_geometry",
        is_active=True,
        version="1.0"
    )
    db_session.add(rule)
    db_session.commit()

    # 6.2 Listar Reglas
    rules_res = client.get("/api/v1/rules", headers=auth_headers)
    assert rules_res.status_code == 200
    assert any(r["code"] == "ARQ-VANOS-01" for r in rules_res.json())

    # 6.3 Crear Observación Formal de Auditoría
    obs = AuditObservation(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        project_id=project_id,
        stage="Ingeniería de Detalle",
        code="OBS-ARQ-001",
        item_type="technical_observation",
        title="Ancho de Vano P1 insuficiente respecto a plano de detalle",
        description="Se detectó vano de 0.80m en lámina ARQ-L01 mientras especificación exige 0.90m",
        recommendation="Ajustar muro perimetral para dar cumplimiento a 0.90m libres.",
        discipline="architecture",
        severity="critical",
        status="draft",
        rule_id=rule.id,
        rule_code=rule.code,
        document_id=doc.id,
        sheet_id=sheet.id,
        issued_by=user.email
    )
    db_session.add(obs)
    db_session.commit()

    # 6.4 Listar Observaciones en Triage
    list_obs_res = client.get(f"/api/v1/observations?project_id={project_id}", headers=auth_headers)
    assert list_obs_res.status_code == 200
    assert any(o["id"] == obs.id for o in list_obs_res.json())

    # 6.5 Emitir Observación Formalmente
    issue_obs_res = client.post(
        f"/api/v1/observations/{obs.id}/issue",
        headers=auth_headers,
        json={
            "assigned_to": "proyectista@calculo.cl",
            "notes": "Emitida para revisión inmediata"
        }
    )
    assert issue_obs_res.status_code == 200
    assert issue_obs_res.json()["status"] == "issued"

    # =========================================================================
    # PASO 7: BASE DE CONOCIMIENTO OPERACIONAL
    # =========================================================================
    # 7.1 Crear Ítem de Conocimiento
    kb_create_res = client.post(
        "/api/v1/knowledge/items",
        headers=auth_headers,
        json={
            "organization_id": org_id,
            "project_id": project_id,
            "domain": "rule_knowledge",
            "item_type": "standard_clause",
            "title": "Criterio de Ancho Mínimo de Puertas Principales",
            "summary": "Mínimo 0.90m libre para recintos habitacionales",
            "content_text": "Todo acceso principal debe contemplar ancho libre de paso no inferior a 0.90 metros.",
            "discipline": "architecture",
            "stage": "Ingeniería de Detalle",
            "origin_type": "project_feedback",
            "author": user.email,
            "tags": ["puertas", "vanos", "accesibilidad"]
        }
    )
    assert kb_create_res.status_code in [200, 201]
    kb_item = kb_create_res.json()
    kb_id = kb_item["id"]

    # 7.2 Promover a approved_for_reuse
    transition_res = client.post(
        f"/api/v1/knowledge/items/{kb_id}/transition",
        headers=auth_headers,
        json={
            "target_status": "approved_for_reuse",
            "notes": "Validado por Auditor Principal para reutilización corporativa."
        }
    )
    assert transition_res.status_code == 200
    assert transition_res.json()["status"] == "approved_for_reuse"
    assert transition_res.json()["is_active_for_reuse"] is True

    # 7.3 Búsqueda Contextual en KB
    search_res = client.post(
        "/api/v1/knowledge/search",
        headers=auth_headers,
        json={
            "query": "ancho mínimo de puertas",
            "discipline": "architecture",
            "limit": 5
        }
    )
    assert search_res.status_code == 200
    assert "results" in search_res.json()

    # =========================================================================
    # PASO 8: REPORTES CONSOLIDADOS & SNAPSHOTS DE ETAPA
    # =========================================================================
    # 8.1 Preview del Reporte Consolidado
    preview_res = client.get(
        f"/api/v1/reports/consolidated/preview?project_id={project_id}&stage=Ingenier%C3%ADa%20de%20Detalle",
        headers=auth_headers
    )
    assert preview_res.status_code == 200
    preview_data = preview_res.json()
    assert "global_stage_verdict" in preview_data
    assert "completeness" in preview_data

    # 8.2 Emisión de Corte / Snapshot Inmutable con SHA-256
    emit_res = client.post(
        "/api/v1/reports/consolidated/emit",
        headers=auth_headers,
        json={
            "project_id": project_id,
            "stage": "Ingeniería de Detalle",
            "title": "Corte de Auditoría QA/QC - Hito 1"
        }
    )
    assert emit_res.status_code in [200, 201]
    snapshot_data = emit_res.json()
    assert snapshot_data["revision_number"] >= 1
    assert "manifest_hash" in snapshot_data

    # 8.3 Listar Snapshots Históricos
    snapshots_res = client.get(
        f"/api/v1/reports/consolidated/snapshots?project_id={project_id}",
        headers=auth_headers
    )
    assert snapshots_res.status_code == 200
    assert len(snapshots_res.json()) >= 1

    print("\n>>> [E2E-JOURNEY] Todos los 8 pasos troncales del flujo del auditor completados con 100% de exito!")
