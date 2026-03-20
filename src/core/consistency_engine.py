"""Moteur de cohérence pour enrichir les prompts de plans sans changer la topologie."""

from __future__ import annotations

from copy import deepcopy
import re

from src.core.io_utils import write_json_utf8

# Contraintes visuelles fixes injectées dans chaque shot.
VISUAL_CONSTRAINTS = {
    "lighting_style": "cinematic soft key light with gentle contrast",
    "color_palette": ["#1F2A44", "#D9A441", "#E8E3D9"],
    "camera_style": "35mm lens, stable dolly movement, medium depth of field",
}

REQUIRED_VISUAL_CONSTRAINT_KEYS = tuple(VISUAL_CONSTRAINTS.keys())
DEFAULT_QUALITY_GATES = {
    "traits_min_overlap": 0.7,
    "lighting_min_similarity": 0.8,
    "max_tension_jump": 3,
    "max_anachronism_count": 0,
}


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


def _normalize_token(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _safe_div(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def build_consistency_packet(scene_doc: dict) -> dict:
    """Construit un consistency packet aligné avec docs/consistency_rules.md."""
    output = scene_doc.get("output")
    if not isinstance(output, dict):
        raise ValueError("scene_doc.output doit être un objet.")

    characters = output.get("characters", [])
    scenes = output.get("scenes", [])
    shots = output.get("shots", [])

    scene_id = ""
    if scenes and isinstance(scenes[0], dict):
        first_scene_id = scenes[0].get("id")
        if isinstance(first_scene_id, str):
            scene_id = first_scene_id

    first_shot_scene_id = scene_id
    if shots and isinstance(shots[0], dict):
        shot_scene_id = shots[0].get("scene_id")
        if isinstance(shot_scene_id, str):
            first_shot_scene_id = shot_scene_id

    packet_characters: list[dict] = []
    for idx, character in enumerate(characters):
        if not isinstance(character, dict):
            continue

        char_id = character.get("id")
        if not isinstance(char_id, str) or not char_id.strip():
            char_id = f"char_{idx + 1:03d}"
        display_name = character.get("name") if isinstance(character.get("name"), str) else char_id
        role = character.get("role") if isinstance(character.get("role"), str) else "personnage"

        packet_characters.append(
            {
                "character_id": char_id,
                "display_name": display_name,
                "allowed_aliases": [],
                "core_traits": [_normalize_token(role)],
                "signature_clothing": [],
                "color_palette": deepcopy(VISUAL_CONSTRAINTS["color_palette"]),
            }
        )

    action_sequence = [
        shot.get("description", "")
        for shot in shots
        if isinstance(shot, dict) and isinstance(shot.get("description"), str) and shot.get("description", "").strip()
    ]

    return {
        "consistency_packet_version": "1.0",
        "project_id": scene_doc.get("request_id", "unknown_project"),
        "sequence_id": scene_doc.get("request_id", "unknown_sequence"),
        "scene_id": first_shot_scene_id,
        "characters": packet_characters,
        "visual_continuity": {
            "lighting_profile": VISUAL_CONSTRAINTS["lighting_style"],
            "period_style": "contemporary",
            "mood_tone": "tension contenue",
            "camera_style": VISUAL_CONSTRAINTS["camera_style"],
            "period_banned_items": [],
        },
        "narrative_continuity": {
            "arc_goal": output.get("synopsis", ""),
            "scene_goal": scenes[0].get("summary", "") if scenes and isinstance(scenes[0], dict) else "",
            "tension_level": 5,
            "action_sequence": action_sequence,
            "twist_flag": False,
            "transition_reason": "",
        },
        "quality_gates": deepcopy(DEFAULT_QUALITY_GATES),
    }


def _apply_enrichment(scene_doc: dict) -> None:
    output = scene_doc.get("output", {})
    if not isinstance(output, dict):
        return
    shots = output.get("shots", [])
    if not isinstance(shots, list):
        return

    base_packet = build_consistency_packet(scene_doc)

    character_ids = [
        char.get("character_id")
        for char in base_packet.get("characters", [])
        if isinstance(char, dict) and isinstance(char.get("character_id"), str)
    ]
    character_ids_text = ", ".join(character_ids) if character_ids else "none"

    for shot in shots:
        if not isinstance(shot, dict):
            continue

        shot_packet = deepcopy(base_packet)
        shot_packet["scene_id"] = shot.get("scene_id", base_packet.get("scene_id"))
        shot["consistency_packet"] = shot_packet
        shot["consistency_constraints"] = deepcopy(VISUAL_CONSTRAINTS)

        base_description = shot.get("description", "")
        shot["enriched_prompt"] = (
            f"{base_description}\n"
            f"[character_ids: {character_ids_text}]\n"
            f"[scene_id: {shot.get('scene_id', '')}]\n"
            "Respect strict de la continuité inter-scènes et des éléments visuels imposés."
        )


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


def _rule_consistency_packet_presence(output: dict) -> list[dict]:
    issues: list[dict] = []
    shots = output.get("shots", [])
    required_fields = (
        "consistency_packet_version",
        "characters",
        "visual_continuity",
        "narrative_continuity",
        "quality_gates",
    )

    for shot_idx, shot in enumerate(shots):
        if not isinstance(shot, dict):
            continue

        packet = shot.get("consistency_packet")
        location = f"output.shots[{shot_idx}].consistency_packet"
        if not isinstance(packet, dict):
            issues.append(
                _make_issue(
                    rule_id="consistency_packet_presence",
                    severity="error",
                    location=location,
                    message="Consistency packet absent sur le shot.",
                    suggested_fix="Injecter un consistency_packet complet dans chaque shot.",
                )
            )
            continue

        for field in required_fields:
            if field not in packet:
                issues.append(
                    _make_issue(
                        rule_id="consistency_packet_presence",
                        severity="error",
                        location=location,
                        message=f"Champ requis manquant dans consistency_packet: '{field}'.",
                        suggested_fix="Inclure les champs minimaux du packet dans chaque shot.",
                    )
                )

    if not issues:
        issues.append(
            _make_issue(
                rule_id="consistency_packet_presence",
                severity="info",
                location="output.shots",
                message="Consistency packet présent sur tous les shots.",
                suggested_fix="Aucune action requise.",
            )
        )
    return issues


def _rule_traits_overlap(output: dict) -> list[dict]:
    issues: list[dict] = []
    shots = [shot for shot in output.get("shots", []) if isinstance(shot, dict)]
    if not shots:
        return issues

    reference_packet = shots[0].get("consistency_packet")
    if not isinstance(reference_packet, dict):
        return issues

    quality_gates = reference_packet.get("quality_gates", {})
    threshold = (
        quality_gates.get("traits_min_overlap")
        if isinstance(quality_gates, dict) and isinstance(quality_gates.get("traits_min_overlap"), (int, float))
        else DEFAULT_QUALITY_GATES["traits_min_overlap"]
    )

    reference_traits: dict[str, set[str]] = {}
    ref_characters = reference_packet.get("characters", [])
    if isinstance(ref_characters, list):
        for character in ref_characters:
            if not isinstance(character, dict):
                continue
            char_id = character.get("character_id")
            core_traits = character.get("core_traits")
            if isinstance(char_id, str) and isinstance(core_traits, list):
                normalized_traits = {
                    _normalize_token(trait) for trait in core_traits if isinstance(trait, str) and trait.strip()
                }
                if normalized_traits:
                    reference_traits[char_id] = normalized_traits

    for shot_idx, shot in enumerate(shots):
        packet = shot.get("consistency_packet")
        if not isinstance(packet, dict):
            continue
        characters = packet.get("characters", [])
        if not isinstance(characters, list):
            continue

        for char_idx, character in enumerate(characters):
            if not isinstance(character, dict):
                continue
            char_id = character.get("character_id")
            core_traits = character.get("core_traits")
            if not isinstance(char_id, str) or not isinstance(core_traits, list) or char_id not in reference_traits:
                continue

            current_traits = {
                _normalize_token(trait) for trait in core_traits if isinstance(trait, str) and trait.strip()
            }
            if not current_traits:
                continue

            overlap_ratio = len(current_traits & reference_traits[char_id]) / len(reference_traits[char_id])
            if overlap_ratio < float(threshold):
                issues.append(
                    _make_issue(
                        rule_id="traits_overlap",
                        severity="error",
                        location=f"output.shots[{shot_idx}].consistency_packet.characters[{char_idx}]",
                        message=f"Overlap de traits insuffisant pour '{char_id}' ({overlap_ratio:.2f} < {threshold:.2f}).",
                        suggested_fix="Rétablir les core_traits du personnage pour atteindre le seuil minimal.",
                    )
                )

    if not issues:
        issues.append(
            _make_issue(
                rule_id="traits_overlap",
                severity="info",
                location="output.shots",
                message="Overlap des traits conforme.",
                suggested_fix="Aucune action requise.",
            )
        )
    return issues


def _rule_anachronism(output: dict) -> list[dict]:
    issues: list[dict] = []
    shots = output.get("shots", [])
    for shot_idx, shot in enumerate(shots):
        if not isinstance(shot, dict):
            continue
        packet = shot.get("consistency_packet")
        if not isinstance(packet, dict):
            continue
        visual = packet.get("visual_continuity")
        if not isinstance(visual, dict):
            continue
        banned_items = visual.get("period_banned_items", [])
        if not isinstance(banned_items, list):
            continue

        description = str(shot.get("description") or "")
        anachronism_count = 0
        for banned_item in banned_items:
            if isinstance(banned_item, str) and banned_item.strip() and banned_item.lower() in description.lower():
                anachronism_count += 1
                issues.append(
                    _make_issue(
                        rule_id="period_anachronism",
                        severity="error",
                        location=f"output.shots[{shot_idx}].description",
                        message=f"Anachronisme détecté: '{banned_item}'.",
                        suggested_fix="Supprimer les éléments interdits par period_banned_items.",
                    )
                )

        max_count = DEFAULT_QUALITY_GATES["max_anachronism_count"]
        gates = packet.get("quality_gates")
        if isinstance(gates, dict) and isinstance(gates.get("max_anachronism_count"), int):
            max_count = gates["max_anachronism_count"]
        if anachronism_count > max_count:
            issues.append(
                _make_issue(
                    rule_id="period_anachronism",
                    severity="error",
                    location=f"output.shots[{shot_idx}].consistency_packet.quality_gates.max_anachronism_count",
                    message=f"Nombre d'anachronismes ({anachronism_count}) au-dessus du seuil ({max_count}).",
                    suggested_fix="Réduire anachronism_count au seuil autorisé.",
                )
            )

    if not issues:
        issues.append(
            _make_issue(
                rule_id="period_anachronism",
                severity="info",
                location="output.shots",
                message="Aucun anachronisme détecté.",
                suggested_fix="Aucune action requise.",
            )
        )
    return issues


def _rule_tension_jump(output: dict) -> list[dict]:
    issues: list[dict] = []
    shots = [shot for shot in output.get("shots", []) if isinstance(shot, dict)]
    previous_tension: int | None = None
    previous_twist = False

    for shot_idx, shot in enumerate(shots):
        packet = shot.get("consistency_packet")
        if not isinstance(packet, dict):
            continue
        narrative = packet.get("narrative_continuity")
        gates = packet.get("quality_gates")
        if not isinstance(narrative, dict):
            continue

        tension = narrative.get("tension_level")
        if not isinstance(tension, (int, float)):
            continue
        twist_flag = bool(narrative.get("twist_flag"))
        max_jump = DEFAULT_QUALITY_GATES["max_tension_jump"]
        if isinstance(gates, dict) and isinstance(gates.get("max_tension_jump"), (int, float)):
            max_jump = gates["max_tension_jump"]

        if previous_tension is not None and abs(float(tension) - previous_tension) > float(max_jump):
            if not (twist_flag or previous_twist):
                issues.append(
                    _make_issue(
                        rule_id="tension_jump",
                        severity="warning",
                        location=f"output.shots[{shot_idx}].consistency_packet.narrative_continuity.tension_level",
                        message=(
                            f"Saut de tension trop fort ({previous_tension:.1f} -> {float(tension):.1f}) "
                            f"sans twist_flag."
                        ),
                        suggested_fix="Lisser la courbe de tension ou expliciter twist_flag=true.",
                    )
                )
        previous_tension = float(tension)
        previous_twist = twist_flag

    if not issues:
        issues.append(
            _make_issue(
                rule_id="tension_jump",
                severity="info",
                location="output.shots",
                message="Variation de tension conforme.",
                suggested_fix="Aucune action requise.",
            )
        )
    return issues


def _rule_causal_order(output: dict) -> list[dict]:
    issues: list[dict] = []
    shots = [shot for shot in output.get("shots", []) if isinstance(shot, dict)]
    seen_actions: set[str] = set()

    for shot_idx, shot in enumerate(shots):
        description = str(shot.get("description") or "")
        packet = shot.get("consistency_packet")
        if not isinstance(packet, dict):
            continue
        narrative = packet.get("narrative_continuity")
        if not isinstance(narrative, dict):
            continue
        action_sequence = narrative.get("action_sequence")
        if not isinstance(action_sequence, list):
            continue

        normalized_description = _normalize_token(description)
        for action_idx, action in enumerate(action_sequence):
            if not isinstance(action, str) or not action.strip():
                continue
            normalized_action = _normalize_token(action)
            if normalized_action and normalized_action in normalized_description:
                missing_predecessor = next(
                    (
                        _normalize_token(prev_action)
                        for prev_action in action_sequence[:action_idx]
                        if isinstance(prev_action, str)
                        and _normalize_token(prev_action)
                        and _normalize_token(prev_action) not in seen_actions
                    ),
                    None,
                )
                if missing_predecessor:
                    issues.append(
                        _make_issue(
                            rule_id="causal_order",
                            severity="error",
                            location=f"output.shots[{shot_idx}].description",
                            message=f"Ordre causal violé: '{action}' apparaît avant ses prérequis.",
                            suggested_fix="Respecter l'ordre des actions défini dans action_sequence.",
                        )
                    )
                seen_actions.add(normalized_action)

    if not issues:
        issues.append(
            _make_issue(
                rule_id="causal_order",
                severity="info",
                location="output.shots",
                message="Ordre causal respecté.",
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
    report.extend(_rule_consistency_packet_presence(output))
    report.extend(_rule_visual_constraints(output))
    report.extend(_rule_scene_shot_order(output))
    report.extend(_rule_traits_overlap(output))
    report.extend(_rule_anachronism(output))
    report.extend(_rule_tension_jump(output))
    report.extend(_rule_causal_order(output))
    return report


def _compute_character_trait_alignment(output: dict) -> tuple[float, dict]:
    shots = [shot for shot in output.get("shots", []) if isinstance(shot, dict)]
    if not shots:
        return 1.0, {"comparisons": 0}

    reference_packet = shots[0].get("consistency_packet")
    if not isinstance(reference_packet, dict):
        return 0.0, {"comparisons": 0}

    reference_traits: dict[str, set[str]] = {}
    for character in reference_packet.get("characters", []):
        if not isinstance(character, dict):
            continue
        char_id = character.get("character_id")
        core_traits = character.get("core_traits")
        if not isinstance(char_id, str) or not isinstance(core_traits, list):
            continue
        normalized_traits = {
            _normalize_token(trait)
            for trait in core_traits
            if isinstance(trait, str) and trait.strip()
        }
        if normalized_traits:
            reference_traits[char_id] = normalized_traits

    overlap_scores: list[float] = []
    for shot in shots:
        packet = shot.get("consistency_packet")
        if not isinstance(packet, dict):
            continue
        characters = packet.get("characters")
        if not isinstance(characters, list):
            continue
        for character in characters:
            if not isinstance(character, dict):
                continue
            char_id = character.get("character_id")
            core_traits = character.get("core_traits")
            if (
                not isinstance(char_id, str)
                or char_id not in reference_traits
                or not isinstance(core_traits, list)
            ):
                continue
            current_traits = {
                _normalize_token(trait)
                for trait in core_traits
                if isinstance(trait, str) and trait.strip()
            }
            if not current_traits:
                overlap_scores.append(0.0)
                continue
            overlap = _safe_div(len(current_traits & reference_traits[char_id]), len(reference_traits[char_id]))
            overlap_scores.append(overlap)

    score = _safe_div(sum(overlap_scores), len(overlap_scores)) if overlap_scores else 0.0
    return round(score, 3), {"comparisons": len(overlap_scores)}


def _compute_visual_similarity(output: dict) -> tuple[float, dict]:
    shots = [shot for shot in output.get("shots", []) if isinstance(shot, dict)]
    if len(shots) <= 1:
        return 1.0, {"pairs": 0}

    pair_scores: list[float] = []
    for idx in range(1, len(shots)):
        previous = shots[idx - 1].get("consistency_constraints")
        current = shots[idx].get("consistency_constraints")
        if not isinstance(previous, dict) or not isinstance(current, dict):
            pair_scores.append(0.0)
            continue

        prev_palette = {
            _normalize_token(color)
            for color in (previous.get("color_palette") or [])
            if isinstance(color, str) and color.strip()
        }
        curr_palette = {
            _normalize_token(color)
            for color in (current.get("color_palette") or [])
            if isinstance(color, str) and color.strip()
        }
        palette_score = 1.0 if not prev_palette and not curr_palette else _safe_div(
            len(prev_palette & curr_palette),
            len(prev_palette | curr_palette),
        )

        prev_lighting = str(previous.get("lighting_style") or "")
        curr_lighting = str(current.get("lighting_style") or "")
        lighting_score = 1.0 if _normalize_token(prev_lighting) == _normalize_token(curr_lighting) else 0.0
        pair_scores.append((palette_score * 0.6) + (lighting_score * 0.4))

    score = _safe_div(sum(pair_scores), len(pair_scores)) if pair_scores else 0.0
    return round(score, 3), {"pairs": len(pair_scores)}


def _compute_tension_progression(output: dict) -> tuple[float, dict]:
    shots = [shot for shot in output.get("shots", []) if isinstance(shot, dict)]
    tensions: list[float] = []
    max_allowed_jump = float(DEFAULT_QUALITY_GATES["max_tension_jump"])

    for shot in shots:
        packet = shot.get("consistency_packet")
        if not isinstance(packet, dict):
            continue
        narrative = packet.get("narrative_continuity")
        if isinstance(narrative, dict) and isinstance(narrative.get("tension_level"), (int, float)):
            tensions.append(float(narrative["tension_level"]))
        gates = packet.get("quality_gates")
        if isinstance(gates, dict) and isinstance(gates.get("max_tension_jump"), (int, float)):
            max_allowed_jump = float(gates["max_tension_jump"])

    if len(tensions) <= 1:
        return 1.0, {"steps": 0, "max_observed_jump": 0.0}

    non_decreasing_steps = 0
    jumps: list[float] = []
    excess_penalties: list[float] = []
    jump_scale = max(1.0, 10.0 - max_allowed_jump)

    for idx in range(1, len(tensions)):
        diff = tensions[idx] - tensions[idx - 1]
        if diff >= 0:
            non_decreasing_steps += 1
        jump = abs(diff)
        jumps.append(jump)
        excess = max(0.0, jump - max_allowed_jump)
        excess_penalties.append(min(1.0, excess / jump_scale))

    trend_score = _safe_div(non_decreasing_steps, len(tensions) - 1)
    jump_score = 1.0 - _safe_div(sum(excess_penalties), len(excess_penalties))
    progression = (trend_score * 0.6) + (jump_score * 0.4)

    return round(progression, 3), {
        "steps": len(tensions) - 1,
        "non_decreasing_steps": non_decreasing_steps,
        "max_observed_jump": round(max(jumps) if jumps else 0.0, 3),
    }


def _compute_trope_repetition_ratio(output: dict) -> float:
    shots = [shot for shot in output.get("shots", []) if isinstance(shot, dict)]
    descriptions = [
        _normalize_token(str(shot.get("description") or ""))
        for shot in shots
        if str(shot.get("description") or "").strip()
    ]
    if not descriptions:
        return 0.0
    unique = len(set(descriptions))
    return round(max(0.0, 1.0 - _safe_div(unique, len(descriptions))), 3)


def build_coherence_metrics(
    scene_doc: dict,
    consistency_report: list[dict] | None = None,
    *,
    export_json: bool = False,
    output_dir: str = "outputs",
) -> dict:
    """Calcule des sous-scores de cohérence exploitables et un score global."""
    output = scene_doc.get("output")
    if not isinstance(output, dict):
        raise ValueError("scene_doc.output doit être un objet.")

    traits_score, traits_details = _compute_character_trait_alignment(output)
    visual_score, visual_details = _compute_visual_similarity(output)
    tension_score, tension_details = _compute_tension_progression(output)
    trope_repetition_ratio = _compute_trope_repetition_ratio(output)

    global_score = round((traits_score * 0.4) + (visual_score * 0.35) + (tension_score * 0.25), 3)
    metrics = {
        "request_id": scene_doc.get("request_id", "unknown_request"),
        "coherence_score": global_score,
        "subscores": {
            "character_trait_alignment": traits_score,
            "visual_palette_lighting_similarity": visual_score,
            "narrative_tension_progression": tension_score,
        },
        "max_tension_jump": float(tension_details["max_observed_jump"]),
        "trope_repetition_ratio": trope_repetition_ratio,
        "details": {
            "character_trait_alignment": traits_details,
            "visual_palette_lighting_similarity": visual_details,
            "narrative_tension_progression": tension_details,
            "consistency_issue_count": len(consistency_report or []),
        },
    }

    if export_json:
        request_id = str(scene_doc.get("request_id") or "unknown_request")
        write_json_utf8(f"{output_dir}/coherence_metrics.json", metrics)
        write_json_utf8(f"{output_dir}/coherence_metrics_{request_id}.json", metrics)

    return metrics


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

    _apply_enrichment(enriched_doc)

    write_json_utf8("outputs/scene_enriched.json", enriched_doc)

    consistency_report = build_consistency_report(enriched_doc)

    return {
        "enriched_doc": enriched_doc,
        "consistency_report": consistency_report,
    }
