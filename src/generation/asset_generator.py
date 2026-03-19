"""Génération d'assets placeholder persistants pour le pipeline narratif."""

from __future__ import annotations

import re
from pathlib import Path

from src.core.io_utils import write_json_utf8


ASSETS_ROOT = Path("assets")


def _slugify(value: str) -> str:
    """Convertit une chaîne en slug simple pour un nom de fichier stable."""
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower())
    return cleaned.strip("_") or "item"


def _write_asset_file(asset_uri: str, payload: dict) -> None:
    """Écrit un fichier JSON simple pour l'asset généré."""
    if not asset_uri.startswith("local://"):
        raise ValueError("Les URIs d'assets doivent commencer par local://")

    path = Path(asset_uri.replace("local://", "", 1))
    write_json_utf8(path, payload)


def generate(scene_doc: dict) -> list[dict]:
    """Génère des placeholders d'assets et réinjecte les références dans `output.asset_refs`.

    Règles:
    - un placeholder par personnage;
    - au moins un placeholder d'environnement;
    - chaque ref suit le contrat `{id, type, uri}`;
    - les fichiers assets sont écrits dans `assets/`.
    """
    if not isinstance(scene_doc, dict):
        raise TypeError("scene_doc doit être un dictionnaire")

    output = scene_doc.get("output")
    if not isinstance(output, dict):
        raise ValueError("scene_doc.output doit être un objet")

    request_id = str(scene_doc.get("request_id", "request_unknown"))
    asset_dir = ASSETS_ROOT / request_id
    asset_dir.mkdir(parents=True, exist_ok=True)

    asset_refs: list[dict] = []

    characters = output.get("characters", [])
    for index, character in enumerate(characters, start=1):
        if not isinstance(character, dict):
            continue

        char_id = str(character.get("id") or f"char_{index}")
        char_name = str(character.get("name") or char_id)
        file_name = f"character_{_slugify(char_name)}_{index:02d}.json"
        uri = f"local://{(asset_dir / file_name).as_posix()}"

        asset_ref = {
            "id": f"asset_character_{index:03d}",
            "type": "character",
            "uri": uri,
        }
        asset_refs.append(asset_ref)

        _write_asset_file(
            uri,
            {
                "kind": "character",
                "character_id": char_id,
                "character_name": char_name,
                "placeholder": True,
            },
        )

    scenes = output.get("scenes", [])
    scene_summary = ""
    if scenes and isinstance(scenes[0], dict):
        scene_summary = str(scenes[0].get("summary") or "")

    env_uri = f"local://{(asset_dir / 'environment_main_01.json').as_posix()}"
    environment_ref = {
        "id": "asset_environment_001",
        "type": "environment",
        "uri": env_uri,
    }
    asset_refs.append(environment_ref)

    _write_asset_file(
        env_uri,
        {
            "kind": "environment",
            "scene_summary": scene_summary,
            "placeholder": True,
        },
    )

    write_json_utf8(asset_dir / "assets_manifest.json", {"request_id": request_id, "assets": asset_refs})

    output["asset_refs"] = asset_refs
    return asset_refs
