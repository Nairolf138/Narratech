"""Provider shot semi-réel basé sur des URLs d'images stables (Picsum)."""

from __future__ import annotations

import time
from collections.abc import Mapping
from uuid import uuid4

from src.providers.adapter import call_with_normalized_errors
from src.providers.base import BaseProvider, ProviderHealth, ProviderInvalidResponse, ProviderRequest, ProviderResponse
from src.providers.contracts import ShotProviderContract
from src.providers.trace import build_provider_trace


class PicsumShotProvider(BaseProvider, ShotProviderContract):
    """Construit des shots "semi-réels" en attachant des URLs d'images publiques."""

    def __init__(self) -> None:
        self._config: dict[str, object] = {
            "base_url": "https://picsum.photos",
            "width": 1280,
            "height": 720,
            "seed_prefix": "narratech",
        }

    def configure(self, config: Mapping[str, object]) -> None:
        merged = dict(self._config)
        merged.update(dict(config))
        self._config = merged

    def generate_shots(self, request: ProviderRequest) -> ProviderResponse:
        return call_with_normalized_errors(lambda: self._generate_shots_impl(request))

    def _generate_shots_impl(self, request: ProviderRequest) -> ProviderResponse:
        output = request.payload.get("output")
        if not isinstance(output, dict):
            raise ProviderInvalidResponse("payload.output doit être un objet")

        shots = output.get("shots")
        if not isinstance(shots, list):
            raise ProviderInvalidResponse("payload.output.shots doit être une liste")

        asset_refs = request.payload.get("asset_refs", [])
        if not isinstance(asset_refs, list):
            raise ProviderInvalidResponse("payload.asset_refs doit être une liste")

        base_url = str(self._config.get("base_url") or "https://picsum.photos").rstrip("/")
        width = int(self._config.get("width") or 1280)
        height = int(self._config.get("height") or 720)
        seed_prefix = str(self._config.get("seed_prefix") or "narratech")

        start = time.perf_counter()
        asset_dependency_ids = [
            str(asset.get("id"))
            for asset in asset_refs
            if isinstance(asset, dict) and asset.get("id") is not None
        ]

        clips: list[dict] = []
        for order, shot in enumerate(shots, start=1):
            if not isinstance(shot, dict):
                continue
            shot_id = str(shot.get("id") or f"shot_{order:03d}")
            desc = str(shot.get("enriched_prompt") or shot.get("description") or "")
            duration = float(shot.get("duration_sec") or 0.0)
            image_url = f"{base_url}/seed/{seed_prefix}-{request.request_id}-{shot_id}/{width}/{height}"

            clips.append(
                {
                    "order": order,
                    "shot_id": shot_id,
                    "duration": duration,
                    "description_enriched": f"{desc} | ref_image={image_url}",
                    "file_name": f"shot_{order:03d}_{shot_id}.txt",
                    "asset_dependencies": asset_dependency_ids,
                    "reference_image_url": image_url,
                }
            )

        latency_ms = int((time.perf_counter() - start) * 1000)
        model_name = "picsum-shot-v1"
        cost_estimate = 0.0
        return ProviderResponse(
            data={"clips": clips},
            provider_trace=build_provider_trace(
                provider="picsum_shot_provider",
                model=model_name,
                latency_ms=latency_ms,
                cost_estimate=cost_estimate,
                retries=0,
                status="success",
                error=None,
                stage="shot_generation",
                trace_id=f"trace_{uuid4().hex[:12]}",
                mode="semi_real",
            ),
            latency_ms=latency_ms,
            cost_estimate=cost_estimate,
            model_name=model_name,
        )

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        return self.generate_shots(request)

    def healthcheck(self) -> ProviderHealth:
        return ProviderHealth(ok=True, details={"provider": "picsum_shot_provider", "mode": "semi_real"})
