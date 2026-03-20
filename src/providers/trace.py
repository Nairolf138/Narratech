"""Helpers pour normaliser le format `provider_trace`."""

from __future__ import annotations

from typing import Any


def build_provider_trace(
    *,
    provider: str,
    model: str,
    latency_ms: int,
    cost_estimate: float,
    retries: int = 0,
    status: str = "success",
    error: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Construit un `provider_trace` unifié avec les champs obligatoires."""
    trace: dict[str, Any] = {
        "provider": provider,
        "model": model,
        "modele": model,
        "latency_ms": int(latency_ms),
        "cost_estimate": float(cost_estimate),
        "retries": int(retries),
        "status": status,
        "error": error or "",
    }
    trace.update(extra)
    return trace
