"""Chargement de configuration provider via couche runtime unifiée."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.config.runtime import load_runtime_config
from src.providers import (
    AsyncShotProvider,
    BaseProvider,
    LocalAssetProvider,
    MockAssetProvider,
    MockAudioProvider,
    MockNarrativeProvider,
    MockShotProvider,
)
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
    audio: ProviderSlot
    success_criteria: dict[str, Any]


_PROVIDER_REGISTRY: dict[str, type[BaseProvider]] = {
    "mock_narrative": MockNarrativeProvider,
    "mock_asset": MockAssetProvider,
    "local_asset": LocalAssetProvider,
    "mock_shot": MockShotProvider,
    "picsum_shot": PicsumShotProvider,
    "async_shot": AsyncShotProvider,
    "openai_narrative": OpenAINarrativeProvider,
    "mock_audio": MockAudioProvider,
}


_DEFAULT_POLICY = {
    "enabled": True,
    "trigger_on": ["ProviderTimeout", "ProviderRateLimit"],
    "activate_after_attempt": 2,
}


def _build_provider(*, provider_type: str, config: dict[str, Any] | None = None) -> BaseProvider:
    provider_cls = _PROVIDER_REGISTRY.get(provider_type)
    if provider_cls is None:
        raise ValueError(f"Type provider inconnu: {provider_type}")

    provider = provider_cls()
    if isinstance(config, dict) and config:
        provider.configure(config)
    return provider


def load_provider_bundle(environment: str | None = None, config_dir: str = "config") -> ProviderBundle:
    del config_dir  # conservé pour compatibilité de signature
    runtime = load_runtime_config(profile=environment)

    narrative_config = {
        "type": runtime.narrative.provider,
        "config": {
            "model": runtime.narrative.model,
            "api_key": runtime.narrative.api_key,
            "timeout_sec": runtime.narrative.timeout_sec,
        },
    }

    asset_config = {
        "type": runtime.asset.provider,
        "config": {
            "model": runtime.asset.model,
            "timeout_sec": runtime.asset.timeout_sec,
        },
    }
    shot_config = {
        "type": runtime.shot.provider,
        "config": {
            "model": runtime.shot.model,
            "timeout_sec": runtime.shot.timeout_sec,
        },
    }
    audio_config = {
        "type": runtime.audio.provider,
        "config": {
            "model": runtime.audio.model,
            "timeout_sec": runtime.audio.timeout_sec,
            "provider_name": runtime.audio.provider,
        },
    }

    return ProviderBundle(
        environment=runtime.profile,
        vertical=runtime.vertical,
        story=ProviderSlot(
            primary=create_narrative_provider(narrative_config),
            fallback=_build_provider(provider_type="mock_narrative"),
            fallback_policy=dict(_DEFAULT_POLICY),
        ),
        asset=ProviderSlot(
            primary=_build_provider(provider_type=asset_config["type"], config=asset_config["config"]),
            fallback=_build_provider(provider_type="mock_asset"),
            fallback_policy=dict(_DEFAULT_POLICY),
        ),
        shot=ProviderSlot(
            primary=_build_provider(provider_type=shot_config["type"], config=shot_config["config"]),
            fallback=_build_provider(provider_type="mock_shot"),
            fallback_policy=dict(_DEFAULT_POLICY),
        ),
        audio=ProviderSlot(
            primary=_build_provider(provider_type=audio_config["type"], config=audio_config["config"]),
            fallback=_build_provider(provider_type="mock_audio"),
            fallback_policy=dict(_DEFAULT_POLICY),
        ),
        success_criteria={
            "max_total_runtime_sec": 30,
            "expected_shot_count": 3,
            "max_placeholder_ratio": 0.2,
            "min_coherence_score": 0.8,
        },
    )
