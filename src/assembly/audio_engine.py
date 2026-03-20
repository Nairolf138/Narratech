"""Moteur audio placeholder basé sur output.audio_plan."""

from __future__ import annotations

from pathlib import Path

from src.core.io_utils import write_json_utf8
from src.providers import MockAudioProvider, ProviderRequest

AUDIO_ROOT = Path("outputs/audio")


class AudioContractError(ValueError):
    """Erreur levée quand le contrat output.audio_plan est invalide."""


def _as_bool(value: object) -> bool:
    return bool(value) if isinstance(value, bool) else False


def _extract_shots(scene_doc: dict) -> list[dict]:
    output = scene_doc.get("output")
    if not isinstance(output, dict):
        return []
    shots = output.get("shots")
    if not isinstance(shots, list):
        return []
    return [shot for shot in shots if isinstance(shot, dict)]


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

    provider = MockAudioProvider()
    shots = _extract_shots(scene_doc)
    input_doc = scene_doc.get("input") if isinstance(scene_doc.get("input"), dict) else {}

    voice_response = provider.synthesize_audio(
        ProviderRequest(
            request_id=request_id,
            payload={
                "request_id": request_id,
                "mode": "voiceover",
                "narrative_text": str(voiceover.get("script") or "Placeholder voix off."),
                "language": str(voiceover.get("language") or input_doc.get("language") or "und"),
                "style": str(voiceover.get("style") or input_doc.get("style") or "neutral"),
                "voice": {
                    "name": str(voiceover.get("voice") or "default"),
                },
                "shots": shots,
                "format": "txt",
            },
            timeout_sec=10.0,
        )
    )

    ambience_response = provider.synthesize_audio(
        ProviderRequest(
            request_id=request_id,
            payload={
                "request_id": request_id,
                "mode": "ambience",
                "narrative_text": str(ambience.get("description") or "Placeholder ambiance sonore."),
                "language": str(ambience.get("language") or input_doc.get("language") or "und"),
                "style": str(ambience.get("style") or input_doc.get("style") or "ambient"),
                "shots": shots,
                "format": "txt",
            },
            timeout_sec=10.0,
        )
    )

    artifacts = [
        {
            "kind": "voiceover",
            "enabled": _as_bool(voiceover.get("enabled")),
            "language": voice_response.data["metadata"]["language"],
            "path": voice_response.data["audio_file"],
            "description": str(voiceover.get("script") or ""),
            "metadata": voice_response.data["metadata"],
            "timestamps": voice_response.data["timestamps"],
            "provider_trace": voice_response.provider_trace,
            "latency_ms": voice_response.latency_ms,
            "cost_estimate": voice_response.cost_estimate,
            "model_name": voice_response.model_name,
        },
        {
            "kind": "ambience",
            "enabled": _as_bool(ambience.get("enabled")),
            "path": ambience_response.data["audio_file"],
            "description": str(ambience.get("description") or ""),
            "metadata": ambience_response.data["metadata"],
            "timestamps": ambience_response.data["timestamps"],
            "provider_trace": ambience_response.provider_trace,
            "latency_ms": ambience_response.latency_ms,
            "cost_estimate": ambience_response.cost_estimate,
            "model_name": ambience_response.model_name,
        },
    ]

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
