"""Moteur de cohérence pour enrichir les prompts de plans sans changer la topologie."""

from __future__ import annotations

from copy import deepcopy

from src.core.io_utils import write_json_utf8

# Contraintes visuelles fixes injectées dans chaque shot.
VISUAL_CONSTRAINTS = {
    "lighting_style": "cinematic soft key light with gentle contrast",
    "color_palette": ["#1F2A44", "#D9A441", "#E8E3D9"],
    "camera_style": "35mm lens, stable dolly movement, medium depth of field",
}


def enrich(scene_doc: dict) -> dict:
    """Enrichit les prompts des shots et sauvegarde un artefact enrichi.

    Garanties:
    - réutilise les IDs personnages existants (`output.characters[*].id`);
    - injecte des contraintes visuelles fixes dans chaque shot;
    - ne modifie pas la topologie (même nombre de scènes/shots, mêmes id/scene_id).
    """
    if not isinstance(scene_doc, dict):
        raise TypeError("scene_doc doit être un dictionnaire.")

    enriched_doc = deepcopy(scene_doc)
    output = enriched_doc.get("output")
    if not isinstance(output, dict):
        raise ValueError("scene_doc.output doit être un objet.")

    characters = output.get("characters", [])
    shots = output.get("shots", [])

    character_ids = [char.get("id") for char in characters if isinstance(char, dict) and char.get("id")]
    character_ids_text = ", ".join(character_ids) if character_ids else "none"

    for shot in shots:
        if not isinstance(shot, dict):
            continue

        base_description = shot.get("description", "")
        enriched_prompt = (
            f"{base_description}\n"
            f"[character_ids: {character_ids_text}]\n"
            f"[scene_id: {shot.get('scene_id', '')}]\n"
            "Respect strict de la continuité inter-scènes et des éléments visuels imposés."
        )

        shot["consistency_constraints"] = deepcopy(VISUAL_CONSTRAINTS)
        shot["enriched_prompt"] = enriched_prompt

    write_json_utf8("outputs/scene_enriched.json", enriched_doc)

    return enriched_doc
