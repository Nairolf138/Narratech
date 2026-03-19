"""Provider mock concret pour la génération de références d'assets."""

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


class MockAssetProvider(BaseProvider):
    """Produit des références d'assets déterministes à partir du document enrichi."""

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
            raise ProviderTimeout("Mock asset timeout")
        if mode == "rate_limit":
            raise ProviderRateLimit("Mock asset rate limit")
        if mode == "auth":
            raise ProviderAuthError("Mock asset auth error")

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        self._simulate_failure_if_needed()

        output = request.payload.get("output")
        if not isinstance(output, dict):
            raise ProviderInvalidResponse("payload.output doit être un objet")

        request_id = str(request.payload.get("request_id", "request_unknown"))
        start = time.perf_counter()

        assets: list[dict] = []
        characters = output.get("characters", [])
        for index, character in enumerate(characters, start=1):
            if not isinstance(character, dict):
                continue

            char_name = str(character.get("name") or character.get("id") or f"char_{index}")
            assets.append(
                {
                    "id": f"asset_character_{index:03d}",
                    "type": "character",
                    "file_name": f"character_{char_name.lower()}_{index:02d}.json",
                    "payload": {
                        "kind": "character",
                        "character_id": str(character.get("id") or f"char_{index}"),
                        "character_name": char_name,
                        "placeholder": True,
                    },
                }
            )

        scenes = output.get("scenes", [])
        scene_summary = ""
        if scenes and isinstance(scenes[0], dict):
            scene_summary = str(scenes[0].get("summary") or "")

        assets.append(
            {
                "id": "asset_environment_001",
                "type": "environment",
                "file_name": "environment_main_01.json",
                "payload": {
                    "kind": "environment",
                    "scene_summary": scene_summary,
                    "placeholder": True,
                },
            }
        )

        latency_ms = int((time.perf_counter() - start) * 1000)
        return ProviderResponse(
            data={"request_id": request_id, "assets": assets},
            provider_trace={"stage": "asset_generation", "provider": "mock_asset_provider"},
            latency_ms=latency_ms,
            cost_estimate=0.001,
            model_name="mock-asset-v1",
        )

    def healthcheck(self) -> ProviderHealth:
        return ProviderHealth(ok=True, details={"provider": "mock_asset_provider"})
