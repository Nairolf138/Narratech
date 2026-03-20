"""Provider mock concret pour la génération de clips de shots."""

from __future__ import annotations

import time
from collections.abc import Mapping
from uuid import uuid4

from src.providers.adapter import call_with_normalized_errors
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
from src.providers.contracts import ShotProviderContract
from src.providers.trace import build_provider_trace


class MockShotProvider(BaseProvider, ShotProviderContract):
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

    def generate_shots(self, request: ProviderRequest) -> ProviderResponse:
        return call_with_normalized_errors(lambda: self._generate_shots_impl(request))

    def _generate_shots_impl(self, request: ProviderRequest) -> ProviderResponse:
        self._simulate_failure_if_needed()

        output = request.payload.get("output")
        if not isinstance(output, dict):
            raise ProviderInvalidResponse("payload.output doit être un objet")

        shots = output.get("shots")
        if not isinstance(shots, list):
            raise ProviderInvalidResponse("payload.output.shots doit être une liste")
        asset_refs = request.payload.get("asset_refs", [])
        if not isinstance(asset_refs, list):
            raise ProviderInvalidResponse("payload.asset_refs doit être une liste")

        start = time.perf_counter()
        clips: list[dict] = []
        asset_dependency_ids = [
            str(asset.get("id"))
            for asset in asset_refs
            if isinstance(asset, dict) and asset.get("id") is not None
        ]

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
                    "asset_dependencies": asset_dependency_ids,
                }
            )

        latency_ms = int((time.perf_counter() - start) * 1000)
        model_name = "mock-shot-v1"
        cost_estimate = 0.0015
        return ProviderResponse(
            data={"clips": clips},
            provider_trace=build_provider_trace(
                provider="mock_shot_provider",
                model=model_name,
                latency_ms=latency_ms,
                cost_estimate=cost_estimate,
                retries=0,
                status="success",
                error=None,
                stage="shot_generation",
                trace_id=f"trace_{uuid4().hex[:12]}",
                asset_ref_count=len(asset_dependency_ids),
                asset_dependency_ids=asset_dependency_ids,
            ),
            latency_ms=latency_ms,
            cost_estimate=cost_estimate,
            model_name=model_name,
        )

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        """Compatibilité avec l'interface provider générique existante."""
        return self.generate_shots(request)

    def healthcheck(self) -> ProviderHealth:
        return ProviderHealth(ok=True, details={"provider": "mock_shot_provider"})
