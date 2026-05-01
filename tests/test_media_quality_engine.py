"""Tests unitaires pour le moteur de qualité média."""

from __future__ import annotations

from src.core.media_quality_engine import build_media_quality_report


def test_media_quality_engine_nominal_case(tmp_path) -> None:
    clips = [
        {"shot_id": "shot_001", "duration_sec": 3.0, "style": "cinematic"},
        {"shot_id": "shot_002", "duration_sec": 3.2, "style": "cinematic"},
        {"shot_id": "shot_003", "duration_sec": 2.8, "style": "cinematic"},
    ]
    report = build_media_quality_report(
        request_id="req_nominal",
        clips=clips,
        consistency_report=[],
        audio_artifacts=[{"kind": "voiceover", "enabled": True, "sample_rate_hz": 24000, "snr_db": 22.0}],
        output_dir=tmp_path.as_posix(),
    )

    assert report["score_composite"] >= 0.75
    assert report["accepted"] is True
    assert (tmp_path / "media_quality_report.json").exists()


def test_media_quality_engine_degraded_case(tmp_path) -> None:
    clips = [
        {"shot_id": "shot_001", "duration_sec": 0.6, "style": "noir"},
        {"shot_id": "shot_002", "duration_sec": 7.2, "style": "cartoon"},
    ]
    consistency_report = [
        {"rule_id": "visual_constraints_presence", "severity": "error"},
        {"rule_id": "period_anachronism", "severity": "error"},
    ]
    report = build_media_quality_report(
        request_id="req_degraded",
        clips=clips,
        consistency_report=consistency_report,
        audio_artifacts=[{"kind": "voiceover", "enabled": False}],
        output_dir=tmp_path.as_posix(),
    )

    assert report["score_composite"] < 0.75
    assert report["accepted"] is False
