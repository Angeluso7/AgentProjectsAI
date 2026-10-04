import requests
import json
import uuid

BASE_URL = "http://localhost:8000/api/v1"

def run_evidence():
    print("================================================================================")
    print("EVIDENCIA EN VIVO: DEDUPLICACIÓN ESTRICTA Y BLOQUEO HTTP 409 EN EL MOTOR QA/QC")
    print("================================================================================")

    # 1. Obtener o crear proyecto
    r_prj = requests.get(f"{BASE_URL}/projects/")
    projects = r_prj.json() if r_prj.status_code == 200 else []
    if projects:
        project_id = projects[0]["id"]
    else:
        print("Creando proyecto para test...")
        r_new_prj = requests.post(f"{BASE_URL}/projects/", json={
            "name": "Proyecto Demostración Evidencia",
            "code": f"PRJ-EVID-{uuid.uuid4().hex[:6]}",
            "discipline": "electrical"
        })
        project_id = r_new_prj.json()["id"]

    print(f"Proyecto activo: {project_id}")

    # 2. Crear sesión de extracción
    print("\n--- PASO 1: Creando sesión de extracción ---")
    r_session = requests.post(f"{BASE_URL}/intake/extractions", json={
        "title": "Documento NSEG-05 2026 - Extracción IA",
        "document_type": "norma",
        "authority": "SEC",
        "discipline": "electrical",
        "extraction_mode": "ai_document",
        "source_origin": "document",
        "project_id": project_id
    })
    session_data = r_session.json()
    session_id = session_data["id"]
    print(f"Sesión creada ID: {session_id}")

    # 3. Crear documento activo previo en el motor para la prueba de exact match
    print("\n--- PASO 2: Creando Regla Activa previa en el Motor QA/QC ---")
    r_doc = requests.post(f"{BASE_URL}/rules/documents/", json={
        "title": "Norma Técnica de Seguridad Eléctrica y Combustibles SEC",
        "document_type": "norma",
        "authority": "SEC",
        "discipline": "electrical",
        "version": "2026.1"
    })
    doc_data = r_doc.json()
    rule_doc_id = doc_data["id"]

    # Agregar ítem activo al documento del motor
    r_motor_rule = requests.post(f"{BASE_URL}/rules/documents/{rule_doc_id}/items", json={
        "title": "Distancia libre de cables MT respecto a ductos de combustible",
        "code_or_number": "SEC-ELEC-500",
        "description": "Los cables de media tensión deben instalarse a una distancia radial no inferior a 0.50 m de tuberías de gas.",
        "content_text": "Los cables de media tensión deben instalarse a una distancia radial no inferior a 0.50 m de tuberías de gas.",
        "item_type": "rule"
    })
    motor_rule = r_motor_rule.json()
    print(f"Regla existente en Motor QA/QC creada: ID={motor_rule['id']}, Código={motor_rule['code_or_number']}, Título='{motor_rule['title']}'")

    # 4. Agregar Ítem 1: EXACT MATCH
    print("\n--- PASO 3: Extrayendo Regla Candidata que es DUPLICADO EXACTO ---")
    r_item_exact = requests.post(f"{BASE_URL}/intake/extractions/{session_id}/items", json={
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
    print(f"Candidato 1 (Exact Match) Registrado:")
    print(f"  - ID: {exact_item['id']}")
    print(f"  - duplicate_status: {exact_item['duplicate_status']}")
    print(f"  - blocked_from_acceptance: {exact_item['blocked_from_acceptance']}")
    print(f"  - best_match_rule_code: {exact_item['best_match_rule_code']}")
    print(f"  - best_match_title: {exact_item['best_match_title']}")
    print(f"  - duplicate_reason: {exact_item['duplicate_reason']}")
    print(f"  - duplicate_confidence: {exact_item['duplicate_confidence']}")

    # 5. Intentar Aceptar Ítem 1 (Debe responder HTTP 409 Conflict)
    print("\n--- PASO 4: Intentando ACEPTAR el duplicado exacto vía PUT (Debe fallar con HTTP 409) ---")
    r_put_blocked = requests.put(
        f"{BASE_URL}/intake/extractions/{session_id}/items/{exact_item['id']}",
        json={"review_status": "accepted"}
    )
    print(f"Código HTTP de Respuesta: {r_put_blocked.status_code} ({r_put_blocked.reason})")
    print(f"Cuerpo de Respuesta JSON:\n{json.dumps(r_put_blocked.json(), indent=2, ensure_ascii=False)}")

    # 6. Agregar Ítem 2: LIKELY DUPLICATE (Similitud parcial, no idéntico)
    print("\n--- PASO 5: Extrayendo Regla Candidata con SIMILITUD PARCIAL (Likely Duplicate) ---")
    r_item_likely = requests.post(f"{BASE_URL}/intake/extractions/{session_id}/items", json={
        "item_type": "rule",
        "candidate_type": "rule_candidate",
        "title": "Separación recomendada entre bandejas de cables y cañerías de gas natural",
        "code_or_number": "SEC-ELEC-500-VAR",
        "description": "Se sugiere una distancia mínima operativa entre escalerillas y ductos para facilitar mantenimiento.",
        "content_text": "Se sugiere una distancia mínima operativa entre escalerillas y ductos para facilitar mantenimiento.",
        "target_destination": "rules_engine",
        "review_status": "to_confirm"
    })
    likely_item = r_item_likely.json()
    print(f"Candidato 2 (Likely Duplicate) Registrado:")
    print(f"  - ID: {likely_item['id']}")
    print(f"  - duplicate_status: {likely_item['duplicate_status']}")
    print(f"  - blocked_from_acceptance: {likely_item['blocked_from_acceptance']}")
    print(f"  - best_match_rule_code: {likely_item.get('best_match_rule_code')}")
    print(f"  - duplicate_reason: {likely_item.get('duplicate_reason')}")

    # 7. Aceptar Ítem 2 (Debe responder HTTP 200 OK)
    print("\n--- PASO 6: Aceptando la regla de similitud parcial (Debe responder HTTP 200 OK) ---")
    r_put_likely = requests.put(
        f"{BASE_URL}/intake/extractions/{session_id}/items/{likely_item['id']}",
        json={"review_status": "accepted"}
    )
    print(f"Código HTTP de Respuesta: {r_put_likely.status_code} ({r_put_likely.reason})")
    print(f"Estado del Ítem tras Aceptación: {r_put_likely.json().get('review_status')}")

    # 8. Listar candidatos para verificar que TODOS siguen visibles
    print("\n--- PASO 7: Verificando que TODAS las reglas siguen visibles en el listado ---")
    r_list = requests.get(f"{BASE_URL}/intake/extractions/{session_id}/candidates")
    all_candidates = r_list.json()
    print(f"Total candidatos listados: {len(all_candidates)}")
    for i, c in enumerate(all_candidates, 1):
        print(f"  {i}. [{c['duplicate_status']}] {c['code_or_number']}: {c['title']} | blocked={c['blocked_from_acceptance']} | status={c['review_status']}")

    print("\n================================================================================")
    print("DEMOSTRACIÓN DE EVIDENCIA FINALIZADA CON ÉXITO")
    print("================================================================================")

if __name__ == "__main__":
    run_evidence()
