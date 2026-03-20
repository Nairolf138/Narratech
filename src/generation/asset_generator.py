"""Génération d'assets persistants pour le pipeline narratif."""

from __future__ import annotations

import re
from pathlib import Path

from src.core.io_utils import write_json_utf8
from src.providers import MockAssetProvider, ProviderRequest
from src.providers.adapter import call_with_normalized_errors
from src.providers.contracts import AssetProviderContract


ASSETS_ROOT = Path("assets")


def _slugify(value: str) -> str:
    """Convertit une chaîne en slug simple pour un nom de fichier stable."""
    cleaned = re.sub(r"[^a-zA-Z0-9.]+", "_", value.strip().lower())
    return cleaned.strip("_") or "item"


def _write_asset_file(asset_uri: str, payload: dict) -> None:
    """Écrit un fichier JSON simple pour l'asset généré."""
    if not asset_uri.startswith("local://"):
        raise ValueError("Les URIs d'assets doivent commencer par local://")

    path = Path(asset_uri.replace("local://", "", 1))
    write_json_utf8(path, payload)


def _resolve_uri(asset: dict, asset_dir: Path, index: int) -> str:
    uri = asset.get("uri")
    if isinstance(uri, str) and uri.startswith("local://"):
        return uri

    file_name = str(asset.get("file_name") or f"asset_{index:03d}.json")
    extension = ".json"
    if "." in file_name:
        extension = f".{file_name.split('.')[-1]}"
    normalized_name = _slugify(file_name)
    if not normalized_name.endswith(extension):
        normalized_name = f"{normalized_name}.{extension.lstrip('.')}"
    return f"local://{(asset_dir / normalized_name).as_posix()}"


def generate(scene_doc: dict, provider: AssetProviderContract | None = None) -> list[dict]:
    """Génère les placeholders d'assets via un provider injectable."""
    if not isinstance(scene_doc, dict):
        raise TypeError("scene_doc doit être un dictionnaire")

    output = scene_doc.get("output")
    if not isinstance(output, dict):
        raise ValueError("scene_doc.output doit être un objet")

    request_id = str(scene_doc.get("request_id", "request_unknown"))
    asset_dir = ASSETS_ROOT / request_id
    asset_dir.mkdir(parents=True, exist_ok=True)

    active_provider = provider or MockAssetProvider()
    response = call_with_normalized_errors(
        lambda: (
            active_provider.generate_assets(
                ProviderRequest(
                    request_id=request_id,
                    payload={"request_id": request_id, "output": output},
                    timeout_sec=10.0,
                )
            )
            if hasattr(active_provider, "generate_assets")
            else active_provider.generate(
                ProviderRequest(
                    request_id=request_id,
                    payload={"request_id": request_id, "output": output},
                    timeout_sec=10.0,
                )
            )
        )
    )

    provider_assets = response.data.get("assets")
    if not isinstance(provider_assets, list):
        raise ValueError("Le provider d'assets doit retourner data.assets sous forme de liste")

    asset_refs: list[dict] = []
    for index, asset in enumerate(provider_assets, start=1):
        if not isinstance(asset, dict):
            continue

        uri = _resolve_uri(asset, asset_dir, index)
        asset_ref = {
            "id": str(asset.get("id") or f"asset_{index:03d}"),
            "type": str(asset.get("type") or "generic"),
            "uri": uri,
            "metadata_uri": asset.get("metadata_uri"),
            "seed": asset.get("seed"),
            "generation_params": asset.get("generation_params"),
            "request_id": request_id,
            "provider_trace": response.provider_trace,
            "latency_ms": response.latency_ms,
            "cost_estimate": response.cost_estimate,
            "model_name": response.model_name,
        }
        asset_refs.append(asset_ref)

        payload = asset.get("payload") if isinstance(asset.get("payload"), dict) else {}
        if payload:
            _write_asset_file(f"local://{(asset_dir / f'{asset_ref['id']}_generation.json').as_posix()}", payload)

    write_json_utf8(asset_dir / "assets_manifest.json", {"request_id": request_id, "assets": asset_refs})

    output["asset_refs"] = asset_refs
    return asset_refs
