"""Smoke test du pipeline mock Narratech, sans dépendance externe."""

from __future__ import annotations

import socket
import time
from pathlib import Path

import pytest

from src.main import ensure_dirs
from src.assembly.audio_engine import build_from_audio_plan
from src.assembly.video_assembler import assemble as assemble_video
from src.core.consistency_engine import enrich
from src.core.story_engine import StoryEngine
from src.generation.asset_generator import generate as generate_assets
from src.generation.shot_generator import generate as generate_shots


@pytest.mark.smoke
def test_smoke_pipeline_mock_e2e(
    isolated_workdir: Path,
    minimal_prompt: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Valide un flux narratif complet avec la config minimale locale."""

    def _block_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Unexpected network call in smoke pipeline test")

    monkeypatch.setattr(socket, "create_connection", _block_network)
    monkeypatch.setattr(socket.socket, "connect", _block_network)

    start = time.perf_counter()

    ensure_dirs()
    narrative = StoryEngine().generate(minimal_prompt)
    consistency_result = enrich(narrative)
    enriched_narrative = consistency_result["enriched_doc"]
    asset_refs = generate_assets(enriched_narrative)
    clips = generate_shots(enriched_narrative, asset_refs=asset_refs)
    audio_artifacts = build_from_audio_plan(enriched_narrative)
    final_video_path = assemble_video(clips, "outputs/final", audio_artifacts=audio_artifacts)

    elapsed = time.perf_counter() - start

    assert elapsed < 5.0

    assert isinstance(narrative, dict)
    assert narrative.get("output")
    assert isinstance(narrative["output"].get("shots"), list)
    assert narrative["output"]["shots"]

    assert isinstance(asset_refs, list)
    assert asset_refs
    assert isinstance(clips, list)
    assert clips
    assert all(clip.get("asset_dependencies") for clip in clips)
    assert isinstance(audio_artifacts, list)
    assert len(audio_artifacts) == 2

    final_path = Path(final_video_path)
    assert final_path.exists()
    assert final_path.read_bytes()

    assembly_manifest = isolated_workdir / "outputs" / "final" / "assembly_manifest.json"
    assert assembly_manifest.exists()

    assert (isolated_workdir / "outputs" / "scene.json").exists()
    assert (isolated_workdir / "outputs" / "scene_enriched.json").exists()
    assert (isolated_workdir / "outputs" / "shots" / "shots_manifest.json").exists()
    assert (isolated_workdir / "outputs" / "audio" / "audio_manifest.json").exists()
