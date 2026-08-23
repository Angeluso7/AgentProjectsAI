def test_root_health_endpoint(client):
    """Verifica que GET /health retorne 200 y el estado esperado."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "app_name" in data
    assert "version" in data

def test_api_v1_health_endpoint(client):
    """Verifica que GET /api/v1/health retorne 200."""
    response = client.get("/api/v1/health/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"

def test_root_index_endpoint(client):
    """Verifica que GET / retorne metadatos y estado ready."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["docs_url"] == "/docs"
