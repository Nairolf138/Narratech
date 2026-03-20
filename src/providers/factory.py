"""Factory de sélection provider actif selon la config runtime."""

from __future__ import annotations

import os
from typing import Any

from src.providers.base import BaseProvider
from src.providers.mock_narrative_provider import MockNarrativeProvider
from src.providers.narrative.openai_provider import OpenAINarrativeProvider


_NARRATIVE_PROVIDER_REGISTRY: dict[str, type[BaseProvider]] = {
    "mock_narrative": MockNarrativeProvider,
    "openai_narrative": OpenAINarrativeProvider,
}


def create_narrative_provider(definition: dict[str, Any] | None = None) -> BaseProvider:
    definition = dict(definition or {})
    selected_type = str(
        os.getenv("NARRATECH_NARRATIVE_PROVIDER")
        or definition.get("type")
        or "mock_narrative"
    )

    provider_cls = _NARRATIVE_PROVIDER_REGISTRY.get(selected_type)
    if provider_cls is None:
        raise ValueError(f"Type provider narratif inconnu: {selected_type}")

    provider = provider_cls()
    config = definition.get("config")
    if isinstance(config, dict):
        provider.configure(config)
    return provider


__all__ = ["create_narrative_provider"]
