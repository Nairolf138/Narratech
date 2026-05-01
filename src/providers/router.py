"""Routeur dynamique de providers basé sur contraintes + benchmark global."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.providers.base import BaseProvider


@dataclass(slots=True)
class RoutingConstraints:
    max_cost: float | None = None
    max_latency_ms: int | None = None
    min_quality_score: float | None = None


@dataclass(slots=True)
class RoutedProvider:
    provider: BaseProvider
    provider_name: str
    score: float
    error_rate: float
    avg_latency_ms: float
    avg_cost: float
    quality_score: float


class ProviderRouter:
    def __init__(self, benchmark_path: str = "outputs/benchmarks/provider_benchmark_global.json") -> None:
        self._benchmark_path = Path(benchmark_path)

    def rank_providers(
        self,
        *,
        candidates: list[BaseProvider],
        constraints: RoutingConstraints,
    ) -> list[RoutedProvider]:
        stats = self._load_stats()
        ranked: list[RoutedProvider] = []

        for provider in candidates:
            name = self._provider_name(provider)
            item = stats.get(name, {})
            error_rate = float(item.get("error_rate", 0.0))
            avg_latency = float(item.get("latency_ms_avg", 0.0))
            avg_cost = float(item.get("cost_avg", 0.0))
            quality_score = float(item.get("quality_score", 0.75))

            score = self._compute_score(
                avg_latency_ms=avg_latency,
                avg_cost=avg_cost,
                error_rate=error_rate,
                quality_score=quality_score,
                constraints=constraints,
            )
            ranked.append(
                RoutedProvider(
                    provider=provider,
                    provider_name=name,
                    score=score,
                    error_rate=error_rate,
                    avg_latency_ms=avg_latency,
                    avg_cost=avg_cost,
                    quality_score=quality_score,
                )
            )

        ranked.sort(key=lambda entry: (entry.score, -entry.error_rate), reverse=True)
        return ranked

    def _load_stats(self) -> dict[str, dict[str, float]]:
        if not self._benchmark_path.exists():
            return {}
        try:
            payload = json.loads(self._benchmark_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

        aggregate: dict[str, dict[str, float]] = {}
        runs = payload.get("runs") if isinstance(payload, dict) else []
        if not isinstance(runs, list):
            return aggregate

        for run in runs:
            providers = run.get("providers") if isinstance(run, dict) else []
            if not isinstance(providers, list):
                continue
            for entry in providers:
                if not isinstance(entry, dict):
                    continue
                name = str(entry.get("provider") or "unknown")
                calls = float(entry.get("calls") or 0)
                latency_total = float(entry.get("latency_ms_total") or 0.0)
                cost_total = float(entry.get("cost_estimate_total") or 0.0)
                errors = float(entry.get("error_count") or 0.0)
                status_counts = entry.get("status_counts") if isinstance(entry.get("status_counts"), dict) else {}
                ok_count = float(status_counts.get("ok", 0.0))
                degraded_count = float(status_counts.get("degraded", 0.0))

                agg = aggregate.setdefault(name, {"calls": 0.0, "latency_total": 0.0, "cost_total": 0.0, "errors": 0.0, "ok": 0.0, "degraded": 0.0})
                agg["calls"] += calls
                agg["latency_total"] += latency_total
                agg["cost_total"] += cost_total
                agg["errors"] += errors
                agg["ok"] += ok_count
                agg["degraded"] += degraded_count

        result: dict[str, dict[str, float]] = {}
        for name, agg in aggregate.items():
            calls = max(agg["calls"], 1.0)
            quality = agg["ok"] / max(agg["ok"] + agg["degraded"], 1.0)
            result[name] = {
                "error_rate": agg["errors"] / calls,
                "latency_ms_avg": agg["latency_total"] / calls,
                "cost_avg": agg["cost_total"] / calls,
                "quality_score": quality,
            }
        return result

    def _compute_score(self, *, avg_latency_ms: float, avg_cost: float, error_rate: float, quality_score: float, constraints: RoutingConstraints) -> float:
        latency_score = 1.0 / (1.0 + (avg_latency_ms / 1200.0))
        cost_score = 1.0 / (1.0 + (avg_cost / 0.02))
        reliability_score = 1.0 - min(max(error_rate, 0.0), 1.0)
        base_score = (quality_score * 0.45) + (reliability_score * 0.35) + (latency_score * 0.1) + (cost_score * 0.1)

        if constraints.max_latency_ms is not None and avg_latency_ms > constraints.max_latency_ms:
            base_score -= 0.2
        if constraints.max_cost is not None and avg_cost > constraints.max_cost:
            base_score -= 0.2
        if constraints.min_quality_score is not None and quality_score < constraints.min_quality_score:
            base_score -= 0.25
        return round(base_score, 6)

    @staticmethod
    def _provider_name(provider: BaseProvider) -> str:
        custom = getattr(provider, "_config", {}).get("provider_name") if hasattr(provider, "_config") else None
        if isinstance(custom, str) and custom:
            return custom
        return provider.__class__.__name__.replace("Provider", "").lower()


__all__ = ["ProviderRouter", "RoutingConstraints", "RoutedProvider"]
