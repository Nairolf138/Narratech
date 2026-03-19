"""Moteur de génération narrative conforme au schéma narrative.v1."""

from __future__ import annotations

from uuid import uuid4

from src.core.io_utils import write_json_utf8
from src.providers import MockNarrativeProvider, ProviderRequest, ProviderResponse
from src.providers.adapter import call_with_normalized_errors
from src.providers.contracts import NarrativeProviderContract


class StoryEngine:
    """Construit un payload narratif V1 via un provider injectable."""

    schema_version = "narrative.v1"

    def __init__(self, provider: NarrativeProviderContract | None = None) -> None:
        self.provider = provider or MockNarrativeProvider()

    def _build_response(self, prompt: str, request_id: str | None = None) -> ProviderResponse:
        request = ProviderRequest(
            request_id=request_id or f"req_{uuid4().hex}",
            payload={"prompt": prompt},
            timeout_sec=8.0,
        )
        return call_with_normalized_errors(
            lambda: (
                self.provider.generate_narrative(request)
                if hasattr(self.provider, "generate_narrative")
                else self.provider.generate(request)
            )
        )

    def generate(self, prompt: str, request_id: str | None = None) -> dict:
        """Génère une narration minimale valide et la sauvegarde sur disque."""
        if not prompt or not prompt.strip():
            raise ValueError("Le prompt doit être non vide.")

        response = self._build_response(prompt.strip(), request_id=request_id)
        narrative = dict(response.data)
        provider_trace = dict(response.provider_trace)
        provider_trace.setdefault("stage", "story_generation")
        provider_trace.setdefault("provider", "mock_narrative_provider")
        provider_trace.setdefault("model", response.model_name)
        provider_trace.setdefault("trace_id", f"trace_{uuid4().hex[:12]}")
        provider_trace["latency_ms"] = response.latency_ms
        narrative["provider_trace"] = [provider_trace]

        write_json_utf8("outputs/scene.json", narrative)
        return narrative
