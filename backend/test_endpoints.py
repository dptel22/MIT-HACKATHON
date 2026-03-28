from __future__ import annotations


def test_runtime_config_exposes_backend_catalog(app_client):
    client, main = app_client

    response = client.get("/api/config")

    assert response.status_code == 200
    payload = response.json()
    assert payload["services"] == main.SERVICES
    assert payload["chaos_services"] == main.CHAOS_SERVICES
    assert payload["chaos_scenarios"] == main.CHAOS_SCENARIOS
    assert payload["demo_mode"] is True
    assert payload["namespace"] == "boutique"


def test_detect_run_returns_demo_metrics_without_missing_fields(app_client):
    client, main = app_client

    response = client.post("/api/detect/run")

    assert response.status_code == 200
    payload = response.json()
    assert list(payload.keys()) == main.SERVICES

    for service_name in main.SERVICES:
        service_state = payload[service_name]
        assert service_state["features"]["all_available"] is True
        assert service_state["features"]["missing_fields"] == []
        assert service_state["is_anomaly"] is False
        assert service_state["votes"] == [0]


def test_recover_rejects_untracked_service(app_client):
    client, _ = app_client

    response = client.post("/api/recover?service_name=paymentservice")

    assert response.status_code == 404
    assert response.json()["detail"] == "Service not tracked"
