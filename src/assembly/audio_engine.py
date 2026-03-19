"""Moteur audio placeholder basé sur output.audio_plan."""

from __future__ import annotations

from pathlib import Path

from src.core.io_utils import write_json_utf8

AUDIO_ROOT = Path("outputs/audio")


class AudioContractError(ValueError):
    """Erreur levée quand le contrat output.audio_plan est invalide."""


def _as_bool(value: object) -> bool:
    return bool(value) if isinstance(value, bool) else False


def build_from_audio_plan(scene_doc: dict) -> list[dict]:
    """Génère des artefacts audio mock (voix off + ambiance) à partir du narratif."""
    if not isinstance(scene_doc, dict):
        raise TypeError("scene_doc doit être un dictionnaire")

    output = scene_doc.get("output")
    if not isinstance(output, dict):
        raise AudioContractError("scene_doc.output doit être un objet")

    audio_plan = output.get("audio_plan")
    if not isinstance(audio_plan, dict):
        raise AudioContractError("scene_doc.output.audio_plan doit être un objet")

    voiceover = audio_plan.get("voiceover")
    ambience = audio_plan.get("ambience")

    if not isinstance(voiceover, dict):
        raise AudioContractError("audio_plan.voiceover doit être un objet")
    if not isinstance(ambience, dict):
        raise AudioContractError("audio_plan.ambience doit être un objet")

    request_id = str(scene_doc.get("request_id", "request_unknown"))
    AUDIO_ROOT.mkdir(parents=True, exist_ok=True)

    artifacts: list[dict] = []

    voice_enabled = _as_bool(voiceover.get("enabled"))
    voice_language = str(voiceover.get("language") or scene_doc.get("input", {}).get("language") or "und")
    voice_script = str(voiceover.get("script") or "Placeholder voix off.")
    voice_text_path = AUDIO_ROOT / "voiceover.txt"
    voice_text_path.write_text(
        (
            "type: voiceover\n"
            f"request_id: {request_id}\n"
            f"enabled: {str(voice_enabled).lower()}\n"
            f"language: {voice_language}\n"
            f"script: {voice_script}\n"
        ),
        encoding="utf-8",
    )
    artifacts.append(
        {
            "kind": "voiceover",
            "enabled": voice_enabled,
            "language": voice_language,
            "path": voice_text_path.as_posix(),
            "description": voice_script,
        }
    )

    ambience_enabled = _as_bool(ambience.get("enabled"))
    ambience_description = str(ambience.get("description") or "Placeholder ambiance sonore.")
    ambience_text_path = AUDIO_ROOT / "ambience.txt"
    ambience_text_path.write_text(
        (
            "type: ambience\n"
            f"request_id: {request_id}\n"
            f"enabled: {str(ambience_enabled).lower()}\n"
            f"description: {ambience_description}\n"
        ),
        encoding="utf-8",
    )
    artifacts.append(
        {
            "kind": "ambience",
            "enabled": ambience_enabled,
            "path": ambience_text_path.as_posix(),
            "description": ambience_description,
        }
    )

    manifest_path = write_json_utf8(
        AUDIO_ROOT / "audio_manifest.json",
        {
            "request_id": request_id,
            "source_contract": "output.audio_plan",
            "audio_plan": audio_plan,
            "artifacts": artifacts,
            "count": len(artifacts),
        },
    )

    output["audio_artifacts"] = artifacts
    output["audio_manifest_file"] = manifest_path.as_posix()
    return artifacts
