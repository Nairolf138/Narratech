"""Tests de non-régression de personnalisation pour profils extrêmes."""

from __future__ import annotations

from src.core.story_engine import StoryEngine
from src.generation.asset_generator import generate as generate_assets
from src.generation.shot_generator import generate as generate_shots


def _scene_doc() -> dict:
    return {
        "request_id": "req_profile_1",
        "output": {
            "synopsis": "Synopsis",
            "characters": [{"id": "char_1", "name": "Mia", "role": "protagonist"}],
            "scenes": [{"id": "scene_1", "summary": "Résumé", "duration_sec": 45}],
            "shots": [{"id": "shot_001", "scene_id": "scene_1", "description": "Plan", "duration_sec": 5.0}],
        },
    }


def test_personalization_profile_jeunesse_is_applied_in_pipeline_traces() -> None:
    profile = {
        "preferences": {
            "genre": "adventure",
            "ambiance": "uplifting",
            "rhythm": "fast",
            "duration_sec": 30,
            "language": "fr",
        },
        "constraints": {
            "age_rating": "7+",
            "culture": "global",
            "exclusions": ["violence"],
        },
        "identity": {"session_id": "session_kids_001"},
    }

    narrative = StoryEngine().generate("Une chasse au trésor amusante.", request_id="req_kids", user_profile=profile)
    asset_refs = generate_assets(_scene_doc(), user_profile=profile)
    clips = generate_shots(_scene_doc(), asset_refs=asset_refs, user_profile=profile)

    assert narrative["input"]["language"] == "fr"
    assert narrative["input"]["style"] == "adventure"
    assert asset_refs[0]["personalization"]["age_rating"] == "7+"
    assert clips[0]["personalization"]["rhythm"] == "fast"


def test_personalization_profile_adulte_with_exclusions_is_non_regression() -> None:
    profile = {
        "preferences": {
            "genre": "drama",
            "ambiance": "tense",
            "rhythm": "slow",
            "duration_sec": 90,
            "language": "fr",
        },
        "constraints": {
            "age_rating": "18+",
            "culture": "western",
            "exclusions": ["nudity", "gore"],
        },
        "identity": {"session_id": "session_adult_001"},
    }

    narrative = StoryEngine().generate("Un drame psychologique.", request_id="req_adult", user_profile=profile)
    assert narrative["input"]["style"] == "drama"
    assert narrative["input"]["duration_sec"] == 90


def test_personalization_profile_multilingue_is_applied_in_narrative_and_clips() -> None:
    profile = {
        "preferences": {
            "genre": "comedy",
            "ambiance": "light",
            "rhythm": "medium",
            "duration_sec": 45,
            "language": "es",
        },
        "constraints": {
            "age_rating": "all",
            "culture": "latam",
            "exclusions": [],
        },
        "identity": {"session_id": "session_multi_001"},
    }

    narrative = StoryEngine().generate("Historia corta.", request_id="req_multi", user_profile=profile)
    clips = generate_shots(_scene_doc(), user_profile=profile)

    assert narrative["input"]["language"] == "es"
    assert clips[0]["personalization"]["language"] == "es"
