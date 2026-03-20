"""Provider mock concret pour la génération audio narratif et ambiance."""

from __future__ import annotations

import time
from collections.abc import Mapping
from pathlib import Path
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
from src.providers.contracts import AudioProviderContract
from src.providers.trace import build_provider_trace


class MockAudioProvider(BaseProvider, AudioProviderContract):
    """Génère des pistes audio placeholder avec alignement temporel minimal par shot."""

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
            raise ProviderTimeout("Mock audio timeout")
        if mode == "rate_limit":
            raise ProviderRateLimit("Mock audio rate limit")
        if mode == "auth":
            raise ProviderAuthError("Mock audio auth error")

    def synthesize_audio(self, request: ProviderRequest) -> ProviderResponse:
        return call_with_normalized_errors(lambda: self._synthesize_audio_impl(request))

    def _synthesize_audio_impl(self, request: ProviderRequest) -> ProviderResponse:
        self._simulate_failure_if_needed()

        payload = request.payload
        narrative_text = payload.get("narrative_text")
        if not isinstance(narrative_text, str) or not narrative_text.strip():
            raise ProviderInvalidResponse("payload.narrative_text doit être une chaîne non vide")

        mode = str(payload.get("mode") or "voiceover")
        if mode not in {"voiceover", "ambience"}:
            raise ProviderInvalidResponse("payload.mode doit être 'voiceover' ou 'ambience'")

        voice = payload.get("voice")
        voice_params = voice if isinstance(voice, dict) else {}
        language = str(payload.get("language") or voice_params.get("language") or "und")
        style = str(payload.get("style") or voice_params.get("style") or "neutral")
        format_name = str(payload.get("format") or "txt")
        provider_name = str(self._config.get("provider_name") or "mock_audio_provider")

        shots = payload.get("shots")
        if shots is None:
            shots = []
        if not isinstance(shots, list):
            raise ProviderInvalidResponse("payload.shots doit être une liste")

        request_id = str(payload.get("request_id") or request.request_id or "request_unknown")
        start = time.perf_counter()
        out_dir = Path("outputs/audio")
        out_dir.mkdir(parents=True, exist_ok=True)

        file_name = f"{mode}.{format_name}"
        file_path = out_dir / file_name

        timeline: list[dict[str, object]] = []
        cursor = 0.0
        for shot in shots:
            if not isinstance(shot, dict):
                continue
            duration = float(shot.get("duration_sec") or 0.0)
            if duration < 0:
                duration = 0.0
            start_sec = round(cursor, 3)
            end_sec = round(cursor + duration, 3)
            timeline.append(
                {
                    "shot_id": str(shot.get("id") or f"shot_{len(timeline) + 1:03d}"),
                    "start_sec": start_sec,
                    "end_sec": end_sec,
                }
            )
            cursor += duration

        duration_sec = round(cursor, 3)
        file_path.write_text(
            (
                f"type: {mode}\n"
                f"request_id: {request_id}\n"
                f"language: {language}\n"
                f"style: {style}\n"
                f"duration_sec: {duration_sec}\n"
                f"narrative_text: {narrative_text.strip()}\n"
            ),
            encoding="utf-8",
        )

        latency_ms = int((time.perf_counter() - start) * 1000)
        model_name = "mock-audio-v1"
        cost_estimate = 0.001
        return ProviderResponse(
            data={
                "request_id": request_id,
                "mode": mode,
                "audio_file": file_path.as_posix(),
                "metadata": {
                    "duration_sec": duration_sec,
                    "format": format_name,
                    "provider": provider_name,
                    "language": language,
                    "style": style,
                },
                "timestamps": timeline,
            },
            provider_trace=build_provider_trace(
                provider=provider_name,
                model=model_name,
                latency_ms=latency_ms,
                cost_estimate=cost_estimate,
                retries=0,
                status="success",
                error=None,
                stage="audio_generation",
                trace_id=f"trace_{uuid4().hex[:12]}",
                mode=mode,
            ),
            latency_ms=latency_ms,
            cost_estimate=cost_estimate,
            model_name=model_name,
        )

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        """Compatibilité avec l'interface provider générique existante."""
        return self.synthesize_audio(request)

    def healthcheck(self) -> ProviderHealth:
        return ProviderHealth(ok=True, details={"provider": "mock_audio_provider"})
