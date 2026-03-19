"""Tests unitaires du moteur de cohérence."""

from __future__ import annotations

from copy import deepcopy

from src.core.consistency_engine import build_consistency_report, enrich, has_blocking_violations
from src.core.story_engine import StoryEngine


def _narrative() -> dict:
    return StoryEngine().generate("Prompt de test pour la cohérence.")


def test_rule_character_ids_detects_unknown_shot_reference() -> None:
    narrative = _narrative()
    narrative["output"]["shots"][0]["character_ids"] = ["char_1", "char_999"]

    consistency_result = enrich(narrative)
    report = consistency_result["consistency_report"]

    assert any(
        issue["rule_id"] == "character_ids_consistency"
        and issue["severity"] == "error"
        and "char_999" in issue["message"]
        for issue in report
    )
    assert has_blocking_violations(report)


def test_rule_visual_constraints_presence_flags_missing_constraints() -> None:
    narrative = _narrative()

    report = build_consistency_report(narrative)

    assert any(
        issue["rule_id"] == "visual_constraints_presence"
        and issue["severity"] == "error"
        and "absentes" in issue["message"]
        for issue in report
    )


def test_rule_scene_shot_order_detects_reordered_scenes() -> None:
    narrative = _narrative()
    narrative["output"]["scenes"] = [
        {"id": "scene_1", "summary": "A", "duration_sec": 20},
        {"id": "scene_2", "summary": "B", "duration_sec": 20},
    ]
    narrative["output"]["shots"] = [
        {"id": "shot_001", "scene_id": "scene_2", "description": "D", "duration_sec": 10},
        {"id": "shot_002", "scene_id": "scene_1", "description": "E", "duration_sec": 10},
    ]

    consistency_result = enrich(narrative)
    report = consistency_result["consistency_report"]

    assert any(
        issue["rule_id"] == "scene_shot_order"
        and issue["severity"] == "warning"
        and "Ordre des shots" in issue["message"]
        for issue in report
    )
    assert not has_blocking_violations(report)


def test_enrich_preserves_topology_of_scenes_and_shots() -> None:
    narrative = _narrative()
    before = deepcopy(narrative)

    enriched = enrich(narrative)["enriched_doc"]

    before_scene_ids = [scene["id"] for scene in before["output"]["scenes"]]
    after_scene_ids = [scene["id"] for scene in enriched["output"]["scenes"]]
    assert before_scene_ids == after_scene_ids

    before_shot_ids = [shot["id"] for shot in before["output"]["shots"]]
    after_shot_ids = [shot["id"] for shot in enriched["output"]["shots"]]
    assert before_shot_ids == after_shot_ids

    before_scene_by_shot = [shot["scene_id"] for shot in before["output"]["shots"]]
    after_scene_by_shot = [shot["scene_id"] for shot in enriched["output"]["shots"]]
    assert before_scene_by_shot == after_scene_by_shot


def test_enrich_keeps_narrative_sort_order_stable() -> None:
    narrative = _narrative()

    before_pairs = [
        (scene["id"], scene.get("duration_sec"))
        for scene in narrative["output"]["scenes"]
    ]
    before_shot_pairs = [
        (shot["id"], shot.get("scene_id"), shot.get("duration_sec"))
        for shot in narrative["output"]["shots"]
    ]

    enriched = enrich(narrative)["enriched_doc"]

    after_pairs = [
        (scene["id"], scene.get("duration_sec"))
        for scene in enriched["output"]["scenes"]
    ]
    after_shot_pairs = [
        (shot["id"], shot.get("scene_id"), shot.get("duration_sec"))
        for shot in enriched["output"]["shots"]
    ]

    assert after_pairs == before_pairs
    assert after_shot_pairs == before_shot_pairs
