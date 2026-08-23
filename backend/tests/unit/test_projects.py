def test_create_and_list_projects(client):
    """Verifica el ciclo básico CRUD de creación y listado de proyectos."""
    payload = {
        "code": "PRJ-TEST-001",
        "name": "Proyecto de Prueba Unitario",
        "description": "Descripción de prueba",
        "client_name": "Cliente Test",
        "discipline": "architecture",
        "settings": {"test_key": "test_val"}
    }
    # 1. Crear proyecto
    create_res = client.post("/api/v1/projects/", json=payload)
    assert create_res.status_code == 201
    created_data = create_res.json()
    assert created_data["code"] == "PRJ-TEST-001"
    assert "id" in created_data

    # 2. Listar proyectos
    list_res = client.get("/api/v1/projects/")
    assert list_res.status_code == 200
    projects = list_res.json()
    assert len(projects) >= 1
    assert any(p["code"] == "PRJ-TEST-001" for p in projects)

    # 3. Intentar crear proyecto con código duplicado (debe fallar con 400)
    dup_res = client.post("/api/v1/projects/", json=payload)
    assert dup_res.status_code == 400
