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
    assert state["degraded_shots"] == 0
    assert state["degraded_ratio"] == 0.0

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


def test_pipeline_state_done_with_warnings_when_degraded_ratio_under_threshold(
    isolated_workdir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class DegradedOnceShotProvider:
        def __init__(self) -> None:
            self.calls = 0

        def configure(self, config: dict) -> None:  # pragma: no cover - interface compatibility
            _ = config

        def generate(self, request):
            from src.providers import ProviderRateLimit, ProviderResponse

            self.calls += 1
            shots = request.payload.get("output", {}).get("shots", [])
            first_shot_id = shots[0].get("id") if shots and isinstance(shots[0], dict) else "unknown"
            if first_shot_id == "shot_001":
                raise ProviderRateLimit("degraded shot")
            return ProviderResponse(
                data={
                    "clips": [
                        {
                            "shot_id": first_shot_id,
                            "duration": 2.0,
                            "description_enriched": "ok",
                        }
                    ]
                },
                provider_trace={"provider": "stub-shot"},
                latency_ms=1,
                cost_estimate=0.0,
                model_name="stub",
            )

        def healthcheck(self):
            from src.providers import ProviderHealth

            return ProviderHealth(ok=True)

    monkeypatch.setattr("src.main.MockShotProvider", DegradedOnceShotProvider)
    (isolated_workdir / ".narratech_degraded_ratio_threshold").write_text("0.5\n", encoding="utf-8")

    exit_code = _run_pipeline([])
    assert exit_code == 0

    state = _read_json(isolated_workdir / "outputs" / "pipeline_state.json")
    manifest = _read_json(isolated_workdir / "outputs" / "manifest.json")

    assert state["current_stage"] == "done_with_warnings"
    assert 0 < state["degraded_ratio"] <= 0.5
    assert manifest["quality"]["degraded_ratio"] == state["degraded_ratio"]


def test_pipeline_state_fails_when_degraded_ratio_over_threshold(
    isolated_workdir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class AlwaysFailShotProvider:
        def configure(self, config: dict) -> None:  # pragma: no cover - interface compatibility
            _ = config

        def generate(self, request):
            from src.providers import ProviderRateLimit

            _ = request
            raise ProviderRateLimit("provider unavailable")

        def healthcheck(self):
            from src.providers import ProviderHealth

            return ProviderHealth(ok=True)

    monkeypatch.setattr("src.main.MockShotProvider", AlwaysFailShotProvider)
    (isolated_workdir / ".narratech_degraded_ratio_threshold").write_text("0.1\n", encoding="utf-8")

    exit_code = _run_pipeline([])
    assert exit_code == 1

    state = _read_json(isolated_workdir / "outputs" / "pipeline_state.json")
    assert state["current_stage"] == "failed"
    assert state["failed_stage"] == "shots_generated"
    assert state["degraded_ratio"] > 0.1
    assert state["retry_events"]
