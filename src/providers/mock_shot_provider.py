"""Provider mock concret pour la génération de clips de shots."""

from __future__ import annotations

import time
from collections.abc import Mapping

from src.providers.base import (
    BaseProvider,
    ProviderAuthError,
    ProviderHealth,
    ProviderInvalidResponse,
    ProviderRateLimit,
    ProviderRequest,
    ProviderResponse,
    ProviderTimeout,
)


class MockShotProvider(BaseProvider):
    """Produit un plan de clips déterministe à partir des shots enrichis."""

    def __init__(self) -> None:
        self._config: dict[str, object] = {}
        self._calls = 0

    def configure(self, config: Mapping[str, object]) -> None:
        self._config = dict(config)

    def _simulate_failure_if_needed(self) -> None:
        self._calls += 1
        failures = self._config.get("failure_sequence", [])
        if not isinstance(failures, list) or not failures:
            return

        index = min(self._calls - 1, len(failures) - 1)
        mode = failures[index]
        if mode == "timeout":
            raise ProviderTimeout("Mock shot timeout")
        if mode == "rate_limit":
            raise ProviderRateLimit("Mock shot rate limit")
        if mode == "auth":
            raise ProviderAuthError("Mock shot auth error")

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        self._simulate_failure_if_needed()

        output = request.payload.get("output")
        if not isinstance(output, dict):
            raise ProviderInvalidResponse("payload.output doit être un objet")

        shots = output.get("shots")
        if not isinstance(shots, list):
            raise ProviderInvalidResponse("payload.output.shots doit être une liste")

        start = time.perf_counter()
        clips: list[dict] = []

        for order, shot in enumerate(shots, start=1):
            if not isinstance(shot, dict):
                continue
            shot_id = str(shot.get("id") or f"shot_{order:03d}")
            duration = float(shot.get("duration_sec") or 0.0)
            desc = str(shot.get("enriched_prompt") or shot.get("description") or "")

            clips.append(
                {
                    "order": order,
                    "shot_id": shot_id,
                    "duration": duration if duration > 0 else 0.0,
                    "description_enriched": desc,
                    "file_name": f"shot_{order:03d}_{shot_id}.txt",
                }
            )

        latency_ms = int((time.perf_counter() - start) * 1000)
        return ProviderResponse(
            data={"clips": clips},
            provider_trace={"stage": "shot_generation", "provider": "mock_shot_provider"},
            latency_ms=latency_ms,
            cost_estimate=0.0015,
            model_name="mock-shot-v1",
        )

    def healthcheck(self) -> ProviderHealth:
        return ProviderHealth(ok=True, details={"provider": "mock_shot_provider"})
