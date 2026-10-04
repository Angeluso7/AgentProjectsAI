def test_review_runs_and_findings_flow(client):
    """Verifica el flujo de creación de review-run, consulta de hallazgos y feedback humano."""
    # 1. Crear proyecto previo
    proj_res = client.post("/api/v1/projects/", json={
        "code": "PRJ-REV-001",
        "name": "Proyecto Para Review",
        "discipline": "architecture"
    })
    assert proj_res.status_code == 201
    project_id = proj_res.json()["id"]

    # 2. Iniciar corrida de auditoría
    run_res = client.post("/api/v1/review-runs/", json={
        "project_id": project_id,
        "run_name": "Auditoría de Prueba"
    })
    assert run_res.status_code == 201
    run_data = run_res.json()
    assert run_data["run_name"] == "Auditoría de Prueba"
    assert "id" in run_data
    run_id = run_data["id"]

    # 3. Listar hallazgos de la corrida
    findings_res = client.get(f"/api/v1/review-runs/{run_id}/findings")
    assert findings_res.status_code == 200
    findings = findings_res.json()
    assert len(findings) >= 1
    finding_id = findings[0]["id"]

    # 4. Enviar feedback humano sobre el hallazgo
    feedback_res = client.post(f"/api/v1/findings/{finding_id}/feedback", json={
        "action": "accept_finding",
        "notes": "Validado en test unitario"
    })
    assert feedback_res.status_code == 200
    feedback_data = feedback_res.json()
    assert feedback_data["action"] == "accept_finding"
