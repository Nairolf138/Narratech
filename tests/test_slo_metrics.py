from __future__ import annotations

from src.core.slo_metrics import compute_slo_summary, evaluate_slo_status


def test_compute_slo_summary_nominal_traces() -> None:
    traces = [
        {"provider": "p1", "status": "success", "latency_ms": 100, "retries": 0, "error": ""},
        {"provider": "p1", "status": "success", "latency_ms": 120, "retries": 1, "error": ""},
        {"provider": "p2", "status": "success", "latency_ms": 80, "retries": 0, "error": ""},
    ]

    summary = compute_slo_summary(traces=traces)

    assert summary["global"]["calls"] == 3
    assert summary["global"]["success_rate"] == 1.0
    assert summary["global"]["error_rate"] == 0.0
    assert len(summary["providers"]) == 2


def test_compute_slo_summary_degraded_and_failed_traces() -> None:
    traces = [
        {"provider": "p1", "status": "success", "latency_ms": 100, "retries": 0, "error": ""},
        {"provider": "p1", "status": "degraded", "latency_ms": 1900, "retries": 1, "error": ""},
        {"provider": "p2", "status": "failed", "latency_ms": 2200, "retries": 2, "error": "timeout"},
    ]

    summary = compute_slo_summary(traces=traces)
    thresholds = {
        "max_p95_latency_ms": 1500.0,
        "min_success_rate": 0.95,
        "max_degraded_rate": 0.15,
        "max_retry_rate": 0.25,
        "max_error_rate": 0.05,
    }
    evaluation = evaluate_slo_status(slo_summary=summary, thresholds=thresholds)

    assert summary["global"]["degraded_rate"] == 0.3333
    assert summary["global"]["error_rate"] == 0.3333
    assert evaluation["status"] == "failed"
    assert "success_rate" in evaluation["failing_checks"]
    assert "error_rate" in evaluation["failing_checks"]
