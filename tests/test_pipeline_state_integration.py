"""Tests d'intégration du modèle d'état de pipeline."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import src.config.providers as provider_config
from src.config.providers import ProviderBundle, ProviderSlot
from src.core.story_engine import StoryEngine
from src.main import _run_pipeline, _run_resume_cli
from src.providers import MockAssetProvider, MockAudioProvider, MockNarrativeProvider, MockShotProvider
from src.providers import ProviderRateLimit


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
    assert manifest["recommendation_file"] == "outputs/recommendation.json"
    assert (isolated_workdir / "outputs" / "recommendation.json").exists()
    assert manifest["feedback_capture_file"] == "outputs/feedback_capture.json"
    assert manifest["feedback_audit_file"] == "outputs/feedback_audit_preview.json"
    assert (isolated_workdir / "outputs" / "feedback_capture.json").exists()
    assert (isolated_workdir / "outputs" / "feedback_audit_preview.json").exists()


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

    monkeypatch.setitem(provider_config._PROVIDER_REGISTRY, "mock_shot", DegradedOnceShotProvider)
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

    monkeypatch.setitem(provider_config._PROVIDER_REGISTRY, "mock_shot", AlwaysFailShotProvider)
    (isolated_workdir / ".narratech_degraded_ratio_threshold").write_text("0.1\n", encoding="utf-8")

    exit_code = _run_pipeline([])
    assert exit_code == 1

    state = _read_json(isolated_workdir / "outputs" / "pipeline_state.json")
    assert state["current_stage"] == "failed"
    assert state["failed_stage"] == "shots_generated"
    assert state["degraded_ratio"] > 0.1
    assert state["retry_events"]


def test_pipeline_shots_manifest_references_generated_assets(
    isolated_workdir: Path,
) -> None:
    exit_code = _run_pipeline([])
    assert exit_code == 0

    manifest = _read_json(isolated_workdir / "outputs" / "manifest.json")
    shots_manifest = _read_json(isolated_workdir / "outputs" / "shots" / "shots_manifest.json")
    assets_manifest = _read_json(isolated_workdir / "assets" / manifest["request_id"] / "assets_manifest.json")

    expected_asset_ids = [asset["id"] for asset in assets_manifest["assets"]]
    assert expected_asset_ids

    dependencies_by_shot = {
        entry["shot_id"]: entry["asset_ids"] for entry in shots_manifest["asset_dependencies"]
    }
    assert dependencies_by_shot

    for clip in shots_manifest["clips"]:
        shot_id = clip["shot_id"]
        assert clip["asset_dependencies"] == expected_asset_ids
        assert dependencies_by_shot[shot_id] == expected_asset_ids


def test_pipeline_resume_from_assets_stage_is_idempotent(
    isolated_workdir: Path,
) -> None:
    first_exit = _run_pipeline([])
    assert first_exit == 0

    state_path = isolated_workdir / "outputs" / "pipeline_state.json"
    state = _read_json(state_path)
    state["current_stage"] = "assets_generated"
    state["transitions"] = [event for event in state["transitions"] if event["to_stage"] != "completed"]
    state_path.write_text(json.dumps(state), encoding="utf-8")

    shots_manifest_before = _read_json(isolated_workdir / "outputs" / "shots" / "shots_manifest.json")
    assets_manifest_before = _read_json(
        isolated_workdir / "assets" / state["request_id"] / "assets_manifest.json"
    )

    resumed_exit = _run_resume_cli(["--request-id", state["request_id"]])
    assert resumed_exit == 0

    shots_manifest_after = _read_json(isolated_workdir / "outputs" / "shots" / "shots_manifest.json")
    assets_manifest_after = _read_json(
        isolated_workdir / "assets" / state["request_id"] / "assets_manifest.json"
    )
    resumed_state = _read_json(state_path)

    assert assets_manifest_after == assets_manifest_before
    assert shots_manifest_after["count"] == shots_manifest_before["count"]
    assert resumed_state["current_stage"] in {"completed", "done_with_warnings"}


def test_pipeline_applies_feedback_adjustments_to_next_generation(
    isolated_workdir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NARRATECH_SESSION_ID", "session_feedback_flow")
    (isolated_workdir / "outputs").mkdir(parents=True, exist_ok=True)
    (isolated_workdir / "outputs" / "feedback_input.json").write_text(
        json.dumps(
            {
                "global_note": 2,
                "dimensions": {"histoire": 1, "style": 2, "rythme": 1},
                "commentaire": "à clarifier",
            }
        ),
        encoding="utf-8",
    )
    first_exit = _run_pipeline([])
    assert first_exit == 0

    (isolated_workdir / "outputs" / "feedback_input.json").unlink()
    second_exit = _run_pipeline([])
    assert second_exit == 0

    recommendation = _read_json(isolated_workdir / "outputs" / "recommendation.json")
    applied = recommendation["inputs"]["applied_feedback_adjustments"]
    assert applied is not None
    assert applied["story"] == "clarify"
    assert applied["rhythm"] == "slow_down"


def test_pipeline_recovers_from_narrative_failure_with_local_fallback(
    isolated_workdir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingNarrativeProvider:
        def configure(self, config: dict) -> None:  # pragma: no cover - compat
            _ = config

        def generate(self, request):
            _ = request
            raise ProviderRateLimit("quota cloud dépassé")

    provider_bundle = ProviderBundle(
        environment="test",
        vertical="generic",
        story=ProviderSlot(
            primary=FailingNarrativeProvider(),
            fallback=MockNarrativeProvider(),
            fallback_policy={"enabled": True, "trigger_on": ["ProviderRateLimit"]},
        ),
        asset=ProviderSlot(
            primary=MockAssetProvider(),
            fallback=MockAssetProvider(),
            fallback_policy={"enabled": True, "trigger_on": ["ProviderRateLimit"]},
        ),
        shot=ProviderSlot(
            primary=MockShotProvider(),
            fallback=MockShotProvider(),
            fallback_policy={"enabled": True, "trigger_on": ["ProviderRateLimit"]},
        ),
        audio=ProviderSlot(
            primary=MockAudioProvider(),
            fallback=MockAudioProvider(),
            fallback_policy={"enabled": True, "trigger_on": ["ProviderRateLimit"]},
        ),
        success_criteria={},
    )
    monkeypatch.setattr("src.main.load_provider_bundle", lambda: provider_bundle)

    exit_code = _run_pipeline([])
    assert exit_code == 0

    scene = _read_json(isolated_workdir / "outputs" / "scene.json")
    trace = scene.get("provider_trace")
    assert isinstance(trace, list) and trace
    assert trace[-1]["fallback_mode"] is True
    assert trace[-1]["fallback_reason"] == "ProviderRateLimit"


def test_pipeline_handles_temporary_shot_failure_with_retry(
    isolated_workdir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FlakyShotProvider:
        def __init__(self) -> None:
            self.failures_remaining: dict[str, int] = {"shot_001": 1}

        def configure(self, config: dict) -> None:  # pragma: no cover - compat
            _ = config

        def generate(self, request):
            payload = request.payload if isinstance(request.payload, dict) else {}
            shots = payload.get("output", {}).get("shots", [])
            shot = shots[0] if shots and isinstance(shots[0], dict) else {}
            shot_id = str(shot.get("id") or "shot_001")
            if self.failures_remaining.get(shot_id, 0) > 0:
                self.failures_remaining[shot_id] -= 1
                raise ProviderRateLimit(f"temp failure {shot_id}")

            from src.providers import ProviderResponse

            return ProviderResponse(
                data={
                    "clips": [
                        {
                            "shot_id": shot_id,
                            "duration": float(shot.get("duration_sec") or 2.0),
                            "description_enriched": "ok",
                        }
                    ]
                },
                provider_trace={"provider": "flaky_shot"},
                latency_ms=1,
                cost_estimate=0.0,
                model_name="flaky",
            )

        def healthcheck(self):
            from src.providers import ProviderHealth

            return ProviderHealth(ok=True)

    monkeypatch.setitem(provider_config._PROVIDER_REGISTRY, "mock_shot", FlakyShotProvider)

    exit_code = _run_pipeline([])
    assert exit_code == 0

    state = _read_json(isolated_workdir / "outputs" / "pipeline_state.json")
    shots_manifest = _read_json(isolated_workdir / "outputs" / "shots" / "shots_manifest.json")
    assert state["retry_events"]
    assert any(event["scope_type"] == "shot" for event in state["retry_events"])
    assert shots_manifest["quality"]["degraded_shots"] == 0


def test_pipeline_keeps_running_when_audio_fails_in_degraded_mode(
    isolated_workdir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NARRATECH_ALLOW_DEGRADED_AUDIO", "1")
    monkeypatch.setattr(
        "src.main.build_from_audio_plan",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("audio backend indisponible")),
    )

    exit_code = _run_pipeline([])
    assert exit_code == 0

    state = _read_json(isolated_workdir / "outputs" / "pipeline_state.json")
    audio_manifest = _read_json(isolated_workdir / "outputs" / "audio" / "audio_manifest.json")
    manifest = _read_json(isolated_workdir / "outputs" / "manifest.json")

    assert state["current_stage"] == "completed"
    assert any("audio_degraded" in error["reason"] for error in state["errors"])
    assert audio_manifest["degraded_mode"] is True
    assert audio_manifest["count"] == 0
    assert manifest["audio_files"] == []
    assert (isolated_workdir / "outputs" / "final" / "final_video.mp4").exists()


def test_pipeline_failure_keeps_partial_artifacts_and_consistent_logs(
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
    assert state["current_stage"] == "failed"
    assert state["failed_stage"] == "consistency_enriched"
    assert state["transitions"][-1]["to_stage"] == "failed"
    assert (isolated_workdir / "outputs" / "recommendation.json").exists()
    assert (isolated_workdir / "outputs" / "consistency_report.json").exists()
    assert not (isolated_workdir / "outputs" / "manifest.json").exists()
