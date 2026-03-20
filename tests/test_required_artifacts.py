"""Tests de contrats des artefacts obligatoires du pipeline."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.main import _run_pipeline


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_pipeline_generates_required_manifests(isolated_workdir: Path) -> None:
    exit_code = _run_pipeline([])
    assert exit_code == 0

    manifest_path = isolated_workdir / "outputs" / "manifest.json"
    shots_manifest_path = isolated_workdir / "outputs" / "shots" / "shots_manifest.json"

    assert manifest_path.exists()
    assert shots_manifest_path.exists()

    manifest = _read_json(manifest_path)
    shots_manifest = _read_json(shots_manifest_path)

    assert manifest["shots_manifest_file"] == "outputs/shots/shots_manifest.json"
    assert manifest["request_id"]
    assert shots_manifest["request_id"] == manifest["request_id"]
    assert shots_manifest["count"] > 0
    assert len(shots_manifest["clips"]) == shots_manifest["count"]
    assert len(shots_manifest["asset_dependencies"]) == shots_manifest["count"]


def test_pipeline_generates_audio_outputs(isolated_workdir: Path) -> None:
    exit_code = _run_pipeline([])
    assert exit_code == 0

    audio_manifest_path = isolated_workdir / "outputs" / "audio" / "audio_manifest.json"
    voice_path = isolated_workdir / "outputs" / "audio" / "voiceover.txt"
    ambience_path = isolated_workdir / "outputs" / "audio" / "ambience.txt"
    final_video_path = isolated_workdir / "outputs" / "final" / "final_video.mp4"

    assert audio_manifest_path.exists()
    assert voice_path.exists()
    assert ambience_path.exists()

    audio_manifest = _read_json(audio_manifest_path)
    assert audio_manifest["source_contract"] == "output.audio_plan"
    assert audio_manifest["count"] == 2
    assert len(audio_manifest["artifacts"]) == 2

    final_video_content = final_video_path.read_bytes()
    assert b"NARRATECH_POSTPROD_PLACEHOLDER" in final_video_content

    assembly_manifest_path = isolated_workdir / "outputs" / "final" / "assembly_manifest.json"
    assert assembly_manifest_path.exists()
    assembly_manifest = _read_json(assembly_manifest_path)
    assert assembly_manifest["video"]["concat_strategy"] == "narrative_order"
    assert assembly_manifest["audio"]["mix"]["ambience"]["ducking"]["enabled"] is True


def test_pipeline_fails_if_shots_manifest_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.main import _generate_shots_with_targeted_retries as original_generate_shots

    def _generate_shots_without_manifest(*args, **kwargs):
        result = original_generate_shots(*args, **kwargs)
        (Path("outputs/shots") / "shots_manifest.json").unlink(missing_ok=True)
        return result

    monkeypatch.setattr("src.main._generate_shots_with_targeted_retries", _generate_shots_without_manifest)

    with pytest.raises(RuntimeError, match="Artefact obligatoire manquant"):
        _run_pipeline([])
