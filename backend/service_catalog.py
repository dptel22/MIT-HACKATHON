from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).resolve().parent / "models"
MODEL_CONFIG_PATH = MODELS_DIR / "model_config.json"
BASELINE_STATS_PATH = MODELS_DIR / "baseline_stats.json"

_DEFAULT_NON_CRITICAL_SERVICES = (
    "cartservice",
    "recommendationservice",
    "adservice",
    "productcatalogservice",
)
_DEFAULT_CRITICAL_SERVICES = ("checkoutservice",)
_DEFAULT_AUTO_REMEDIABLE_SCENARIOS = (
    "pod_kill",
    "cpu_stress",
    "network_latency",
    "memory_leak",
    "packet_loss",
)


def _dedupe_services(items: list[Any]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        service = str(item).strip()
        if not service or service in seen:
            continue
        seen.add(service)
        ordered.append(service)
    return tuple(ordered)


def _default_model_config() -> dict[str, Any]:
    return {
        "non_critical_services": list(_DEFAULT_NON_CRITICAL_SERVICES),
        "critical_services": list(_DEFAULT_CRITICAL_SERVICES),
        "auto_remediable_chaos_scenarios": list(_DEFAULT_AUTO_REMEDIABLE_SCENARIOS),
    }


def _load_model_config() -> dict[str, Any]:
    if not MODEL_CONFIG_PATH.exists():
        logger.warning(
            "Model config not found at '%s'; using default service catalog.",
            MODEL_CONFIG_PATH,
        )
        return _default_model_config()

    try:
        with MODEL_CONFIG_PATH.open("r", encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, ValueError, TypeError) as exc:
        logger.warning(
            "Failed to read model config from '%s'; using defaults. Error: %s",
            MODEL_CONFIG_PATH,
            exc,
        )
        return _default_model_config()

    if not isinstance(raw, dict):
        logger.warning(
            "Model config at '%s' is not a JSON object; using defaults.",
            MODEL_CONFIG_PATH,
        )
        return _default_model_config()

    return raw


MODEL_CONFIG: dict[str, Any] = _load_model_config()

NON_CRITICAL_SERVICES: tuple[str, ...] = _dedupe_services(
    list(MODEL_CONFIG.get("non_critical_services", _DEFAULT_NON_CRITICAL_SERVICES))
)
CRITICAL_SERVICES: frozenset[str] = frozenset(
    _dedupe_services(
        list(MODEL_CONFIG.get("critical_services", _DEFAULT_CRITICAL_SERVICES))
    )
)
SUPPORTED_SERVICES: tuple[str, ...] = _dedupe_services(
    [*NON_CRITICAL_SERVICES, *CRITICAL_SERVICES]
)
AUTO_REMEDIABLE_SCENARIOS: frozenset[str] = frozenset(
    str(item).strip()
    for item in MODEL_CONFIG.get(
        "auto_remediable_chaos_scenarios",
        _DEFAULT_AUTO_REMEDIABLE_SCENARIOS,
    )
    if str(item).strip()
)


def get_supported_services() -> list[str]:
    return list(SUPPORTED_SERVICES)


def get_non_critical_services() -> list[str]:
    return list(NON_CRITICAL_SERVICES)


def get_supported_chaos_scenarios() -> list[str]:
    return list(AUTO_REMEDIABLE_SCENARIOS)


def is_supported_service(service: str) -> bool:
    return service in SUPPORTED_SERVICES


def is_critical_service(service: str) -> bool:
    return service in CRITICAL_SERVICES
