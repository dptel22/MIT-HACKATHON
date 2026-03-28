from __future__ import annotations


def test_demo_chaos_injection_and_cleanup_drive_detection_state(app_client):
    client, main = app_client

    inject_response = client.post("/api/chaos/inject?service=cartservice&scenario=cpu_stress")
    assert inject_response.status_code == 200
    assert inject_response.json()["success"] is True

    detect_response = client.post("/api/detect/run")
    assert detect_response.status_code == 200
    cartservice = detect_response.json()["cartservice"]
    assert cartservice["is_anomaly"] is True
    assert cartservice["confidence"] >= 80
    assert cartservice["features"]["p95_latency_ms"] > 10

    cleanup_response = client.post("/api/chaos/cleanup")
    assert cleanup_response.status_code == 200
    assert cleanup_response.json()["message"] == "All chaos experiments cleaned up"

    follow_up_detect = client.post("/api/detect/run")
    assert follow_up_detect.status_code == 200
    cleaned = follow_up_detect.json()["cartservice"]
    assert cleaned["is_anomaly"] is False
    assert cleaned["votes"] == [0]
    assert main.state["services"]["cartservice"]["is_anomaly"] is False


def test_failed_chaos_result_returns_400_instead_of_500(app_client, monkeypatch):
    client, main = app_client

    monkeypatch.setattr(
        main,
        "inject_chaos_safe",
        lambda service, scenario: {
            "success": False,
            "message": "No running pod found for cartservice",
        },
    )

    response = client.post("/api/chaos/inject?service=cartservice&scenario=pod_kill")

    assert response.status_code == 400
    assert response.json()["detail"] == "No running pod found for cartservice"


def test_successful_recovery_resets_live_service_state(app_client, monkeypatch):
    client, main = app_client

    client.post("/api/chaos/inject?service=cartservice&scenario=cpu_stress")
    detect_response = client.post("/api/detect/run")
    assert detect_response.status_code == 200

    monkeypatch.setattr(
        main.recovery,
        "restart_pod",
        lambda service_name: (f"{service_name}-demo-pod", 1234567890.0),
    )
    monkeypatch.setattr(main.verifier, "verify_recovery", lambda *_args, **_kwargs: "HEALED")

    response = client.post("/api/recover?service_name=cartservice")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "HEALED"
    assert payload["pod_name"] == "cartservice-demo-pod"
    assert main.state["services"]["cartservice"]["is_anomaly"] is False
    assert main.state["services"]["cartservice"]["votes"] == []
