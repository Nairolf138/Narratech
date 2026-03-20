"""Génération de placeholders de clips pour les plans (shots)."""

from __future__ import annotations

import re
from pathlib import Path

from src.core.io_utils import write_json_utf8
from src.providers import MockShotProvider, ProviderRequest
from src.providers.adapter import call_with_normalized_errors
from src.providers.contracts import ShotProviderContract


SHOTS_ROOT = Path("outputs/shots")


def _slugify(value: str) -> str:
    """Convertit un texte en slug stable pour nom de fichier."""
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower())
    return cleaned.strip("_") or "shot"


def generate(
    scene_doc: dict,
    provider: ShotProviderContract | None = None,
    asset_refs: list[dict] | None = None,
) -> list[dict]:
    """Écrit un fichier placeholder par shot via un provider injectable."""
    if not isinstance(scene_doc, dict):
        raise TypeError("scene_doc doit être un dictionnaire")

    output = scene_doc.get("output")
    if not isinstance(output, dict):
        raise ValueError("scene_doc.output doit être un objet")

    SHOTS_ROOT.mkdir(parents=True, exist_ok=True)

    request_id = str(scene_doc.get("request_id", "request_unknown"))
    active_provider = provider or MockShotProvider()
    resolved_asset_refs = asset_refs if asset_refs is not None else output.get("asset_refs")
    if resolved_asset_refs is None:
        resolved_asset_refs = []

    response = call_with_normalized_errors(
        lambda: (
            active_provider.generate_shots(
                ProviderRequest(
                    request_id=request_id,
                    payload={
                        "request_id": request_id,
                        "output": output,
                        "asset_refs": resolved_asset_refs,
                    },
                    timeout_sec=10.0,
                )
            )
            if hasattr(active_provider, "generate_shots")
            else active_provider.generate(
                ProviderRequest(
                    request_id=request_id,
                    payload={
                        "request_id": request_id,
                        "output": output,
                        "asset_refs": resolved_asset_refs,
                    },
                    timeout_sec=10.0,
                )
            )
        )
    )

    provider_clips = response.data.get("clips")
    if not isinstance(provider_clips, list):
        raise ValueError("Le provider de shots doit retourner data.clips sous forme de liste")

    fallback_asset_dependency_ids = [
        str(asset.get("id"))
        for asset in resolved_asset_refs
        if isinstance(asset, dict) and asset.get("id") is not None
    ]
    clips: list[dict] = []
    dependencies: list[dict] = []
    for order, clip in enumerate(provider_clips, start=1):
        if not isinstance(clip, dict):
            continue

        shot_id = str(clip.get("shot_id") or f"shot_{order:03d}")
        duration = float(clip.get("duration") or 0.0)
        enriched_description = str(clip.get("description_enriched") or "")
        asset_dependency_ids = clip.get("asset_dependencies")
        if not isinstance(asset_dependency_ids, list):
            asset_dependency_ids = fallback_asset_dependency_ids
        slug = _slugify(shot_id)[:60]

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
                "request_id": request_id,
                "duration": duration,
                "order": order,
                "provider_trace": response.provider_trace,
                "latency_ms": response.latency_ms,
                "cost_estimate": response.cost_estimate,
                "model_name": response.model_name,
                "asset_dependencies": asset_dependency_ids,
            }
        )
        dependencies.append({"shot_id": shot_id, "asset_ids": asset_dependency_ids})

    write_json_utf8(
        SHOTS_ROOT / "shots_manifest.json",
        {
            "request_id": request_id,
            "clips": clips,
            "count": len(clips),
            "asset_dependencies": dependencies,
        },
    )

    output["clips"] = clips
    return clips
