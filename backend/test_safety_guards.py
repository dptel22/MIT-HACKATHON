from __future__ import annotations

from types import SimpleNamespace

from chaos import chaos_engine


def test_fallback_pod_kill_scopes_commands_to_configured_namespace(monkeypatch):
    calls: list[list[str]] = []

    def fake_run(args, **_kwargs):
        calls.append(args)
        if args[:3] == ["kubectl", "get", "pod"]:
            return SimpleNamespace(stdout="cartservice-abc123", returncode=0, stderr="")
        return SimpleNamespace(stdout="", returncode=0, stderr="")

    monkeypatch.setattr(chaos_engine.subprocess, "run", fake_run)

    success, _message = chaos_engine.fallback_pod_kill("cartservice")

    assert success is True
    assert calls == [
        [
            "kubectl",
            "get",
            "pod",
            "-n",
            chaos_engine.KUBE_NAMESPACE,
            "-l",
            "app=cartservice",
            "-o",
            "jsonpath={.items[0].metadata.name}",
        ],
        [
            "kubectl",
            "delete",
            "pod",
            "cartservice-abc123",
            "-n",
            chaos_engine.KUBE_NAMESPACE,
        ],
    ]


def test_cleanup_all_only_targets_configured_namespace(monkeypatch):
    calls: list[list[str]] = []

    def fake_run(args, **_kwargs):
        calls.append(args)
        return SimpleNamespace(stdout="", returncode=0, stderr="")

    monkeypatch.setattr(chaos_engine.subprocess, "run", fake_run)

    chaos_engine.cleanup_all()

    assert calls == [
        [
            "kubectl",
            "delete",
            "podchaos",
            "--all",
            "-n",
            chaos_engine.KUBE_NAMESPACE,
            "--ignore-not-found=true",
        ],
        [
            "kubectl",
            "delete",
            "stresschaos",
            "--all",
            "-n",
            chaos_engine.KUBE_NAMESPACE,
            "--ignore-not-found=true",
        ],
        [
            "kubectl",
            "delete",
            "networkchaos",
            "--all",
            "-n",
            chaos_engine.KUBE_NAMESPACE,
            "--ignore-not-found=true",
        ],
    ]


def test_demo_blast_radius_guard_trips_after_four_services(app_client):
    _client, main = app_client

    main.decision.update_blast_radius("cartservice", True)
    main.decision.update_blast_radius("adservice", True)
    main.decision.update_blast_radius("recommendationservice", True)

    exceeded, reason = main.decision.is_blast_radius_exceeded()

    assert exceeded is False
    assert reason == "ok"

    main.decision.update_blast_radius("productcatalogservice", True)

    exceeded, reason = main.decision.is_blast_radius_exceeded()

    assert exceeded is True
    assert reason == "cluster_wide_event_suspected"


def test_cleanup_resets_auto_chaos_and_manual_mode(app_client):
    client, main = app_client

    start_response = client.post("/api/chaos/auto/start")
    assert start_response.status_code == 200

    main.state["manual_mode"] = True

    cleanup_response = client.post("/api/chaos/cleanup")

    assert cleanup_response.status_code == 200
    assert main.state["auto_chaos"] is False
    assert main.state["manual_mode"] is False
