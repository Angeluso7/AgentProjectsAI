import requests
import json
import uuid
import sys
import os

sys.path.insert(0, "/app")
from app.db.session import SessionLocal
from app.db.models.core import Organization, Project
from app.db.models.intake_extractions import RuleDocument, RuleDocumentItem
from app.core.security import create_access_token

BASE_URL = "http://localhost:8000/api/v1"

def run_evidence():
    print("================================================================================")
    print("EVIDENCIA EN VIVO: DEDUPLICACIÓN ESTRICTA Y BLOQUEO HTTP 409 EN EL MOTOR QA/QC")
    print("================================================================================")

    db = SessionLocal()
    try:
        org = db.query(Organization).first()
        org_id = org.id
        proj = db.query(Project).filter(Project.organization_id == org_id).first()
        project_id = proj.id
        user_id = "10847273-134a-4f24-a100-6e6ea39f6a88"

        # 1. Crear documento previo y regla activa existente en el Motor de Reglas QA/QC
        print("\n--- PASO 1: Creando Regla Activa Existente en el Motor QA/QC ---")
        existing_doc_id = str(uuid.uuid4())
        existing_rule_id = str(uuid.uuid4())

        existing_doc = RuleDocument(
            id=existing_doc_id,
            organization_id=org_id,
            project_id=project_id,
            title="Norma Técnica de Seguridad Eléctrica y Combustibles SEC",
            document_type="norma",
            source_origin="con_ia_documento",
            authority="SEC",
            discipline="electrical",
            version="2026.1",
            status="active",
            items_count=1,
            rules_count=1
        )
        db.add(existing_doc)

        existing_rule = RuleDocumentItem(
            id=existing_rule_id,
            rule_document_id=existing_doc_id,
            item_type="rule",
            source_origin="document",
            title="Distancia libre de cables MT respecto a ductos de combustible",
            code_or_number="SEC-ELEC-500",
            description="Los cables de media tensión deben instalarse a una distancia radial no inferior a 0.50 m de tuberías de gas.",
            content_text="Los cables de media tensión deben instalarse a una distancia radial no inferior a 0.50 m de tuberías de gas.",
            status="active"
        )
        db.add(existing_rule)
        db.commit()

        print(f"✓ Regla existente en Motor QA/QC registrada:")
        print(f"  - ID: {existing_rule_id}")
        print(f"  - Código: SEC-ELEC-500")
        print(f"  - Título: 'Distancia libre de cables MT respecto a ductos de combustible'")
        print(f"  - Estado: active (Motor QA/QC)")

        token = create_access_token(subject=user_id, email="admin@planreview.ai", extra_claims={"org_id": org_id, "role": "admin"})
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Organization-Id": org_id,
            "Content-Type": "application/json"
        }

        # 2. Crear sesión de extracción
        print("\n--- PASO 2: Creando sesión de extracción de candidatos ---")
        r_session = requests.post(f"{BASE_URL}/intake/extractions/create-manual", headers=headers, json={
            "title": "Documento de Planos Eléctricos SEC 2026 - Extracción",
            "document_type": "norma",
            "authority": "SEC",
            "discipline": "electrical",
            "project_id": project_id
        })
        session_data = r_session.json()
        session_id = session_data["id"]
        print(f"✓ Sesión creada ID: {session_id}")

        # 3. Agregar Ítem 1: EXACT MATCH (Coincidencia exacta de código y contenido)
        print("\n--- PASO 3: Agregando Regla Candidata que es DUPLICADO EXACTO ---")
        r_item_exact = requests.post(f"{BASE_URL}/intake/extractions/{session_id}/items", headers=headers, json={
            "item_type": "rule",
            "candidate_type": "rule_candidate",
            "title": "Distancia libre de cables MT respecto a ductos de combustible",
            "code_or_number": "SEC-ELEC-500",
            "description": "Los cables de media tensión deben instalarse a una distancia radial no inferior a 0.50 m de tuberías de gas.",
            "content_text": "Los cables de media tensión deben instalarse a una distancia radial no inferior a 0.50 m de tuberías de gas.",
            "target_destination": "rules_engine",
            "review_status": "to_confirm"
        })
        exact_item = r_item_exact.json()
        print(f"✓ Candidato 1 (Exact Match) Registrado y Clasificado por el Backend:")
        print(f"  - ID: {exact_item['id']}")
        print(f"  - duplicate_status: {exact_item['duplicate_status']}")
        print(f"  - blocked_from_acceptance: {exact_item['blocked_from_acceptance']}")
        print(f"  - best_match_rule_code: {exact_item['best_match_rule_code']}")
        print(f"  - best_match_title: {exact_item['best_match_title']}")
        print(f"  - duplicate_reason: {exact_item['duplicate_reason']}")
        print(f"  - duplicate_confidence: {exact_item['duplicate_confidence']}")

        # 4. Intentar Aceptar Ítem 1 (Debe responder HTTP 409 Conflict)
        print("\n--- PASO 4: Intentando ACEPTAR el duplicado exacto vía PUT (Bloqueo Backend) ---")
        r_put_blocked = requests.put(
            f"{BASE_URL}/intake/extractions/{session_id}/items/{exact_item['id']}",
            headers=headers,
            json={"review_status": "accepted"}
        )
        print(f"✓ Código HTTP de Respuesta: {r_put_blocked.status_code} ({r_put_blocked.reason})")
        print(f"✓ Cuerpo de Respuesta JSON:")
        print(json.dumps(r_put_blocked.json(), indent=2, ensure_ascii=False))

        # 5. Agregar Ítem 2: LIKELY DUPLICATE (Similitud parcial alta pero no idéntico)
        print("\n--- PASO 5: Agregando Regla Candidata con SIMILITUD PARCIAL (Likely Duplicate) ---")
        r_item_likely = requests.post(f"{BASE_URL}/intake/extractions/{session_id}/items", headers=headers, json={
            "item_type": "rule",
            "candidate_type": "rule_candidate",
            "title": "Distancia de seguridad de cables de media tensión respecto a ductos de combustible y gas",
            "code_or_number": "SEC-ELEC-500-MOD",
            "description": "Los conductores de media tensión deben disponer de una distancia radial mínima de 0.50 m de tuberías y redes de gas.",
            "content_text": "Los conductores de media tensión deben disponer de una distancia radial mínima de 0.50 m de tuberías y redes de gas.",
            "target_destination": "rules_engine",
            "review_status": "to_confirm"
        })
        likely_item = r_item_likely.json()
        print(f"✓ Candidato 2 (Likely Duplicate) Registrado:")
        print(f"  - ID: {likely_item['id']}")
        print(f"  - duplicate_status: {likely_item['duplicate_status']}")
        print(f"  - blocked_from_acceptance: {likely_item['blocked_from_acceptance']}")
        print(f"  - best_match_rule_code: {likely_item.get('best_match_rule_code')}")
        print(f"  - duplicate_reason: {likely_item.get('duplicate_reason')}")

        # 6. Aceptar Ítem 2 (Debe responder HTTP 200 OK)
        print("\n--- PASO 6: Aceptando la regla de similitud parcial (Aceptación Permitida) ---")
        r_put_likely = requests.put(
            f"{BASE_URL}/intake/extractions/{session_id}/items/{likely_item['id']}",
            headers=headers,
            json={"review_status": "accepted"}
        )
        print(f"✓ Código HTTP de Respuesta: {r_put_likely.status_code} ({r_put_likely.reason})")
        print(f"✓ Estado del Ítem tras Aceptación: {r_put_likely.json().get('review_status')}")

        # 7. Listar candidatos para verificar que TODOS siguen visibles
        print("\n--- PASO 7: Verificando que TODAS las reglas siguen visibles en el listado ---")
        r_list = requests.get(f"{BASE_URL}/intake/extractions/{session_id}/candidates", headers=headers)
        all_candidates = r_list.json()
        print(f"✓ Total candidatos listados: {len(all_candidates)}")
        for i, c in enumerate(all_candidates, 1):
            print(f"  {i}. [{c['duplicate_status']}] {c['code_or_number']}: {c['title']} | blocked={c['blocked_from_acceptance']} | status={c['review_status']}")

        print("\n================================================================================")
        print("DEMOSTRACIÓN DE EVIDENCIA FINALIZADA CON ÉXITO")
        print("================================================================================")

    finally:
        db.close()

if __name__ == "__main__":
    run_evidence()
