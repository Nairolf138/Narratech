"""Tests du provider de shots asynchrone multi-adaptateurs."""

from __future__ import annotations

import pytest

from src.providers import AsyncShotProvider, ProviderRequest, ProviderTimeout


def test_async_shot_provider_maps_shots_manifest_to_prompts_and_metadata() -> None:
    provider = AsyncShotProvider()
    provider.configure(
        {
            "backend": "kling",
            "adapter_config": {
                "polls_before_completed": 2,
                "fps": 30,
                "width": 1920,
                "height": 1080,
                "codec": "h265",
                "base_uri": "https://cdn.example.com/renders",
                "base_path": "/tmp/renders",
            },
        }
    )

    response = provider.generate_shots(
        ProviderRequest(
            request_id="req_async_1",
            payload={
                "shots_manifest": {
                    "shots": [
                        {
                            "id": "shot_001",
                            "description": "Plan large du port",
                            "duration_sec": 4.0,
                        }
                    ]
                },
                "asset_refs": [{"id": "asset_char_001"}, {"id": "asset_env_001"}],
            },
            timeout_sec=10.0,
        )
    )

    clips = response.data["clips"]
    assert len(clips) == 1
    clip = clips[0]
    assert clip["shot_id"] == "shot_001"
    assert "Plan large du port" in clip["prompt"]
    assert clip["clip_uri"].startswith("https://cdn.example.com/renders")
    assert clip["local_path"].startswith("/tmp/renders")
    assert clip["technical_metadata"]["fps"] == 30
    assert clip["technical_metadata"]["codec"] == "h265"
    assert clip["technical_metadata"]["provider_name"] == "kling"
    assert clip["asset_dependencies"] == ["asset_char_001", "asset_env_001"]


def test_async_shot_provider_timeout_when_polling_never_completes() -> None:
    provider = AsyncShotProvider()
    provider.configure(
        {
            "backend": "runway",
            "max_poll_attempts": 2,
            "poll_interval_sec": 0.0,
            "adapter_config": {
                "polls_before_completed": 20,
            },
        }
    )

    with pytest.raises(ProviderTimeout):
        provider.generate_shots(
            ProviderRequest(
                request_id="req_async_timeout",
                payload={
                    "output": {
                        "shots": [
                            {
                                "id": "shot_999",
                                "description": "Shot impossible",
                                "duration_sec": 3.0,
                            }
                        ]
                    }
                },
            )
        )


def test_shot_generator_persists_clip_locations_and_technical_metadata(isolated_workdir) -> None:
    from src.generation.shot_generator import generate

    scene_doc = {
        "request_id": "req_async_manifest",
        "output": {
            "shots": [
                {"id": "shot_010", "description": "Vue drone", "duration_sec": 5.0},
            ]
        },
    }

    provider = AsyncShotProvider()
    provider.configure({"backend": "local"})

    clips = generate(scene_doc, provider=provider, asset_refs=[{"id": "asset_1"}])
    assert len(clips) == 1
    clip = clips[0]
    assert clip["clip_uri"] is not None
    assert clip["local_path"] is not None
    assert isinstance(clip["technical_metadata"], dict)
    assert clip["technical_metadata"]["provider_name"] == "local"
