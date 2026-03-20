"""Tests unitaires du moteur de cohérence."""

from __future__ import annotations

from copy import deepcopy

from src.core.consistency_engine import (
    build_coherence_metrics,
    build_consistency_packet,
    build_consistency_report,
    enrich,
    has_blocking_violations,
)
from src.core.schema_validator import ENRICHED_SCHEMA_PATH, validate_narrative_document
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


def test_build_consistency_packet_has_required_minimal_fields() -> None:
    narrative = _narrative()

    packet = build_consistency_packet(narrative)

    assert "consistency_packet_version" in packet
    assert "characters" in packet
    assert "visual_continuity" in packet
    assert "narrative_continuity" in packet
    assert "quality_gates" in packet


def test_enrich_injects_consistency_packet_in_each_shot() -> None:
    narrative = _narrative()

    enriched = enrich(narrative)["enriched_doc"]
    shots = enriched["output"]["shots"]

    assert shots
    for shot in shots:
        assert "consistency_packet" in shot
        packet = shot["consistency_packet"]
        assert packet["consistency_packet_version"] == "1.0"
        assert isinstance(packet["characters"], list)
        assert isinstance(packet["visual_continuity"], dict)
        assert isinstance(packet["narrative_continuity"], dict)
        assert isinstance(packet["quality_gates"], dict)


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


def test_rule_traits_overlap_is_blocking_when_below_threshold() -> None:
    narrative = _narrative()
    enriched = enrich(narrative)["enriched_doc"]
    shots = enriched["output"]["shots"]
    assert len(shots) >= 2

    shots[1]["consistency_packet"]["characters"][0]["core_traits"] = ["incoherent_trait"]

    report = build_consistency_report(enriched)

    assert any(
        issue["rule_id"] == "traits_overlap"
        and issue["severity"] == "error"
        and "Overlap de traits insuffisant" in issue["message"]
        for issue in report
    )
    assert has_blocking_violations(report)


def test_rule_period_anachronism_is_blocking() -> None:
    narrative = _narrative()
    enriched = enrich(narrative)["enriched_doc"]
    shot = enriched["output"]["shots"][0]
    shot["consistency_packet"]["visual_continuity"]["period_banned_items"] = ["hologramme futuriste"]
    shot["description"] = "Un hologramme futuriste apparaît au centre de la scène."

    report = build_consistency_report(enriched)

    assert any(
        issue["rule_id"] == "period_anachronism"
        and issue["severity"] == "error"
        and "Anachronisme détecté" in issue["message"]
        for issue in report
    )
    assert has_blocking_violations(report)


def test_rule_tension_jump_is_non_blocking_warning_without_twist() -> None:
    narrative = _narrative()
    enriched = enrich(narrative)["enriched_doc"]
    shots = enriched["output"]["shots"]
    assert len(shots) >= 2

    shots[0]["consistency_packet"]["narrative_continuity"]["tension_level"] = 1
    shots[1]["consistency_packet"]["narrative_continuity"]["tension_level"] = 9
    shots[0]["consistency_packet"]["narrative_continuity"]["twist_flag"] = False
    shots[1]["consistency_packet"]["narrative_continuity"]["twist_flag"] = False

    report = build_consistency_report(enriched)

    assert any(
        issue["rule_id"] == "tension_jump"
        and issue["severity"] == "warning"
        and "Saut de tension trop fort" in issue["message"]
        for issue in report
    )
    assert not has_blocking_violations([issue for issue in report if issue["rule_id"] == "tension_jump"])


def test_rule_causal_order_is_blocking_on_inverted_sequence() -> None:
    narrative = _narrative()
    enriched = enrich(narrative)["enriched_doc"]
    shot = enriched["output"]["shots"][0]
    shot["consistency_packet"]["narrative_continuity"]["action_sequence"] = [
        "repérage entrée nord",
        "passage contrôle",
        "accès salle technique",
    ]
    shot["description"] = "Alex réalise un accès salle technique immédiat."

    report = build_consistency_report(enriched)

    assert any(
        issue["rule_id"] == "causal_order"
        and issue["severity"] == "error"
        and "Ordre causal violé" in issue["message"]
        for issue in report
    )
    assert has_blocking_violations(report)


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


def test_enrich_outputs_document_valid_against_enriched_schema() -> None:
    narrative = _narrative()

    enriched = enrich(narrative)["enriched_doc"]

    validate_narrative_document(enriched, schema_path=ENRICHED_SCHEMA_PATH)


def test_build_coherence_metrics_returns_subscores_and_global_score() -> None:
    narrative = _narrative()
    enriched = enrich(narrative)["enriched_doc"]
    report = build_consistency_report(enriched)

    metrics = build_coherence_metrics(enriched, report)

    assert metrics["coherence_score"] >= 0.0
    assert metrics["coherence_score"] <= 1.0
    assert set(metrics["subscores"].keys()) == {
        "character_trait_alignment",
        "visual_palette_lighting_similarity",
        "narrative_tension_progression",
    }
    assert "details" in metrics


def test_build_coherence_metrics_can_export_json_per_run(tmp_path) -> None:
    narrative = _narrative()
    narrative["request_id"] = "req_test_metrics"
    enriched = enrich(narrative)["enriched_doc"]
    report = build_consistency_report(enriched)

    build_coherence_metrics(enriched, report, export_json=True, output_dir=tmp_path.as_posix())

    assert (tmp_path / "coherence_metrics.json").exists()
    assert (tmp_path / "coherence_metrics_req_test_metrics.json").exists()
