"""Tests pour la configuration providers par environnement."""

from __future__ import annotations

import pytest

from src.config.providers import load_provider_bundle
from src.providers import MockShotProvider
from src.providers.picsum_shot_provider import PicsumShotProvider


def test_load_provider_bundle_local_uses_mock_vertical() -> None:
    bundle = load_provider_bundle("local")

    assert bundle.environment == "local"
    assert bundle.vertical == "local_mock_full"
    assert isinstance(bundle.shot.primary, MockShotProvider)
    assert bundle.story.fallback_policy.get("enabled") is True


def test_load_provider_bundle_demo_uses_single_demo_vertical() -> None:
    bundle = load_provider_bundle("demo")

    assert bundle.environment == "demo"
    assert bundle.vertical == "demo_narration_mock_plus_picsum_shots"
    assert isinstance(bundle.shot.primary, PicsumShotProvider)
    assert bundle.success_criteria.get("expected_shot_count") == 3


def test_load_provider_bundle_raises_when_env_missing() -> None:
    with pytest.raises(FileNotFoundError):
        load_provider_bundle("unknown_env")
