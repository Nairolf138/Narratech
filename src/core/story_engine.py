"""Moteur de génération narrative conforme au schéma narrative.v1."""

from __future__ import annotations

from uuid import uuid4

from src.core.io_utils import write_json_utf8
from src.core.user_context import UserProfile, build_user_context
from src.providers import MockNarrativeProvider, ProviderRequest, ProviderResponse
from src.providers.adapter import call_with_normalized_errors
from src.providers.contracts import NarrativeProviderContract


class StoryEngine:
    """Construit un payload narratif V1 via un provider injectable."""

    schema_version = "narrative.v1"

    def __init__(self, provider: NarrativeProviderContract | None = None) -> None:
        self.provider = provider or MockNarrativeProvider()

    def _build_response(
        self,
        prompt: str,
        request_id: str | None = None,
        user_profile: UserProfile | None = None,
    ) -> ProviderResponse:
        resolved_profile = build_user_context(user_profile)
        request = ProviderRequest(
            request_id=request_id or f"req_{uuid4().hex}",
            payload={"prompt": prompt, "user_profile": resolved_profile},
            timeout_sec=8.0,
        )
        return call_with_normalized_errors(
            lambda: (
                self.provider.generate_narrative(request)
                if hasattr(self.provider, "generate_narrative")
                else self.provider.generate(request)
            )
        )

    def generate(
        self,
        prompt: str,
        request_id: str | None = None,
        user_profile: UserProfile | None = None,
    ) -> dict:
        """Génère une narration minimale valide et la sauvegarde sur disque."""
        if not prompt or not prompt.strip():
            raise ValueError("Le prompt doit être non vide.")

        resolved_profile = build_user_context(user_profile)
        response = self._build_response(prompt.strip(), request_id=request_id, user_profile=resolved_profile)
        narrative = dict(response.data)
        response_trace = dict(response.provider_trace)
        response_trace.setdefault("stage", "story_generation")
        response_trace.setdefault("provider", "mock_narrative_provider")
        response_trace.setdefault("model", response.model_name)
        response_trace.setdefault("modele", response.model_name)
        response_trace.setdefault("trace_id", f"trace_{uuid4().hex[:12]}")
        response_trace["latency_ms"] = response.latency_ms
        response_trace.setdefault("cost_estimate", response.cost_estimate)
        response_trace.setdefault("retries", 0)
        response_trace.setdefault("status", "success")
        response_trace.setdefault("error", None)

        allowed_trace_keys = {
            "stage",
            "provider",
            "model",
            "modele",
            "trace_id",
            "latency_ms",
            "cost_estimate",
            "retries",
            "status",
            "error",
            "fallback_mode",
            "fallback_reason",
        }
        narrative["provider_trace"] = [{key: value for key, value in response_trace.items() if key in allowed_trace_keys}]

        write_json_utf8("outputs/scene.json", narrative)
        return narrative
