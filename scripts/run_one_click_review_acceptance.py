import os
import io
import sys
import json
import uuid
import hashlib
import requests
from datetime import datetime

# Add backend directory to sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.db.session import SessionLocal
from app.db.models.core import User, OrganizationMembership, Project
from app.db.models.document_memory import Document, DocumentSheet, DetectedSymbol, SheetRegion
from app.db.models.template_memory import SymbolTemplate
from app.db.models.symbol_catalog import SymbolTemplateVersion
from app.core.security import create_access_token

BASE_URL = "http://localhost:8000/api/v1"

def run_acceptance():
    print("=" * 70)
    print("🚀 INICIANDO ACEPTACIÓN FUNCIONAL DE ONE-CLICK REVIEW (PIPING → PID_SYMBOLS)")
    print("=" * 70)

    db = SessionLocal()
    try:
        # 1. Obtener usuario activo y generar token JWT
        user = db.query(User).filter(User.is_active == True).first()
        if not user:
            raise RuntimeError("No se encontró usuario activo en la base de datos.")
        mem = db.query(OrganizationMembership).filter(
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.status == "active"
        ).first()
        role = mem.role if mem else "admin"
        token = create_access_token(user.id, email=user.email, extra_claims={"role": role})
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        print(f"✓ [AUTH] Token generado para {user.email} (rol: {role})")

        # 2. Verificar taxonomía en backend
        res_disc = requests.get(f"{BASE_URL}/review/disciplines?active_only=true", headers=headers)
        assert res_disc.status_code == 200, f"Error listando disciplinas: {res_disc.text}"
        disciplines = res_disc.json()
        print(f"✓ [TAXONOMY] Disciplinas disponibles: {[d['code'] for d in disciplines]}")
        assert any(d["code"] == "PIPING" for d in disciplines), "Falta disciplina PIPING"

        res_topics = requests.get(f"{BASE_URL}/review/topics?discipline_code=PIPING&active_only=true", headers=headers)
        assert res_topics.status_code == 200, f"Error listando tópicos: {res_topics.text}"
        topics = res_topics.json()
        print(f"✓ [TAXONOMY] Tópicos disponibles para PIPING: {[t['code'] for t in topics]}")
        assert any(t["code"] == "PID_SYMBOLS" for t in topics), "Falta tópico PID_SYMBOLS"

        # 3. Crear proyecto de prueba no sensible
        suffix = str(uuid.uuid4())[:6].upper()
        proj_code = f"PRJ-ACCEPT-PIP-{suffix}"
        res_proj = requests.post(f"{BASE_URL}/projects/", json={
            "name": f"Proyecto Aceptación One-Click Review UI {suffix}",
            "code": proj_code,
            "description": "Proyecto para validación y aceptación funcional de One-Click Review",
            "stage": "Factibilidad"
        }, headers=headers)
        assert res_proj.status_code == 201, f"Error creando proyecto: {res_proj.text}"
        project = res_proj.json()
        proj_id = project["id"]
        print(f"✓ [PROJECT] Proyecto creado: {project['name']} (ID: {proj_id}, Código: {proj_code})")

        # 4. Crear documentos y láminas con simbología en el proyecto
        # Documento 1: Leyenda P&ID
        doc1_id = f"doc-leg-{suffix.lower()}"
        doc1 = Document(
            id=doc1_id,
            project_id=proj_id,
            organization_id=project["organization_id"],
            filename="PID_Legend_PNC00001_Fixture.pdf",
            file_path=f"/storage/{doc1_id}.pdf",
            file_hash_sha256=hashlib.sha256(f"legend-{suffix}".encode()).hexdigest(),
            file_size_bytes=1048576,
            page_count=1,
            status="ready",
            metadata_info={"document_type": "legend_sheet", "discipline": "piping"}
        )
        db.add(doc1)
        db.flush()

        sheet1_id = f"sheet-leg-{suffix.lower()}"
        sheet1 = DocumentSheet(
            id=sheet1_id,
            document_id=doc1.id,
            sheet_number=1,
            sheet_code="LEG-01",
            title="Simbología y Abreviaturas de Cañerías",
            width_px=3300,
            height_px=2550
        )
        db.add(sheet1)
        db.flush()

        reg1 = SheetRegion(
            sheet_id=sheet1.id,
            region_type="drawing_area",
            bbox=[200, 200, 3100, 2350],
            bbox_normalized=[0.06, 0.08, 0.94, 0.92],
            polygon_points=[[0.06, 0.08], [0.94, 0.08], [0.94, 0.92], [0.06, 0.92]]
        )
        db.add(reg1)

        # Documento 2: Diagrama P&ID principal con válvulas
        doc2_id = f"doc-diag-{suffix.lower()}"
        doc2 = Document(
            id=doc2_id,
            project_id=proj_id,
            organization_id=project["organization_id"],
            filename="PID_Piping_Diagram_Loop101.pdf",
            file_path=f"/storage/{doc2_id}.pdf",
            file_hash_sha256=hashlib.sha256(f"diagram-{suffix}".encode()).hexdigest(),
            file_size_bytes=2097152,
            page_count=1,
            status="ready",
            metadata_info={"document_type": "piping_diagram", "discipline": "piping"}
        )
        db.add(doc2)
        db.flush()

        sheet2_id = f"sheet-diag-{suffix.lower()}"
        sheet2 = DocumentSheet(
            id=sheet2_id,
            document_id=doc2.id,
            sheet_number=1,
            sheet_code="PID-101",
            title="Diagrama P&ID Lazos de Control 101",
            width_px=3300,
            height_px=2550
        )
        db.add(sheet2)
        db.flush()

        reg2 = SheetRegion(
            sheet_id=sheet2.id,
            region_type="drawing_area",
            bbox=[250, 250, 3100, 2300],
            bbox_normalized=[0.075, 0.098, 0.939, 0.902],
            polygon_points=[[0.075, 0.098], [0.939, 0.098], [0.939, 0.902], [0.075, 0.902]]
        )
        db.add(reg2)

        # Símbolo 1: Válvula reconocida (V-101)
        sym1 = DetectedSymbol(
            id=f"sym-valve-{suffix.lower()}",
            document_id=doc2.id,
            sheet_id=sheet2.id,
            discipline="piping",
            symbol_type="gate_valve",
            confidence=0.96,
            bbox=[450.0, 600.0, 550.0, 700.0],
            bbox_normalized=[0.136, 0.235, 0.166, 0.274],
            environment="sandbox",
            match_evidence={
                "tag_or_code": "V-101",
                "canonical_name": "gate_valve",
                "standard": "PIP PNC00001",
                "spec": "A1A",
                "is_recognized": True
            }
        )
        # Símbolo 2: Componente desconocido / exploratorio
        sym2 = DetectedSymbol(
            id=f"sym-unknown-{suffix.lower()}",
            document_id=doc2.id,
            sheet_id=sheet2.id,
            discipline="piping",
            symbol_type="unknown_actuator",
            confidence=0.38,
            bbox=[1200.0, 850.0, 1350.0, 980.0],
            bbox_normalized=[0.363, 0.333, 0.409, 0.384],
            environment="sandbox",
            match_evidence={
                "tag_or_code": "SYM-UNKNOWN-099",
                "canonical_name": "unknown_actuator",
                "standard": "PIP PNC00001",
                "is_recognized": False
            }
        )
        db.add_all([sym1, sym2])
        db.commit()
        print(f"✓ [DOCUMENTS] Creados 2 documentos fixture y 2 símbolos en lámina PID-101")

        # 5. Confirmar visibilidad de documentos en el proyecto
        res_docs = requests.get(f"{BASE_URL}/projects/{proj_id}/documents", headers=headers)
        assert res_docs.status_code == 200, f"Error listando documentos: {res_docs.text}"
        proj_docs = res_docs.json()
        print(f"✓ [VISIBILITY] Documentos visibles en el proyecto: {[d['filename'] for d in proj_docs]}")
        assert len(proj_docs) == 2, f"Se esperaban 2 documentos, hay {len(proj_docs)}"

        # 6. Generar Pre-flight Plan en SANDBOX
        res_plan_sbx = requests.post(f"{BASE_URL}/review/plan", json={
            "project_id": proj_id,
            "discipline_code": "PIPING",
            "topic_code": "PID_SYMBOLS",
            "document_ids": [doc1_id, doc2_id],
            "mode": "sandbox"
        }, headers=headers)
        assert res_plan_sbx.status_code == 200, f"Error generando plan sandbox: {res_plan_sbx.text}"
        plan_sbx = res_plan_sbx.json()
        print(f"✓ [PRE-FLIGHT SANDBOX] can_execute: {plan_sbx['can_execute']}")
        print(f"  - Reglas aplicables: {len(plan_sbx['applicable_rules'])} ({[r['code'] for r in plan_sbx['applicable_rules']]})")
        print(f"  - Fases de blueprint: {len(plan_sbx.get('phases_blueprint', []))}")
        print(f"  - Limitaciones reportadas: {plan_sbx.get('limitations')}")
        assert plan_sbx["can_execute"] is True, "Plan sandbox debería ser ejecutable"
        assert len(plan_sbx["applicable_rules"]) >= 4, "Deberían haber al menos 4 reglas"

        # 7. Generar Pre-flight Plan en PRODUCTION
        res_plan_prod = requests.post(f"{BASE_URL}/review/plan", json={
            "project_id": proj_id,
            "discipline_code": "PIPING",
            "topic_code": "PID_SYMBOLS",
            "document_ids": [doc1_id, doc2_id],
            "mode": "production"
        }, headers=headers)
        assert res_plan_prod.status_code == 200, f"Error generando plan production: {res_plan_prod.text}"
        plan_prod = res_plan_prod.json()
        print(f"✓ [PRE-FLIGHT PRODUCTION] can_execute: {plan_prod['can_execute']}, Limitaciones: {plan_prod.get('limitations')}")

        # 8. Ejecutar One-Click Review en modo SANDBOX
        res_exec_sbx = requests.post(f"{BASE_URL}/review/runs", json={
            "project_id": proj_id,
            "discipline_code": "PIPING",
            "topic_code": "PID_SYMBOLS",
            "document_ids": [doc1_id, doc2_id],
            "mode": "sandbox",
            "run_name": f"Aceptación UI One-Click Review Sandbox {suffix}"
        }, headers=headers)
        assert res_exec_sbx.status_code == 201, f"Error ejecutando revisión: {res_exec_sbx.text}"
        exec_sbx = res_exec_sbx.json()
        run_id = exec_sbx["review_run_id"]
        print(f"✓ [EXECUTION SANDBOX] Corrida finalizada exitosamente! Run ID: {run_id}")

        # 9. Consultar detalles de la corrida
        res_run_details = requests.get(f"{BASE_URL}/review/runs/{run_id}", headers=headers)
        assert res_run_details.status_code == 200, f"Error consultando corrida: {res_run_details.text}"
        run_details = res_run_details.json()
        print(f"✓ [RUN DETAILS] Estado: {run_details['status']}, Modo: {run_details['execution_mode']}")
        print(f"  - Pasos ejecutados: {len(run_details['steps'])} pasos")
        for st in run_details['steps']:
            print(f"    * Fase {st['phase']} ({st['phase_name']}): {st['status']}")
        print(f"  - Ejecuciones de reglas: {len(run_details['executions'])} reglas")
        print(f"  - Hallazgos detectados: {len(run_details['findings'])} hallazgos")

        # 10. Validar Contrato de Hallazgos Sandbox y Contexto de Navegación
        assert len(run_details["findings"]) > 0, "Se esperaba al menos 1 hallazgo en sandbox"
        for f in run_details["findings"]:
            print(f"  [HALLAZGO] {f['rule_code']} ({f['severity'].upper()}): {f['title']}")
            assert f["evidence_refs"].get("execution_mode") == "sandbox", "Debe ser sandbox"
            assert f["evidence_refs"].get("is_exploratory") is True, "Debe ser exploratorio"
            assert "Resultado exploratorio" in f["evidence_refs"].get("warning", ""), "Falta advertencia"
            assert "[SANDBOX]" in f["title"], "Debe tener prefijo [SANDBOX]"
            
            # Verificar navigation_context
            nav_ctx = f.get("navigation_context") or {}
            print(f"    -> Contexto Navegación: doc_id={nav_ctx.get('document_id')}, sheet_id={nav_ctx.get('sheet_id')}, bbox={f.get('bbox')}")
            assert nav_ctx.get("document_id") == doc2_id, "Contexto debe apuntar a doc2"
            assert nav_ctx.get("sheet_id") == sheet2_id, "Contexto debe apuntar a sheet2"
            assert f.get("bbox") is not None, "Debe tener coordenadas BBox"

        # 11. Generar Exportaciones Persistidas (JSON, XLSX, PDF)
        print("\n--- Generando y Validando Exportaciones Persistidas ---")
        
        # Export JSON
        res_exp_json = requests.post(f"{BASE_URL}/review/runs/{run_id}/exports", json={"format": "json"}, headers=headers)
        assert res_exp_json.status_code == 201, f"Error exportando JSON: {res_exp_json.text}"
        exp_json = res_exp_json.json()
        print(f"✓ [EXPORT JSON] Creado: {exp_json['artifact_path']} (SHA256: {exp_json['sha256'][:16]}...)")
        assert os.path.exists(exp_json["artifact_path"]), "Archivo JSON no existe en disco"
        with open(exp_json["artifact_path"], "r", encoding="utf-8") as jf:
            jdata = json.load(jf)
            assert jdata["execution_mode"] == "sandbox"
            assert jdata["project_id"] == proj_id

        # Export XLSX
        res_exp_xlsx = requests.post(f"{BASE_URL}/review/runs/{run_id}/exports", json={"format": "xlsx"}, headers=headers)
        assert res_exp_xlsx.status_code == 201, f"Error exportando XLSX: {res_exp_xlsx.text}"
        exp_xlsx = res_exp_xlsx.json()
        print(f"✓ [EXPORT XLSX] Creado: {exp_xlsx['artifact_path']} (SHA256: {exp_xlsx['sha256'][:16]}...)")
        assert os.path.exists(exp_xlsx["artifact_path"]), "Archivo XLSX no existe en disco"
        assert os.path.getsize(exp_xlsx["artifact_path"]) > 1000, "XLSX sospechosamente pequeño"

        # Export PDF
        res_exp_pdf = requests.post(f"{BASE_URL}/review/runs/{run_id}/exports", json={"format": "pdf"}, headers=headers)
        assert res_exp_pdf.status_code == 201, f"Error exportando PDF: {res_exp_pdf.text}"
        exp_pdf = res_exp_pdf.json()
        print(f"✓ [EXPORT PDF] Creado: {exp_pdf['artifact_path']} (SHA256: {exp_pdf['sha256'][:16]}...)")
        assert os.path.exists(exp_pdf["artifact_path"]), "Archivo PDF no existe en disco"
        with open(exp_pdf["artifact_path"], "rb") as pf:
            pdf_bytes = pf.read().decode("latin-1", errors="ignore")
            assert "SANDBOX" in pdf_bytes, "PDF debe contener marca SANDBOX"
            assert "Resultado exploratorio" in pdf_bytes, "PDF debe contener advertencia exploratoria"

        # 12. Descarga HTTP de cada reporte
        for fmt, report_meta in [("JSON", exp_json), ("XLSX", exp_xlsx), ("PDF", exp_pdf)]:
            res_dl = requests.get(f"{BASE_URL}/review/reports/{report_meta['id']}/download", headers=headers)
            assert res_dl.status_code == 200, f"Error descargando {fmt}: {res_dl.status_code}"
            assert len(res_dl.content) > 0, f"Contenido vacío en descarga {fmt}"
            print(f"✓ [DOWNLOAD {fmt}] Descargado exitosamente vía endpoint HTTP ({len(res_dl.content)} bytes)")

        print("\n" + "=" * 70)
        print("🎉 ACEPTACIÓN FUNCIONAL COMPLETADA EXITOSAMENTE AL 100%")
        print("=" * 70)

        return {
            "project": project,
            "documents": [doc1, doc2],
            "symbols": [sym1, sym2],
            "plan_sandbox": plan_sbx,
            "plan_production": plan_prod,
            "run_details": run_details,
            "exports": {
                "json": exp_json,
                "xlsx": exp_xlsx,
                "pdf": exp_pdf
            }
        }
    finally:
        db.close()

if __name__ == "__main__":
    run_acceptance()
