from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

_BACKEND_MODULES = {
    "config",
    "database",
    "decision",
    "detector",
    "main",
    "models",
    "prometheus_client",
    "recovery",
    "service_catalog",
    "verifier",
    "zscore_detector",
}


def _clear_backend_modules() -> None:
    for name in list(sys.modules):
        if name in _BACKEND_MODULES or name.startswith("chaos"):
            sys.modules.pop(name, None)


@pytest.fixture()
def app_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    incidents_db = tmp_path / "incidents.sqlite3"
    decision_db = tmp_path / "decision.sqlite3"

    monkeypatch.setenv("KUBERESILIENCE_DEMO_MODE", "1")
    monkeypatch.delenv("PROMETHEUS_URL", raising=False)
    monkeypatch.setenv("PROMETHEUS_TIMEOUT_SECONDS", "0.1")
    monkeypatch.setenv("KUBE_NAMESPACE", "boutique")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{incidents_db.as_posix()}")
    monkeypatch.setenv("KUBERESILIENCE_STATE_DB_PATH", str(decision_db))

    _clear_backend_modules()
    import main

    client = TestClient(main.app, raise_server_exceptions=False)
    return client, main
