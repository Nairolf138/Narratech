"""Génération de placeholders de clips pour les plans (shots)."""

from __future__ import annotations

import re
from pathlib import Path


SHOTS_ROOT = Path("outputs/shots")


def _slugify(value: str) -> str:
    """Convertit un texte en slug stable pour nom de fichier."""
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower())
    return cleaned.strip("_") or "shot"


def _safe_duration(raw_duration: object) -> float:
    """Retourne une durée float positive, ou 0.0 si invalide."""
    try:
        duration = float(raw_duration)
    except (TypeError, ValueError):
        return 0.0
    return duration if duration >= 0 else 0.0


def generate(scene_doc: dict) -> list[dict]:
    """Écrit un fichier placeholder par shot et retourne les clips minimaux.

    Chaque fichier inclut:
    - shot_id
    - order
    - description enrichie
    - durée

    Retourne une liste de clips avec: path, shot_id, duration.
    """
    if not isinstance(scene_doc, dict):
        raise TypeError("scene_doc doit être un dictionnaire")

    output = scene_doc.get("output")
    if not isinstance(output, dict):
        raise ValueError("scene_doc.output doit être un objet")

    shots = output.get("shots")
    if not isinstance(shots, list):
        raise ValueError("scene_doc.output.shots doit être une liste")

    SHOTS_ROOT.mkdir(parents=True, exist_ok=True)

    clips: list[dict] = []
    for order, shot in enumerate(shots, start=1):
        if not isinstance(shot, dict):
            continue

        shot_id = str(shot.get("id") or f"shot_{order:03d}")
        duration = _safe_duration(shot.get("duration_sec"))

        base_description = str(shot.get("description") or "")
        enriched_description = str(shot.get("enriched_prompt") or base_description)
        slug_source = base_description or enriched_description or shot_id
        slug = _slugify(slug_source)[:60]

        file_name = f"shot_{order:03d}_{slug}.txt"
        file_path = SHOTS_ROOT / file_name

        content = (
            f"shot_id: {shot_id}\n"
            f"order: {order}\n"
            f"description_enriched: {enriched_description}\n"
            f"duration_sec: {duration}\n"
        )
        file_path.write_text(content, encoding="utf-8")

        clips.append(
            {
                "path": file_path.as_posix(),
                "shot_id": shot_id,
                "duration": duration,
            }
        )

    output["clips"] = clips
    return clips
