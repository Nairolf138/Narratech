"""Agrégation simple des traces provider pour benchmark run/global."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.core.io_utils import write_json_utf8


Trace = dict[str, Any]


def aggregate_provider_benchmark(*, request_id: str, traces: list[Trace]) -> dict[str, Any]:
    providers: dict[str, dict[str, Any]] = {}

    for trace in traces:
        if not isinstance(trace, dict):
            continue
        provider = str(trace.get("provider") or "unknown")
        entry = providers.setdefault(
            provider,
            {
                "provider": provider,
                "calls": 0,
                "latency_ms_total": 0,
                "latency_ms_avg": 0.0,
                "cost_estimate_total": 0.0,
                "retries_total": 0,
                "error_count": 0,
                "status_counts": {},
                "models": [],
            },
        )
        entry["calls"] += 1
        entry["latency_ms_total"] += int(trace.get("latency_ms") or 0)
        entry["cost_estimate_total"] += float(trace.get("cost_estimate") or 0.0)
        entry["retries_total"] += int(trace.get("retries") or 0)

        status = str(trace.get("status") or "unknown")
        status_counts = entry["status_counts"]
        status_counts[status] = int(status_counts.get(status, 0)) + 1
        if status in {"failed", "degraded"} or trace.get("error"):
            entry["error_count"] += 1

        model = str(trace.get("model") or "unknown")
        if model not in entry["models"]:
            entry["models"].append(model)

    per_provider = []
    for provider_entry in providers.values():
        calls = int(provider_entry["calls"])
        provider_entry["latency_ms_avg"] = round(provider_entry["latency_ms_total"] / calls, 2) if calls else 0.0
        provider_entry["cost_estimate_total"] = round(float(provider_entry["cost_estimate_total"]), 6)
        per_provider.append(provider_entry)

    per_provider.sort(key=lambda item: str(item["provider"]))
    return {
        "request_id": request_id,
        "totals": {
            "calls": sum(int(item["calls"]) for item in per_provider),
            "latency_ms_total": sum(int(item["latency_ms_total"]) for item in per_provider),
            "cost_estimate_total": round(sum(float(item["cost_estimate_total"]) for item in per_provider), 6),
            "retries_total": sum(int(item["retries_total"]) for item in per_provider),
            "error_count": sum(int(item["error_count"]) for item in per_provider),
        },
        "providers": per_provider,
    }


def update_global_provider_benchmark(
    *,
    run_benchmark: dict[str, Any],
    target_path: str = "outputs/benchmarks/provider_benchmark_global.json",
) -> dict[str, Any]:
    path = Path(target_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            existing = {}
    else:
        existing = {}

    runs = existing.get("runs") if isinstance(existing.get("runs"), list) else []
    runs.append(run_benchmark)

    total_calls = 0
    total_latency = 0
    total_cost = 0.0
    total_retries = 0
    total_errors = 0
    for run in runs:
        if not isinstance(run, dict):
            continue
        totals = run.get("totals") if isinstance(run.get("totals"), dict) else {}
        total_calls += int(totals.get("calls") or 0)
        total_latency += int(totals.get("latency_ms_total") or 0)
        total_cost += float(totals.get("cost_estimate_total") or 0.0)
        total_retries += int(totals.get("retries_total") or 0)
        total_errors += int(totals.get("error_count") or 0)

    global_benchmark = {
        "runs": runs,
        "totals": {
            "runs": len(runs),
            "calls": total_calls,
            "latency_ms_total": total_latency,
            "latency_ms_avg_per_call": round(total_latency / total_calls, 2) if total_calls else 0.0,
            "cost_estimate_total": round(total_cost, 6),
            "retries_total": total_retries,
            "error_count": total_errors,
        },
    }
    write_json_utf8(path, global_benchmark)
    return global_benchmark
