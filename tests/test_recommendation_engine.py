from __future__ import annotations

import json
from pathlib import Path

from src.core.recommendation_engine import RecommendationEngine, RecommendationHistoryStore


def test_recommendation_engine_increases_tension_and_variety_from_feedback(tmp_path: Path) -> None:
    store = RecommendationHistoryStore(path=tmp_path / "history.json", max_items_per_user=3)
    engine = RecommendationEngine(history_store=store)

    recommendation = engine.recommend(
        user_id="user_1",
        generated_content={"output": {"shots": [{"id": "shot_001"}]}},
        user_feedback={"wants_more_tension": True, "repetitive_tropes": True},
        coherence_metrics={"coherence_score": 0.95, "trope_repetition_ratio": 0.5},
        request_id="req_001",
    )

    assert recommendation.tension == "increase"
    assert recommendation.trope_variety == "increase"
    assert recommendation.recommendation_policy_version == "recommendation_policy_v1"
    assert recommendation.applied_signals
    assert recommendation.recommended_instructions

    history = json.loads((tmp_path / "history.json").read_text(encoding="utf-8"))
    assert "user_1" in history
    assert history["user_1"][0]["request_id"] == "req_001"


def test_recommendation_history_is_trimmed_per_user(tmp_path: Path) -> None:
    store = RecommendationHistoryStore(path=tmp_path / "history.json", max_items_per_user=2)

    for idx in range(4):
        store.append(user_id="user_2", event={"request_id": f"req_{idx}"})

    kept = store.recent(user_id="user_2")
    assert [item["request_id"] for item in kept] == ["req_2", "req_3"]


def test_same_feedback_input_produces_same_recommendation(tmp_path: Path) -> None:
    store = RecommendationHistoryStore(path=tmp_path / "history.json", max_items_per_user=10)
    engine = RecommendationEngine(history_store=store)
    feedback = {"wants_more_tension": True, "confusing_arcs": True, "repetitive_tropes": False}
    metrics = {"coherence_score": 0.7, "max_tension_jump": 1.0, "trope_repetition_ratio": 0.1}

    rec_a = engine.recommend(
        user_id="same_user",
        generated_content={"output": {"shots": []}},
        user_feedback=feedback,
        coherence_metrics=metrics,
        request_id="req_a",
    )
    rec_b = engine.recommend(
        user_id="same_user",
        generated_content={"output": {"shots": []}},
        user_feedback=feedback,
        coherence_metrics=metrics,
        request_id="req_b",
    )

    assert rec_a.to_dict() == rec_b.to_dict()
