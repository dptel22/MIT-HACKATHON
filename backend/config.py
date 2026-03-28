from __future__ import annotations

import os


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", "").strip()
KUBE_NAMESPACE = os.environ.get("KUBE_NAMESPACE", "boutique").strip() or "boutique"
PROMETHEUS_TIMEOUT_SECONDS = float(
    os.environ.get("PROMETHEUS_TIMEOUT_SECONDS", "0.75")
)
DEMO_MODE = _env_bool(
    "KUBERESILIENCE_DEMO_MODE",
    default=not bool(PROMETHEUS_URL),
)
