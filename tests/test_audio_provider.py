"""Tests du provider audio et de son intégration minimale."""

from __future__ import annotations

import json
from pathlib import Path

from src.assembly.audio_engine import build_from_audio_plan
from src.providers import MockAudioProvider, ProviderRequest


def test_mock_audio_provider_generates_metadata_and_timestamps(isolated_workdir: Path) -> None:
    provider = MockAudioProvider()

    response = provider.synthesize_audio(
        ProviderRequest(
            request_id="req_audio_1",
            payload={
                "request_id": "req_audio_1",
                "mode": "voiceover",
                "narrative_text": "Texte de narration",
                "language": "fr",
                "style": "documentary",
                "shots": [
                    {"id": "shot_001", "duration_sec": 2.5},
                    {"id": "shot_002", "duration_sec": 1.5},
                ],
            },
        )
    )

    assert response.data["audio_file"].endswith("outputs/audio/voiceover.txt")
    assert response.data["metadata"]["duration_sec"] == 4.0
    assert response.data["metadata"]["format"] == "txt"
    assert response.data["metadata"]["provider"] == "mock_audio_provider"
    assert response.data["timestamps"] == [
        {"shot_id": "shot_001", "start_sec": 0.0, "end_sec": 2.5},
        {"shot_id": "shot_002", "start_sec": 2.5, "end_sec": 4.0},
    ]


def test_build_from_audio_plan_exposes_provider_metadata_and_timestamps(isolated_workdir: Path) -> None:
    scene_doc = {
        "request_id": "req_audio_2",
        "input": {"language": "fr", "style": "cinematic"},
        "output": {
            "shots": [
                {"id": "shot_001", "duration_sec": 3.0},
                {"id": "shot_002", "duration_sec": 2.0},
            ],
            "audio_plan": {
                "voiceover": {"enabled": True, "language": "fr", "script": "Voix off"},
                "ambience": {"enabled": True, "description": "Ambiance légère"},
            },
        },
    }

    artifacts = build_from_audio_plan(scene_doc)

    assert len(artifacts) == 2
    assert artifacts[0]["kind"] == "voiceover"
    assert artifacts[1]["kind"] == "ambience"
    assert artifacts[0]["metadata"]["duration_sec"] == 5.0
    assert artifacts[0]["timestamps"][0]["start_sec"] == 0.0
    assert artifacts[0]["timestamps"][1]["end_sec"] == 5.0

    manifest_path = isolated_workdir / "outputs" / "audio" / "audio_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["count"] == 2
    assert "timestamps" in manifest["artifacts"][0]
