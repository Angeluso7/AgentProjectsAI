def test_create_and_list_knowledge_assets(client):
    """Verifica creación y consulta de KnowledgeAssets."""
    asset_payload = {
        "code": "ASSET-TEST-001",
        "title": "Manual de Criterios Estructurales",
        "asset_type": "guide_manual",
        "discipline": "structural",
        "version": "1.0",
        "description": "Manual de diseño sismorresistente",
        "content_payload": {"min_thickness_cm": 20}
    }
    create_res = client.post("/api/v1/knowledge/assets", json=asset_payload)
    assert create_res.status_code == 201
    asset_data = create_res.json()
    assert asset_data["code"] == "ASSET-TEST-001"

    # Listar
    list_res = client.get("/api/v1/knowledge/assets")
    assert list_res.status_code == 200
    assets = list_res.json()
    assert any(a["code"] == "ASSET-TEST-001" for a in assets)

def test_sync_seed_knowledge(client):
    """Verifica que el endpoint de sincronización de seed lea los archivos YAML/JSON."""
    sync_res = client.post("/api/v1/knowledge/sync-seed")
    assert sync_res.status_code == 200
    data = sync_res.json()
    assert "counts" in data
