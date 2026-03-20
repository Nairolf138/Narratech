"""Tests du comportement de blocage du pipeline sur rapport de cohérence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.main import _run_pipeline
from src.core.story_engine import StoryEngine


def _valid_narrative() -> dict:
    return StoryEngine().generate("Prompt de test pipeline.")


def test_pipeline_stops_on_blocking_consistency_violation(
    isolated_workdir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    narrative = _valid_narrative()

    monkeypatch.setattr("src.main.load_prompt", lambda _args: "prompt")
    monkeypatch.setattr(
        "src.main.StoryEngine",
        lambda *args, **kwargs: type("Stub", (), {"generate": lambda _self, _p, request_id=None: narrative})(),
    )
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

    def _should_not_be_called(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Étape aval appelée malgré une violation bloquante")

    monkeypatch.setattr("src.main.generate_assets", _should_not_be_called)
    monkeypatch.setattr("src.main.generate_shots", _should_not_be_called)
    monkeypatch.setattr("src.main.assemble_video", _should_not_be_called)

    exit_code = _run_pipeline([])

    assert exit_code == 1
    report_path = isolated_workdir / "outputs" / "consistency_report.json"
    assert report_path.exists()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report[0]["severity"] == "error"


def test_pipeline_continues_on_non_blocking_consistency_issues(
    isolated_workdir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    narrative = _valid_narrative()

    monkeypatch.setattr("src.main.load_prompt", lambda _args: "prompt")
    monkeypatch.setattr(
        "src.main.StoryEngine",
        lambda *args, **kwargs: type("Stub", (), {"generate": lambda _self, _p, request_id=None: narrative})(),
    )
    monkeypatch.setattr(
        "src.main.enrich",
        lambda _doc: {
            "enriched_doc": narrative,
            "consistency_report": [
                {
                    "rule_id": "scene_shot_order",
                    "severity": "warning",
                    "location": "output.shots",
                    "message": "Avertissement non bloquant",
                    "suggested_fix": "Réordonner",
                }
            ],
        },
    )

    exit_code = _run_pipeline([])

    assert exit_code == 0
    assert (isolated_workdir / "outputs" / "consistency_report.json").exists()
    assert (isolated_workdir / "outputs" / "final" / "final_video.mp4").exists()


def test_pipeline_stops_on_safety_pre_generation_block(
    isolated_workdir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (isolated_workdir / "config").mkdir(parents=True, exist_ok=True)
    (isolated_workdir / "config" / "safety_blacklist.json").write_text(
        json.dumps({"topics": ["interdit"]}, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr("src.main.load_prompt", lambda _args: "Un prompt interdit.")

    exit_code = _run_pipeline([])

    assert exit_code == 1
    audit_path = isolated_workdir / "outputs" / "safety_audit.json"
    assert audit_path.exists()
    events = json.loads(audit_path.read_text(encoding="utf-8"))
    assert events[-1]["phase"] == "pre_generation_prompt"


def test_pipeline_stops_on_safety_post_generation_block(
    isolated_workdir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    narrative = _valid_narrative()
    output = narrative.get("output")
    assert isinstance(output, dict)
    output["synopsis"] = "Synopsis avec sujet interdit."

    (isolated_workdir / "config").mkdir(parents=True, exist_ok=True)
    (isolated_workdir / "config" / "safety_blacklist.json").write_text(
        json.dumps({"topics": ["interdit"]}, ensure_ascii=False),
        encoding="utf-8",
    )

    monkeypatch.setattr("src.main.load_prompt", lambda _args: "prompt normal")
    monkeypatch.setattr(
        "src.main.StoryEngine",
        lambda *args, **kwargs: type("Stub", (), {"generate": lambda _self, _p, request_id=None: narrative})(),
    )

    exit_code = _run_pipeline([])

    assert exit_code == 1
    audit_path = isolated_workdir / "outputs" / "safety_audit.json"
    assert audit_path.exists()
    events = json.loads(audit_path.read_text(encoding="utf-8"))
    assert events[-1]["phase"] == "post_generation_output"
