"""Tests pour la couche de configuration provider unifiée."""

from __future__ import annotations

import pytest

from src.config.providers import load_provider_bundle
from src.config.runtime import ConfigValidationError, load_runtime_config
from src.providers import MockAudioProvider, MockShotProvider
from src.providers.narrative.openai_provider import OpenAINarrativeProvider
from src.providers.picsum_shot_provider import PicsumShotProvider


def test_load_provider_bundle_local_fallback_profile_uses_mock_vertical() -> None:
    bundle = load_provider_bundle("local-fallback")

    assert bundle.environment == "local-fallback"
    assert bundle.vertical == "local_mock_full"
    assert isinstance(bundle.shot.primary, MockShotProvider)
    assert isinstance(bundle.audio.primary, MockAudioProvider)
    assert bundle.story.fallback_policy.get("enabled") is True


def test_load_provider_bundle_dev_profile_uses_picsum_shot() -> None:
    bundle = load_provider_bundle("dev")

    assert bundle.environment == "dev"
    assert bundle.vertical == "dev_picsum_story_mock"
    assert isinstance(bundle.shot.primary, PicsumShotProvider)
    assert bundle.success_criteria.get("expected_shot_count") == 3


def test_load_provider_bundle_prod_requires_api_key_when_openai_story(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("NARRATECH_API_KEY_NARRATIVE", raising=False)

    with pytest.raises(ConfigValidationError):
        load_provider_bundle("prod")


def test_load_runtime_config_accepts_alias_local_to_local_fallback() -> None:
    runtime = load_runtime_config("local")
    assert runtime.profile == "local-fallback"


def test_load_provider_bundle_prod_can_build_openai_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    bundle = load_provider_bundle("prod")
    assert isinstance(bundle.story.primary, OpenAINarrativeProvider)
