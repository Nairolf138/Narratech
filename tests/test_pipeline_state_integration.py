"""Tests d'intégration du modèle d'état de pipeline."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.core.story_engine import StoryEngine
from src.main import _run_pipeline


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_pipeline_state_tracks_nominal_transitions(isolated_workdir: Path) -> None:
    exit_code = _run_pipeline([])

    assert exit_code == 0

    state = _read_json(isolated_workdir / "outputs" / "pipeline_state.json")
    transitions = state["transitions"]
    to_stages = [entry["to_stage"] for entry in transitions]

    assert state["current_stage"] == "completed"
    assert state["failed_stage"] is None
    assert to_stages == [
        "prompt_loaded",
        "story_generated",
        "narrative_validated",
        "consistency_enriched",
        "assets_generated",
        "shots_generated",
        "final_assembled",
        "completed",
    ]
    assert state["errors"] == []

    request_id = state["request_id"]
    assert request_id.startswith("req_")
    assert all(item["request_id"] == request_id for item in transitions)
    assert all(item["timestamp"] for item in transitions)
    assert all(item["reason"] for item in transitions)

    manifest = _read_json(isolated_workdir / "outputs" / "manifest.json")
    scene = _read_json(isolated_workdir / "outputs" / "scene.json")
    shots_manifest = _read_json(isolated_workdir / "outputs" / "shots" / "shots_manifest.json")
    asset_manifest = _read_json(isolated_workdir / "assets" / request_id / "assets_manifest.json")

    assert manifest["request_id"] == request_id
    assert scene["request_id"] == request_id
    assert shots_manifest["request_id"] == request_id
    assert asset_manifest["request_id"] == request_id


def test_pipeline_state_tracks_failure_transition(
    isolated_workdir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    narrative = StoryEngine().generate("Prompt de test.")

    monkeypatch.setattr("src.main.load_prompt", lambda _args: "prompt")
    monkeypatch.setattr("src.main.StoryEngine", lambda *args, **kwargs: type("Stub", (), {"generate": lambda _self, _p, request_id=None: narrative})())
    monkeypatch.setattr(
        "src.main.enrich",
        lambda _doc: {
            "enriched_doc": narrative,
            "consistency_report": [
                {
                    "rule_id": "character_ids_consistency",
                    "severity": "error",
                    "location": "output.characters",
                    "message": "Violation bloquante",
                    "suggested_fix": "Corriger",
                }
            ],
        },
    )

    exit_code = _run_pipeline([])
    assert exit_code == 1

    state = _read_json(isolated_workdir / "outputs" / "pipeline_state.json")
    transitions = state["transitions"]
    assert state["current_stage"] == "failed"
    assert state["failed_stage"] == "consistency_enriched"
    assert state["errors"]
    assert transitions[-1]["to_stage"] == "failed"
    assert "Violations bloquantes" in transitions[-1]["reason"]
