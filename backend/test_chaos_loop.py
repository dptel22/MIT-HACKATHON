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


def test_recent_chaos_injection_keeps_forced_anomaly_until_grace_window_expires(app_client, monkeypatch):
    client, main = app_client

    inject_response = client.post("/api/chaos/inject?service=cartservice&scenario=cpu_stress")
    assert inject_response.status_code == 200

    monkeypatch.setattr(main.time, "time", lambda: 1_000.0)
    main.state["services"]["cartservice"]["forced_anomaly_until"] = 1_030.0
    monkeypatch.setattr(
        main.detector,
        "run_detection",
        lambda *_args, **_kwargs: {
            "confidence": 0.0,
            "triggered": False,
        },
    )

    detect_response = client.post("/api/detect/run")

    assert detect_response.status_code == 200
    cartservice = detect_response.json()["cartservice"]
    assert cartservice["is_anomaly"] is True
    assert cartservice["confidence"] == 99.0
    assert cartservice["votes"] == [1, 1, 1, 1, 1]


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


def test_failed_recovery_uses_service_cooldown_without_global_freeze(app_client, monkeypatch):
    client, main = app_client

    client.post("/api/chaos/inject?service=cartservice&scenario=cpu_stress")
    detect_response = client.post("/api/detect/run")
    assert detect_response.status_code == 200

    monkeypatch.setattr(
        main.recovery,
        "restart_pod",
        lambda service_name: (f"{service_name}-demo-pod", 1234567890.0),
    )
    monkeypatch.setattr(main.verifier, "verify_recovery", lambda *_args, **_kwargs: "FAILED")

    response = client.post("/api/recover?service_name=cartservice")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "FAILED"
    assert main.state["manual_mode"] is False

    cooldown_active, cooldown_remaining = main.decision.is_cooldown_active("cartservice")
    assert cooldown_active is True
    assert cooldown_remaining > 0

    follow_up_detect = client.post("/api/detect/run")
    assert follow_up_detect.status_code == 200
    assert "error" not in follow_up_detect.json()


def test_recovery_marks_service_as_recovering_and_circuit_broken(app_client, monkeypatch):
    client, main = app_client

    client.post("/api/chaos/inject?service=cartservice&scenario=cpu_stress")
    detect_response = client.post("/api/detect/run")
    assert detect_response.status_code == 200

    monkeypatch.setattr(
        main.recovery,
        "restart_pod",
        lambda service_name: (f"{service_name}-demo-pod", 1234567890.0),
    )

    def fake_verify(*_args, **_kwargs):
        svc_state = main.state["services"]["cartservice"]
        assert svc_state["recovery_in_progress"] is True
        assert svc_state["circuit_broken"] is True
        return "HEALED"

    monkeypatch.setattr(main.verifier, "verify_recovery", fake_verify)

    response = client.post("/api/recover?service_name=cartservice")

    assert response.status_code == 200
    svc_state = main.state["services"]["cartservice"]
    assert svc_state["recovery_in_progress"] is False
    assert svc_state["circuit_broken"] is True


def test_demo_auto_chaos_only_blocks_active_incidents_not_other_service_cooldowns(app_client):
    _client, main = app_client

    main.decision.record_action("cartservice", "high", "HEALED")

    assert main._service_has_active_incident("cartservice") is False
    assert main._service_ready_for_auto_chaos("cartservice") is False
    assert any(
        main._service_has_active_incident(service_name)
        for service_name in main.CHAOS_SERVICES
    ) is False

    available_targets = [
        service_name
        for service_name in main.CHAOS_SERVICES
        if main._service_ready_for_auto_chaos(service_name)
    ]

    assert "cartservice" not in available_targets
    assert available_targets
