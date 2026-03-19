"""Assemblage narratif de clips en sortie placeholder."""

from __future__ import annotations

from pathlib import Path


FINAL_FILE_NAME = "final_video.txt"


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


def assemble(clips: list[dict], output_dir: str, audio_artifacts: list[dict] | None = None) -> str:
    """Assemble les clips triés par index narratif et écrit un fichier final.

    Le fichier produit est un placeholder textuel de l'assemblage vidéo.
    Retourne le chemin du fichier final pour logging terminal.
    """
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

    indexed_clips = [
        (_shot_index(clip, fallback_index=i), clip)
        for i, clip in enumerate(clips, start=1)
    ]
    sorted_clips = [clip for _, clip in sorted(indexed_clips, key=lambda item: item[0])]

    shot_lines: list[str] = []
    audio_lines: list[str] = []
    total_duration = 0.0

    for fallback_index, clip in enumerate(sorted_clips, start=1):
        shot_index = _shot_index(clip, fallback_index=fallback_index)
        shot_id = str(clip.get("shot_id") or f"shot_{shot_index:03d}")
        duration = _duration(clip)
        total_duration += duration
        shot_lines.append(f"- shot_index: {shot_index}, shot_id: {shot_id}, duration_sec: {duration:.2f}")

    for artifact in audio_artifacts:
        kind = str(artifact.get("kind") or "audio")
        enabled = bool(artifact.get("enabled"))
        path = str(artifact.get("path") or "")
        audio_lines.append(f"- kind: {kind}, enabled: {str(enabled).lower()}, path: {path}")

    content = "\n".join(
        [
            "placeholder assembled output",
            "============================",
            "",
            "shots_order:",
            *shot_lines,
            "",
            f"total_duration_sec: {total_duration:.2f}",
            "",
            "audio_tracks:",
            *audio_lines,
        ]
    )

    final_path = final_dir / FINAL_FILE_NAME
    final_path.write_text(content + "\n", encoding="utf-8")
    return final_path.as_posix()
