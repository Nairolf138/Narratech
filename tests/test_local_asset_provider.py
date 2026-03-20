"""Tests du provider d'assets concrets et déterministes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.generation.asset_generator import generate as generate_assets
from src.providers import LocalAssetProvider, ProviderInvalidResponse, ProviderRequest


def _enriched_scene() -> dict:
    return {
        "request_id": "req_asset_local_1",
        "output": {
            "synopsis": "Alex infiltre un laboratoire discret.",
            "characters": [
                {
                    "id": "char_1",
                    "name": "Alex",
                    "role": "protagonist",
                }
            ],
            "scenes": [{"id": "scene_1", "summary": "Laboratoire sombre avec néons chauds."}],
            "shots": [
                {
                    "id": "shot_001",
                    "scene_id": "scene_1",
                    "description": "Alex observe les consoles.",
                    "consistency_packet": {
                        "characters": [
                            {
                                "character_id": "char_1",
                                "display_name": "Alex",
                                "core_traits": ["protagonist", "analytique"],
                                "signature_clothing": ["manteau beige", "écharpe rouge"],
                                "color_palette": ["#D9C2A7", "#A63D40", "#2F3E46"],
                            }
                        ],
                        "visual_continuity": {
                            "mood_tone": "tension contenue",
                            "lighting_profile": "golden hour soft",
                            "camera_style": "cinematic dolly",
                        },
                    },
                }
            ],
        },
    }


def test_local_asset_provider_builds_prompt_and_persists_images(isolated_workdir: Path) -> None:
    provider = LocalAssetProvider()
    scene = _enriched_scene()

    response = provider.generate_assets(
        ProviderRequest(
            request_id=scene["request_id"],
            payload={
                "request_id": scene["request_id"],
                "output": scene["output"],
                "seed": 900,
                "generation_params": {"steps": 22, "cfg_scale": 6.5},
            },
        )
    )

    assets = response.data["assets"]
    assert assets
    character_asset = assets[0]

    image_uri = character_asset["uri"]
    metadata_uri = character_asset["metadata_uri"]
    assert isinstance(image_uri, str) and image_uri.startswith("local://")
    assert isinstance(metadata_uri, str) and metadata_uri.startswith("local://")

    image_path = Path(image_uri.replace("local://", "", 1))
    metadata_path = Path(metadata_uri.replace("local://", "", 1))
    assert image_path.exists()
    assert metadata_path.exists()

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["seed"] == 901
    assert metadata["generation_params"]["steps"] == 22
    assert "Signature clothing" in metadata["prompt"]
    assert "Mood:" in metadata["prompt"]


def test_local_asset_provider_validation_rejects_missing_expected_traits() -> None:
    provider = LocalAssetProvider()

    with pytest.raises(ProviderInvalidResponse, match="trait attendu absent"):
        provider._validate_prompt(prompt="Character concept art for Alex.", character={"name": "Alex", "role": "protagonist"})


def test_asset_generator_preserves_provider_uri_and_generation_metadata(isolated_workdir: Path) -> None:
    scene = _enriched_scene()
    provider = LocalAssetProvider()

    asset_refs = generate_assets(scene, provider=provider)

    assert asset_refs
    first = asset_refs[0]
    assert isinstance(first.get("uri"), str) and str(first["uri"]).endswith(".svg")
    assert first.get("metadata_uri")
    assert isinstance(first.get("generation_params"), dict)
    assert "seed" in first

    manifest_path = isolated_workdir / "assets" / scene["request_id"] / "assets_manifest.json"
    assert manifest_path.exists()
