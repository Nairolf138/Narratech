"""Chargement de configuration provider par environnement."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.providers import AsyncShotProvider, BaseProvider, LocalAssetProvider, MockAssetProvider, MockNarrativeProvider, MockShotProvider
from src.providers.factory import create_narrative_provider
from src.providers.narrative.openai_provider import OpenAINarrativeProvider
from src.providers.picsum_shot_provider import PicsumShotProvider


@dataclass(slots=True)
class ProviderSlot:
    primary: BaseProvider
    fallback: BaseProvider
    fallback_policy: dict[str, Any]


@dataclass(slots=True)
class ProviderBundle:
    environment: str
    vertical: str
    story: ProviderSlot
    asset: ProviderSlot
    shot: ProviderSlot
    success_criteria: dict[str, Any]


_PROVIDER_REGISTRY: dict[str, type[BaseProvider]] = {
    "mock_narrative": MockNarrativeProvider,
    "mock_asset": MockAssetProvider,
    "local_asset": LocalAssetProvider,
    "mock_shot": MockShotProvider,
    "picsum_shot": PicsumShotProvider,
    "async_shot": AsyncShotProvider,
    "openai_narrative": OpenAINarrativeProvider,
}


def _build_provider(definition: dict[str, Any], default_type: str) -> BaseProvider:
    provider_type = str(definition.get("type") or default_type)
    provider_cls = _PROVIDER_REGISTRY.get(provider_type)
    if provider_cls is None:
        raise ValueError(f"Type provider inconnu: {provider_type}")

    provider = provider_cls()
    config = definition.get("config")
    if isinstance(config, dict):
        provider.configure(config)
    return provider


def load_provider_bundle(environment: str | None = None, config_dir: str = "config") -> ProviderBundle:
    env_name = environment or os.getenv("NARRATECH_ENV", "local")
    config_path = Path(config_dir) / f"providers.{env_name}.json"
    if not config_path.exists():
        raise FileNotFoundError(
            f"Configuration provider introuvable pour l'environnement '{env_name}': {config_path.as_posix()}"
        )

    payload = json.loads(config_path.read_text(encoding="utf-8"))
    providers = payload.get("providers") if isinstance(payload, dict) else None
    if not isinstance(providers, dict):
        raise ValueError("Le fichier de config provider doit contenir un objet 'providers'")

    story_config = providers.get("story", {}) if isinstance(providers.get("story"), dict) else {}
    asset_config = providers.get("asset", {}) if isinstance(providers.get("asset"), dict) else {}
    shot_config = providers.get("shot", {}) if isinstance(providers.get("shot"), dict) else {}

    return ProviderBundle(
        environment=env_name,
        vertical=str(payload.get("vertical") or "default"),
        story=ProviderSlot(
            primary=create_narrative_provider(story_config.get("primary", {})),
            fallback=create_narrative_provider(story_config.get("fallback", {})),
            fallback_policy=(
                story_config.get("fallback_policy")
                if isinstance(story_config.get("fallback_policy"), dict)
                else {}
            ),
        ),
        asset=ProviderSlot(
            primary=_build_provider(asset_config.get("primary", {}), "mock_asset"),
            fallback=_build_provider(asset_config.get("fallback", {}), "mock_asset"),
            fallback_policy=(
                asset_config.get("fallback_policy")
                if isinstance(asset_config.get("fallback_policy"), dict)
                else {}
            ),
        ),
        shot=ProviderSlot(
            primary=_build_provider(shot_config.get("primary", {}), "mock_shot"),
            fallback=_build_provider(shot_config.get("fallback", {}), "mock_shot"),
            fallback_policy=(
                shot_config.get("fallback_policy")
                if isinstance(shot_config.get("fallback_policy"), dict)
                else {}
            ),
        ),
        success_criteria=payload.get("success_criteria", {}) if isinstance(payload, dict) else {},
    )
