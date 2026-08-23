import os
import io
import json
import requests
from sqlalchemy import text
from app.db.session import engine

BASE_URL = 'http://localhost:8000/api/v1'

def run_verification():
    print("========================================================")
    print("1. DOCUMENTO LOCAL EN DISCO")
    print("========================================================")
    pdf_bytes = (
        b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
        b"xref\n0 4\n0000000000 65535 f\n0000000010 00000 n\n0000000060 00000 n\n0000000117 00000 n\n"
        b"trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n180\n%%EOF"
    )
    
    files = {
        'file': ('NCh2026_Aislacion_Termica_v2.pdf', io.BytesIO(pdf_bytes), 'application/pdf')
    }
    form_data = {
        'title': 'NCh 2026 - Aislación Térmica y Eficiencia Energética',
        'source_type': 'normative_document',
        'discipline': 'Arquitectura',
        'document_type': 'norma',
        'authority': 'INN / MINVU',
        'description': 'Norma oficial chilena de transmitancia térmica y exigencias de envolvente.',
        'version': '2.1'
    }
    
    resp_upload = requests.post(f"{BASE_URL}/intake/sources/upload", data=form_data, files=files)
    assert resp_upload.status_code == 201, f"Upload error: {resp_upload.text}"
    source = resp_upload.json()
    source_id = source['id']
    file_path = source['file_path']
    org_id = source['organization_id']
    
    print(f"- Source ID: {source_id}")
    print(f"- Nombre original: {source.get('original_filename')}")
    print(f"- Nombre físico guardado: {os.path.basename(file_path)}")
    print(f"- Ruta final: {file_path}")
    print(f"- Tamaño: {source.get('file_size_bytes')} bytes")
    print(f"- Organization ID: {org_id}")
    print(f"- Existe físicamente en disco?: {os.path.exists(file_path)}")
    print(f"- Tamaño verificado en disco: {os.path.getsize(file_path)} bytes")

    print("\n========================================================")
    print("2. REUTILIZACION DE DOCUMENTO LOCAL (PROCESAR CON IA)")
    print("========================================================")
    # Procesar con IA referenciando únicamente el source_asset_id
    payload_ai = {
        'title': 'Extracción IA NCh 2026',
        'document_type': 'norma',
        'discipline': 'Arquitectura',
        'authority': 'INN / MINVU',
        'source_asset_id': source_id
    }
    resp_ai = requests.post(f"{BASE_URL}/intake/extractions/process-with-ai", json=payload_ai)
    assert resp_ai.status_code in [200, 201], f"AI extraction error: {resp_ai.text}"
    ai_data = resp_ai.json()
    extraction_id = ai_data['id']
    print(f"- Extracción ID: {extraction_id}")
    print(f"- Source Origin: {ai_data['source_origin']}")
    print(f"- Source File Path leído de disco: {ai_data['source_file_path']}")
    print(f"- Total ítems extraídos desde archivo: {len(ai_data['items'])}")
    for it in ai_data['items'][:3]:
        print(f"   * [{it['item_type']}] {it['code_or_number']}: {it['title']}")

    print("\n========================================================")
    print("3. INTEGRIDAD DEL FLUJO Y COMMIT HACIA MOTOR DE REGLAS QA/QC")
    print("========================================================")
    payload_commit = {
        'target_rule_document_title': 'NCh 2026 - Aislación Térmica (Incorporada al Motor)',
        'target_rule_document_description': 'Documento normativo incorporado desde extracción documental con IA.',
        'approved_item_ids': [it['id'] for it in ai_data['items']]
    }
    resp_commit = requests.post(f"{BASE_URL}/intake/extractions/{extraction_id}/commit", json=payload_commit)
    assert resp_commit.status_code == 200, f"Commit error: {resp_commit.text}"
    commit_data = resp_commit.json()
    rule_doc_id = commit_data['rule_document_id']
    print(f"- RuleDocument ID creado: {rule_doc_id}")
    print(f"- Reglas oficiales incorporadas: {commit_data['rules_incorporated_count']}")
    print(f"- Entradas en base de conocimiento: {commit_data['knowledge_entries_created_count']}")
    print(f"- Mensaje de confirmación: {commit_data['message']}")

    # Consulta directa al endpoint de reglas
    resp_rules = requests.get(f"{BASE_URL}/rules/documents/{rule_doc_id}")
    assert resp_rules.status_code == 200
    rule_doc_data = resp_rules.json()
    print(f"- Verificación endpoint GET /rules/documents/{rule_doc_id}: 200 OK")
    print(f"- Título en Motor de Reglas: {rule_doc_data['title']}")
    print(f"- Origen en Motor de Reglas: {rule_doc_data['source_origin']}")
    print(f"- Estado en Motor de Reglas: {rule_doc_data['status']}")
    print(f"- Total ítems/reglas activas en el documento: {len(rule_doc_data.get('items', []))}")

    print("\n========================================================")
    print("4. INVESTIGACION WEB PERSISTIDA")
    print("========================================================")
    web_payload = {
        'search_prompt': 'Parámetros de resistencia al fuego F-120 para muros cortafuego OGUC',
        'discipline': 'Estructuras',
        'document_type': 'norma',
        'authority': 'MINVU / INN',
        'focus_areas': ['resistencia al fuego', 'muros divisorios', 'F-120', 'sellos de pasada']
    }
    resp_web = requests.post(f"{BASE_URL}/intake/extractions/process-web-research", json=web_payload)
    assert resp_web.status_code in [200, 201], f"Web research error: {resp_web.text}"
    web_data = resp_web.json()
    web_ext_id = web_data['id']
    print(f"- Web Extraction ID: {web_ext_id}")
    print(f"- Citas y fuentes web encontradas: {len(web_data['search_citations'])}")
    for c in web_data['search_citations']:
        print(f"   * {c['title']} ({c.get('domain', 'web')})")

    # Verificación en Base de Datos de las 4 tablas estructuradas
    with engine.connect() as conn:
        q_row = conn.execute(text(
            "SELECT id, search_prompt, discipline, authority, status, created_at FROM research_queries WHERE search_prompt LIKE '%F-120%' ORDER BY created_at DESC LIMIT 1"
        )).mappings().first()
        
        print("\n--- REGISTROS EN BASE DE DATOS (TABLAS RESEARCH_*) ---")
        print(f"- research_queries:")
        print(f"   ID: {q_row['id']}")
        print(f"   Prompt: {q_row['search_prompt']}")
        print(f"   Disciplina: {q_row['discipline']}")
        print(f"   Status: {q_row['status']}")
        
        r_rows = conn.execute(text(
            f"SELECT id, title, total_items_found, executive_summary FROM research_results WHERE query_id = '{q_row['id']}'"
        )).mappings().all()
        print(f"- research_results: {len(r_rows)} registro(s)")
        for r in r_rows:
            print(f"   ID: {r['id']} | Título: {r['title']} | Items: {r['total_items_found']}")
            
            s_rows = conn.execute(text(f"SELECT id, title, url, domain FROM research_sources WHERE result_id = '{r['id']}'")).mappings().all()
            print(f"- research_sources: {len(s_rows)} fuente(s)")
            for s in s_rows:
                print(f"   * {s['title']} -> {s['url']}")
                
            i_rows = conn.execute(text(f"SELECT id, item_type, item_nature, title, code_or_number FROM research_items WHERE result_id = '{r['id']}'")).mappings().all()
            print(f"- research_items: {len(i_rows)} elemento(s) estructurado(s)")
            for it in i_rows[:3]:
                print(f"   * [{it['item_type']} | {it['item_nature']}] {it['code_or_number']}: {it['title']}")

    # Consulta al endpoint de histórico
    resp_q_list = requests.get(f"{BASE_URL}/intake/research/queries")
    assert resp_q_list.status_code == 200
    print(f"- Endpoint GET /intake/research/queries: {len(resp_q_list.json())} consultas en histórico disponibles para la UI")

    print("\n========================================================")
    print("5. ELIMINACION REAL (HARD-DELETE Y SOFT-DELETE)")
    print("========================================================")
    # A) Hard-Delete de documento sin dependencias
    temp_file = {
        'file': ('temp_unprocessed.pdf', io.BytesIO(b"%PDF-1.4 sample temp %EOF"), 'application/pdf')
    }
    temp_data = {
        'title': 'Documento Temporal Sin Procesar',
        'source_type': 'normative_document',
        'discipline': 'Arquitectura'
    }
    res_temp = requests.post(f"{BASE_URL}/intake/sources/upload", data=temp_data, files=temp_file).json()
    temp_id = res_temp['id']
    temp_path = res_temp['file_path']
    print(f"A) Creando fuente temporal sin procesar: ID {temp_id}")
    print(f"   Existe en disco antes de borrar?: {os.path.exists(temp_path)}")

    # Ejecutar Hard-Delete
    del_hard = requests.delete(f"{BASE_URL}/intake/sources/{temp_id}?hard_delete=true").json()
    print(f"   Resultado Delete: {del_hard['mode']} (deleted={del_hard['deleted']})")
    print(f"   Archivo borrado físicamente de disco?: {not os.path.exists(temp_path)}")
    with engine.connect() as conn:
        db_exists = conn.execute(text(f"SELECT COUNT(*) FROM source_assets WHERE id = '{temp_id}'")).scalar()
        print(f"   Registro en PostgreSQL source_assets: {db_exists} (0 = completamente eliminado)")

    # B) Soft-Delete / Archivo de documento con dependencias
    print(f"\nB) Eliminando fuente procesada (con dependencias): ID {source_id}")
    del_soft = requests.delete(f"{BASE_URL}/intake/sources/{source_id}?hard_delete=false").json()
    print(f"   Resultado Delete: {del_soft['mode']} (deleted={del_soft['deleted']})")
    print(f"   Mensaje: {del_soft['message']}")
    with engine.connect() as conn:
        sa_status = conn.execute(text(f"SELECT status, approval_status FROM source_assets WHERE id = '{source_id}'")).mappings().first()
        print(f"   Estado en BD: status='{sa_status['status']}', approval_status='{sa_status['approval_status']}'")
        
    # Verificar que las reglas vinculadas siguen existiendo e intactas en el Motor de Reglas
    with engine.connect() as conn:
        rules_left = conn.execute(text(f"SELECT COUNT(*) FROM rule_documents WHERE id = '{rule_doc_id}'")).scalar()
        items_left = conn.execute(text(f"SELECT COUNT(*) FROM rule_document_items WHERE rule_document_id = '{rule_doc_id}'")).scalar()
        print(f"   Integridad de dependencias: {rules_left} documento normativo y {items_left} reglas preservadas en el motor.")

if __name__ == '__main__':
    run_verification()
