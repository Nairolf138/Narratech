"""Calcul des métriques SLO provider (par provider + global)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

Trace = dict[str, Any]


DEFAULT_SLO_THRESHOLDS: dict[str, float] = {
    "max_p95_latency_ms": 1500.0,
    "min_success_rate": 0.95,
    "max_degraded_rate": 0.15,
    "max_retry_rate": 0.25,
    "max_error_rate": 0.05,
}


def _percentile(values: list[int], p: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    rank = (len(sorted_values) - 1) * p
    lower = int(rank)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = rank - lower
    return round(sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight, 2)


def _build_rates(*, calls: int, success: int, degraded: int, retries: int, errors: int) -> dict[str, float]:
    if calls <= 0:
        return {
            "success_rate": 0.0,
            "degraded_rate": 0.0,
            "retry_rate": 0.0,
            "error_rate": 0.0,
        }
    return {
        "success_rate": round(success / calls, 4),
        "degraded_rate": round(degraded / calls, 4),
        "retry_rate": round(retries / calls, 4),
        "error_rate": round(errors / calls, 4),
    }


def compute_slo_summary(*, traces: list[Trace]) -> dict[str, Any]:
    providers: dict[str, dict[str, Any]] = {}
    all_latencies: list[int] = []
    global_success = global_degraded = global_errors = global_retries = 0

    for trace in traces:
        if not isinstance(trace, dict):
            continue
        provider = str(trace.get("provider") or "unknown")
        status = str(trace.get("status") or "unknown")
        latency = int(trace.get("latency_ms") or 0)
        retries = int(trace.get("retries") or 0)
        is_error = status == "failed" or bool(trace.get("error"))

        entry = providers.setdefault(
            provider,
            {
                "provider": provider,
                "calls": 0,
                "success": 0,
                "degraded": 0,
                "errors": 0,
                "retries_total": 0,
                "latencies_ms": [],
            },
        )
        entry["calls"] += 1
        entry["retries_total"] += retries
        entry["latencies_ms"].append(latency)

        if status == "success":
            entry["success"] += 1
            global_success += 1
        if status == "degraded":
            entry["degraded"] += 1
            global_degraded += 1
        if is_error:
            entry["errors"] += 1
            global_errors += 1

        global_retries += retries
        all_latencies.append(latency)

    per_provider: list[dict[str, Any]] = []
    for provider, entry in sorted(providers.items()):
        calls = int(entry["calls"])
        rates = _build_rates(
            calls=calls,
            success=int(entry["success"]),
            degraded=int(entry["degraded"]),
            retries=int(entry["retries_total"]),
            errors=int(entry["errors"]),
        )
        per_provider.append(
            {
                "provider": provider,
                "calls": calls,
                "latency_ms_p50": _percentile(entry["latencies_ms"], 0.50),
                "latency_ms_p95": _percentile(entry["latencies_ms"], 0.95),
                "success_rate": rates["success_rate"],
                "degraded_rate": rates["degraded_rate"],
                "retry_rate": rates["retry_rate"],
                "error_rate": rates["error_rate"],
            }
        )

    total_calls = sum(int(item["calls"]) for item in per_provider)
    global_rates = _build_rates(
        calls=total_calls,
        success=global_success,
        degraded=global_degraded,
        retries=global_retries,
        errors=global_errors,
    )
    return {
        "global": {
            "calls": total_calls,
            "latency_ms_p50": _percentile(all_latencies, 0.50),
            "latency_ms_p95": _percentile(all_latencies, 0.95),
            "success_rate": global_rates["success_rate"],
            "degraded_rate": global_rates["degraded_rate"],
            "retry_rate": global_rates["retry_rate"],
            "error_rate": global_rates["error_rate"],
        },
        "providers": per_provider,
    }


def load_slo_thresholds(*, config_path: str = "config/slo.local.json") -> dict[str, float]:
    path = Path(config_path)
    thresholds = dict(DEFAULT_SLO_THRESHOLDS)
    if not path.exists():
        return thresholds
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        for key in DEFAULT_SLO_THRESHOLDS:
            value = payload.get(key)
            if isinstance(value, (int, float)):
                thresholds[key] = float(value)
    return thresholds


def evaluate_slo_status(*, slo_summary: dict[str, Any], thresholds: dict[str, float]) -> dict[str, Any]:
    global_metrics = slo_summary.get("global") if isinstance(slo_summary.get("global"), dict) else {}

    checks = {
        "p95_latency_ms": {
            "actual": float(global_metrics.get("latency_ms_p95") or 0.0),
            "threshold": float(thresholds["max_p95_latency_ms"]),
            "ok": float(global_metrics.get("latency_ms_p95") or 0.0) <= float(thresholds["max_p95_latency_ms"]),
        },
        "success_rate": {
            "actual": float(global_metrics.get("success_rate") or 0.0),
            "threshold": float(thresholds["min_success_rate"]),
            "ok": float(global_metrics.get("success_rate") or 0.0) >= float(thresholds["min_success_rate"]),
        },
        "degraded_rate": {
            "actual": float(global_metrics.get("degraded_rate") or 0.0),
            "threshold": float(thresholds["max_degraded_rate"]),
            "ok": float(global_metrics.get("degraded_rate") or 0.0) <= float(thresholds["max_degraded_rate"]),
        },
        "retry_rate": {
            "actual": float(global_metrics.get("retry_rate") or 0.0),
            "threshold": float(thresholds["max_retry_rate"]),
            "ok": float(global_metrics.get("retry_rate") or 0.0) <= float(thresholds["max_retry_rate"]),
        },
        "error_rate": {
            "actual": float(global_metrics.get("error_rate") or 0.0),
            "threshold": float(thresholds["max_error_rate"]),
            "ok": float(global_metrics.get("error_rate") or 0.0) <= float(thresholds["max_error_rate"]),
        },
    }
    failing = [name for name, detail in checks.items() if not bool(detail["ok"])]
    severity = "ok" if not failing else ("failed" if "error_rate" in failing or "success_rate" in failing else "warning")
    return {"status": severity, "checks": checks, "failing_checks": failing}
