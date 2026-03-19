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

REQUIRED_VISUAL_CONSTRAINT_KEYS = tuple(VISUAL_CONSTRAINTS.keys())


def _make_issue(
    *,
    rule_id: str,
    severity: str,
    location: str,
    message: str,
    suggested_fix: str,
) -> dict:
    return {
        "rule_id": rule_id,
        "severity": severity,
        "location": location,
        "message": message,
        "suggested_fix": suggested_fix,
    }


def _apply_enrichment(output: dict) -> None:
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


def _rule_character_ids(output: dict) -> list[dict]:
    issues: list[dict] = []
    characters = output.get("characters", [])
    shots = output.get("shots", [])

    known_ids: set[str] = set()
    duplicate_ids: set[str] = set()

    for idx, character in enumerate(characters):
        location = f"output.characters[{idx}]"
        if not isinstance(character, dict):
            issues.append(
                _make_issue(
                    rule_id="character_ids_consistency",
                    severity="error",
                    location=location,
                    message="Le personnage doit être un objet.",
                    suggested_fix="Définir chaque personnage comme un objet avec au minimum un champ id.",
                )
            )
            continue

        character_id = character.get("id")
        if not isinstance(character_id, str) or not character_id.strip():
            issues.append(
                _make_issue(
                    rule_id="character_ids_consistency",
                    severity="error",
                    location=f"{location}.id",
                    message="ID personnage manquant ou vide.",
                    suggested_fix="Renseigner un identifiant stable non vide, par exemple 'char_001'.",
                )
            )
            continue

        if character_id in known_ids:
            duplicate_ids.add(character_id)
        known_ids.add(character_id)

    for character_id in sorted(duplicate_ids):
        issues.append(
            _make_issue(
                rule_id="character_ids_consistency",
                severity="error",
                location="output.characters",
                message=f"ID personnage dupliqué: '{character_id}'.",
                suggested_fix="Garantir l'unicité de chaque output.characters[*].id.",
            )
        )

    for shot_idx, shot in enumerate(shots):
        if not isinstance(shot, dict):
            continue

        referenced_ids = shot.get("character_ids")
        if referenced_ids is None:
            continue

        if not isinstance(referenced_ids, list):
            issues.append(
                _make_issue(
                    rule_id="character_ids_consistency",
                    severity="error",
                    location=f"output.shots[{shot_idx}].character_ids",
                    message="character_ids doit être une liste lorsqu'il est renseigné.",
                    suggested_fix="Utiliser une liste de chaînes correspondant aux IDs de output.characters.",
                )
            )
            continue

        for char_idx, character_id in enumerate(referenced_ids):
            if not isinstance(character_id, str) or character_id not in known_ids:
                issues.append(
                    _make_issue(
                        rule_id="character_ids_consistency",
                        severity="error",
                        location=f"output.shots[{shot_idx}].character_ids[{char_idx}]",
                        message=f"Référence personnage inconnue: '{character_id}'.",
                        suggested_fix="Remplacer par un ID existant dans output.characters[*].id.",
                    )
                )

    if not issues:
        issues.append(
            _make_issue(
                rule_id="character_ids_consistency",
                severity="info",
                location="output.characters",
                message="IDs personnages cohérents.",
                suggested_fix="Aucune action requise.",
            )
        )

    return issues


def _rule_visual_constraints(output: dict) -> list[dict]:
    issues: list[dict] = []
    shots = output.get("shots", [])

    for shot_idx, shot in enumerate(shots):
        if not isinstance(shot, dict):
            continue

        constraints = shot.get("consistency_constraints")
        location = f"output.shots[{shot_idx}].consistency_constraints"
        if not isinstance(constraints, dict):
            issues.append(
                _make_issue(
                    rule_id="visual_constraints_presence",
                    severity="error",
                    location=location,
                    message="Contraintes visuelles absentes sur le shot.",
                    suggested_fix="Injecter consistency_constraints avec lighting_style, color_palette, camera_style.",
                )
            )
            continue

        missing_keys = [key for key in REQUIRED_VISUAL_CONSTRAINT_KEYS if key not in constraints]
        for missing_key in missing_keys:
            issues.append(
                _make_issue(
                    rule_id="visual_constraints_presence",
                    severity="error",
                    location=location,
                    message=f"Contrainte visuelle manquante: '{missing_key}'.",
                    suggested_fix="Ajouter toutes les clés requises de VISUAL_CONSTRAINTS.",
                )
            )

    if not issues:
        issues.append(
            _make_issue(
                rule_id="visual_constraints_presence",
                severity="info",
                location="output.shots",
                message="Contraintes visuelles présentes sur tous les shots.",
                suggested_fix="Aucune action requise.",
            )
        )

    return issues


def _rule_scene_shot_order(output: dict) -> list[dict]:
    issues: list[dict] = []
    scenes = output.get("scenes", [])
    shots = output.get("shots", [])

    scene_index_map: dict[str, int] = {}
    for idx, scene in enumerate(scenes):
        if not isinstance(scene, dict):
            continue
        scene_id = scene.get("id")
        if isinstance(scene_id, str) and scene_id:
            scene_index_map[scene_id] = idx

    seen_scene_indexes: list[int] = []
    for shot_idx, shot in enumerate(shots):
        if not isinstance(shot, dict):
            continue

        scene_id = shot.get("scene_id")
        if not isinstance(scene_id, str) or scene_id not in scene_index_map:
            issues.append(
                _make_issue(
                    rule_id="scene_shot_order",
                    severity="error",
                    location=f"output.shots[{shot_idx}].scene_id",
                    message=f"scene_id inconnu pour le shot: '{scene_id}'.",
                    suggested_fix="Utiliser un scene_id existant dans output.scenes[*].id.",
                )
            )
            continue

        seen_scene_indexes.append(scene_index_map[scene_id])

    for idx in range(1, len(seen_scene_indexes)):
        previous_scene_index = seen_scene_indexes[idx - 1]
        current_scene_index = seen_scene_indexes[idx]
        if current_scene_index < previous_scene_index:
            issues.append(
                _make_issue(
                    rule_id="scene_shot_order",
                    severity="warning",
                    location="output.shots",
                    message="Ordre des shots non aligné avec l'ordre des scènes.",
                    suggested_fix="Réordonner output.shots pour respecter la progression de output.scenes.",
                )
            )
            break

    if not issues:
        issues.append(
            _make_issue(
                rule_id="scene_shot_order",
                severity="info",
                location="output.shots",
                message="Ordre shots/scènes cohérent.",
                suggested_fix="Aucune action requise.",
            )
        )

    return issues


def build_consistency_report(scene_doc: dict) -> list[dict]:
    """Construit un rapport stable des règles de cohérence."""
    output = scene_doc.get("output")
    if not isinstance(output, dict):
        raise ValueError("scene_doc.output doit être un objet.")

    report: list[dict] = []
    report.extend(_rule_character_ids(output))
    report.extend(_rule_visual_constraints(output))
    report.extend(_rule_scene_shot_order(output))
    return report


def has_blocking_violations(consistency_report: list[dict]) -> bool:
    """Retourne True s'il existe au moins une violation bloquante."""
    return any(issue.get("severity") == "error" for issue in consistency_report if isinstance(issue, dict))


def enrich(scene_doc: dict) -> dict:
    """Enrichit les shots et retourne le document enrichi + rapport de cohérence."""
    if not isinstance(scene_doc, dict):
        raise TypeError("scene_doc doit être un dictionnaire.")

    enriched_doc = deepcopy(scene_doc)
    output = enriched_doc.get("output")
    if not isinstance(output, dict):
        raise ValueError("scene_doc.output doit être un objet.")

    _apply_enrichment(output)

    write_json_utf8("outputs/scene_enriched.json", enriched_doc)

    consistency_report = build_consistency_report(enriched_doc)

    return {
        "enriched_doc": enriched_doc,
        "consistency_report": consistency_report,
    }
