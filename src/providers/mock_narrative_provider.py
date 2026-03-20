"""Provider mock concret pour la génération narrative."""

from __future__ import annotations

import time
from collections.abc import Mapping
from uuid import uuid4

from src.core.user_context import build_user_context
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
from src.providers.contracts import NarrativeProviderContract


class MockNarrativeProvider(BaseProvider, NarrativeProviderContract):
    """Provider narratif local et déterministe sans dépendance externe."""

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
            raise ProviderTimeout("Mock narrative timeout")
        if mode == "rate_limit":
            raise ProviderRateLimit("Mock narrative rate limit")
        if mode == "auth":
            raise ProviderAuthError("Mock narrative auth error")

    def generate_narrative(self, request: ProviderRequest) -> ProviderResponse:
        return call_with_normalized_errors(lambda: self._generate_narrative_impl(request))

    def _generate_narrative_impl(self, request: ProviderRequest) -> ProviderResponse:
        self._simulate_failure_if_needed()

        prompt = request.payload.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ProviderInvalidResponse("payload.prompt doit être une chaîne non vide")

        start = time.perf_counter()
        cleaned_prompt = prompt.strip()
        scene_id = "scene_1"
        user_profile = build_user_context(request.payload.get("user_profile"))
        preferences = user_profile["preferences"]

        data = {
            "request_id": request.request_id,
            "schema_version": "narrative.v1",
            "input": {
                "prompt": cleaned_prompt,
                "duration_sec": int(preferences.get("duration_sec") or 45),
                "style": str(preferences.get("genre") or "cinematic"),
                "language": str(preferences.get("language") or "fr"),
            },
            "output": {
                "synopsis": (
                    "Un protagoniste suit un indice décisif et transforme "
                    "une découverte discrète en révélation finale."
                ),
                "characters": [
                    {
                        "id": "char_1",
                        "name": "Alex",
                        "role": "protagonist",
                        "description": "Observateur persévérant qui suit chaque détail.",
                    }
                ],
                "scenes": [
                    {
                        "id": scene_id,
                        "summary": "Alex découvre un indice, l'analyse et agit.",
                        "duration_sec": 45,
                    }
                ],
                "shots": [
                    {
                        "id": "shot_001",
                        "scene_id": scene_id,
                        "description": "Plan d'ensemble: Alex arrive dans un lieu calme.",
                        "duration_sec": 12.0,
                    },
                    {
                        "id": "shot_002",
                        "scene_id": scene_id,
                        "description": "Gros plan: un indice apparaît sur la table.",
                        "duration_sec": 15.0,
                    },
                    {
                        "id": "shot_003",
                        "scene_id": scene_id,
                        "description": "Plan de conclusion: Alex prend une décision.",
                        "duration_sec": 18.0,
                    },
                ],
                "asset_refs": [],
                "audio_plan": {
                    "voiceover": {
                        "enabled": True,
                        "language": "fr",
                        "script": (
                            "Alex perçoit l'indice, relie les faits et agit avant qu'il ne soit trop tard."
                        ),
                    },
                    "ambience": {
                        "enabled": True,
                        "description": "Ambiance légère, tension progressive, final résolutif.",
                    },
                },
                "render_plan": {
                    "resolution": "1920x1080",
                    "fps": 24,
                    "format": "mp4",
                    "transitions": ["cut", "fade"],
                },
            },
        }

        latency_ms = int((time.perf_counter() - start) * 1000)
        model_name = "mock-narrative-v1"
        trace = {
            "stage": "story_generation",
            "provider": "mock_narrative_provider",
            "model": model_name,
            "trace_id": f"trace_{uuid4().hex[:12]}",
        }
        return ProviderResponse(
            data=data,
            provider_trace=trace,
            latency_ms=latency_ms,
            cost_estimate=0.002,
            model_name=model_name,
        )

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        """Compatibilité avec l'interface provider générique existante."""
        return self.generate_narrative(request)

    def healthcheck(self) -> ProviderHealth:
        return ProviderHealth(ok=True, details={"provider": "mock_narrative_provider"})
