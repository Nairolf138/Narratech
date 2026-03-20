"""Assemblage post-production des clips narratifs."""

from __future__ import annotations

from pathlib import Path

from src.core.io_utils import write_json_utf8

FINAL_FILE_NAME = "final_video.mp4"
ASSEMBLY_MANIFEST_NAME = "assembly_manifest.json"


def _shot_index(clip: dict, fallback_index: int) -> int:
    """Retourne l'index narratif d'un clip, avec fallback stable."""
    for key in ("shot_index", "order", "index", "shot_order"):
        raw_value = clip.get(key)
        if raw_value is None:
            continue
        try:
            return int(raw_value)
        except (TypeError, ValueError):
            continue
    return fallback_index


def _duration(clip: dict) -> float:
    """Retourne une durée float positive, ou 0.0 si invalide."""
    for key in ("duration", "duration_sec"):
        raw_value = clip.get(key)
        if raw_value is None:
            continue
        try:
            parsed = float(raw_value)
        except (TypeError, ValueError):
            continue
        return parsed if parsed >= 0 else 0.0
    return 0.0


def _resolve_track(audio_artifacts: list[dict], kind: str) -> dict:
    """Retourne la première piste audio pour un `kind`, ou un placeholder désactivé."""
    for artifact in audio_artifacts:
        if str(artifact.get("kind") or "") == kind:
            return artifact
    return {"kind": kind, "enabled": False, "path": ""}


def _build_mix_plan(voiceover_track: dict, ambience_track: dict, total_duration: float) -> dict:
    """Construit un plan de mixage simple (ducking + fades)."""
    voiceover_enabled = bool(voiceover_track.get("enabled"))
    ambience_enabled = bool(ambience_track.get("enabled"))

    ambience_gain_db = -16.0 if ambience_enabled else -120.0
    ducked_gain_db = ambience_gain_db - 8.0 if (voiceover_enabled and ambience_enabled) else ambience_gain_db

    fade_window = round(min(1.0, total_duration / 4), 3) if total_duration > 0 else 0.0

    return {
        "voiceover": {
            "enabled": voiceover_enabled,
            "gain_db": -2.0 if voiceover_enabled else -120.0,
            "fade_in_sec": 0.2 if voiceover_enabled else 0.0,
            "fade_out_sec": fade_window if voiceover_enabled else 0.0,
            "path": str(voiceover_track.get("path") or ""),
        },
        "ambience": {
            "enabled": ambience_enabled,
            "base_gain_db": ambience_gain_db,
            "ducking": {
                "enabled": voiceover_enabled and ambience_enabled,
                "trigger": "voiceover_presence",
                "gain_db_when_voiceover": ducked_gain_db,
            },
            "fade_in_sec": 0.8 if ambience_enabled else 0.0,
            "fade_out_sec": fade_window if ambience_enabled else 0.0,
            "path": str(ambience_track.get("path") or ""),
        },
    }


def assemble(clips: list[dict], output_dir: str, audio_artifacts: list[dict] | None = None) -> str:
    """Assemble clips + audio, exporte un MP4 placeholder et un manifeste d'assemblage."""
    if not isinstance(clips, list):
        raise TypeError("clips doit être une liste de dictionnaires")

    for clip in clips:
        if not isinstance(clip, dict):
            raise TypeError("chaque clip doit être un dictionnaire")

    final_dir = Path(output_dir)
    final_dir.mkdir(parents=True, exist_ok=True)

    if audio_artifacts is None:
        audio_artifacts = []

    if not isinstance(audio_artifacts, list):
        raise TypeError("audio_artifacts doit être une liste de dictionnaires")

    for artifact in audio_artifacts:
        if not isinstance(artifact, dict):
            raise TypeError("chaque artefact audio doit être un dictionnaire")

    indexed_clips = [(_shot_index(clip, fallback_index=i), clip) for i, clip in enumerate(clips, start=1)]
    sorted_clips = [clip for _, clip in sorted(indexed_clips, key=lambda item: item[0])]

    timeline: list[dict] = []
    total_duration = 0.0

    for fallback_index, clip in enumerate(sorted_clips, start=1):
        shot_index = _shot_index(clip, fallback_index=fallback_index)
        shot_id = str(clip.get("shot_id") or f"shot_{shot_index:03d}")
        duration = _duration(clip)
        start_sec = total_duration
        end_sec = total_duration + duration
        total_duration = end_sec
        timeline.append(
            {
                "shot_index": shot_index,
                "shot_id": shot_id,
                "source_path": str(clip.get("path") or ""),
                "start_sec": round(start_sec, 3),
                "end_sec": round(end_sec, 3),
                "duration_sec": round(duration, 3),
            }
        )

    voiceover_track = _resolve_track(audio_artifacts, "voiceover")
    ambience_track = _resolve_track(audio_artifacts, "ambience")
    mix_plan = _build_mix_plan(voiceover_track, ambience_track, total_duration=total_duration)

    assembly_manifest = {
        "format": "narratech.assembly.v1",
        "video": {
            "concat_strategy": "narrative_order",
            "clips": timeline,
            "total_duration_sec": round(total_duration, 3),
        },
        "audio": {
            "tracks": [
                {
                    "kind": "voiceover",
                    "enabled": bool(voiceover_track.get("enabled")),
                    "path": str(voiceover_track.get("path") or ""),
                },
                {
                    "kind": "ambience",
                    "enabled": bool(ambience_track.get("enabled")),
                    "path": str(ambience_track.get("path") or ""),
                },
            ],
            "mix": mix_plan,
        },
        "export": {
            "container": "mp4",
            "video_codec": "placeholder_h264",
            "audio_codec": "placeholder_aac",
            "path": (final_dir / FINAL_FILE_NAME).as_posix(),
        },
    }

    write_json_utf8(final_dir / ASSEMBLY_MANIFEST_NAME, assembly_manifest)

    final_path = final_dir / FINAL_FILE_NAME
    final_path.write_bytes(
        (
            b"NARRATECH_POSTPROD_PLACEHOLDER\n"
            + f"clips={len(timeline)}\n".encode("utf-8")
            + f"duration={total_duration:.3f}\n".encode("utf-8")
            + f"voiceover={str(bool(voiceover_track.get('enabled'))).lower()}\n".encode("utf-8")
            + f"ambience={str(bool(ambience_track.get('enabled'))).lower()}\n".encode("utf-8")
        )
    )
    return final_path.as_posix()
