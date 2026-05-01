"""Moteur de scoring composite de qualité média."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.core.io_utils import write_json_utf8

MEDIA_QUALITY_REPORT = "media_quality_report.json"


@dataclass(frozen=True)
class MediaQualityWeights:
    visual_continuity: float = 0.30
    style_stability: float = 0.25
    narrative_pacing: float = 0.25
    voice_intelligibility: float = 0.20


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _duration(clip: dict) -> float:
    for key in ("duration", "duration_sec"):
        raw = clip.get(key)
        if raw is None:
            continue
        try:
            parsed = float(raw)
        except (TypeError, ValueError):
            continue
        if parsed >= 0:
            return parsed
    return 0.0


def _visual_continuity_score(consistency_report: list[dict]) -> tuple[float, dict]:
    visual_issues = [
        issue
        for issue in consistency_report
        if str(issue.get("rule_id") or "") in {"visual_constraints_presence", "period_anachronism"}
    ]
    severity_penalty = 0.0
    for issue in visual_issues:
        severity = str(issue.get("severity") or "warning")
        severity_penalty += 0.35 if severity == "error" else 0.15
    score = _clamp(1.0 - severity_penalty)
    return score, {"issue_count": len(visual_issues), "penalty": round(severity_penalty, 3)}


def _style_stability_score(clips: list[dict]) -> tuple[float, dict]:
    style_values = [str(clip.get("style") or clip.get("visual_style") or "").strip() for clip in clips]
    style_values = [item for item in style_values if item]
    if not style_values:
        return 0.75, {"reason": "styles_absents_default"}

    dominant = max(set(style_values), key=style_values.count)
    aligned = sum(1 for value in style_values if value == dominant)
    score = _clamp(aligned / len(style_values))
    return score, {"dominant_style": dominant, "aligned": aligned, "total": len(style_values)}


def _narrative_pacing_score(clips: list[dict]) -> tuple[float, dict]:
    durations = [_duration(clip) for clip in clips]
    durations = [value for value in durations if value > 0]
    if len(durations) <= 1:
        return 0.8, {"reason": "insufficient_duration_samples"}

    average = sum(durations) / len(durations)
    variance = sum((value - average) ** 2 for value in durations) / len(durations)
    normalized_variance = variance / (average**2 + 1e-6)
    score = _clamp(1.0 - min(1.0, normalized_variance))
    return score, {"avg_duration_sec": round(average, 3), "normalized_variance": round(normalized_variance, 3)}


def _voice_intelligibility_score(audio_artifacts: list[dict]) -> tuple[float, dict]:
    voiceover = next((item for item in audio_artifacts if str(item.get("kind") or "") == "voiceover"), None)
    if voiceover is None:
        return 0.0, {"reason": "missing_voiceover"}
    if not bool(voiceover.get("enabled")):
        return 0.2, {"reason": "voiceover_disabled"}

    sample_rate = int(voiceover.get("sample_rate_hz") or 24000)
    snr_estimate = float(voiceover.get("snr_db") or 18.0)
    sample_rate_score = 1.0 if sample_rate >= 22050 else 0.7
    snr_score = _clamp((snr_estimate - 8.0) / 20.0)
    score = _clamp((sample_rate_score * 0.4) + (snr_score * 0.6))
    return score, {"sample_rate_hz": sample_rate, "snr_db": snr_estimate}


def build_media_quality_report(
    *,
    request_id: str,
    clips: list[dict],
    consistency_report: list[dict],
    audio_artifacts: list[dict],
    output_dir: str = "outputs",
    weights: MediaQualityWeights = MediaQualityWeights(),
) -> dict:
    """Calcule et exporte un score composite de qualité média."""
    visual_score, visual_details = _visual_continuity_score(consistency_report)
    style_score, style_details = _style_stability_score(clips)
    pacing_score, pacing_details = _narrative_pacing_score(clips)
    voice_score, voice_details = _voice_intelligibility_score(audio_artifacts)

    composite = _clamp(
        (visual_score * weights.visual_continuity)
        + (style_score * weights.style_stability)
        + (pacing_score * weights.narrative_pacing)
        + (voice_score * weights.voice_intelligibility)
    )

    payload = {
        "format": "narratech.media_quality.v1",
        "request_id": request_id,
        "threshold_min_acceptance": 0.75,
        "accepted": composite >= 0.75,
        "score_composite": round(composite, 4),
        "subscores": {
            "continuite_visuelle": {"score": round(visual_score, 4), "details": visual_details},
            "stabilite_style": {"score": round(style_score, 4), "details": style_details},
            "rythme_narratif": {"score": round(pacing_score, 4), "details": pacing_details},
            "intelligibilite_voix": {"score": round(voice_score, 4), "details": voice_details},
        },
    }

    target_path = Path(output_dir) / MEDIA_QUALITY_REPORT
    write_json_utf8(target_path, payload)
    return payload
