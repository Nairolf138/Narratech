"""Tests du schéma de contexte utilisateur/session."""

from __future__ import annotations

import pytest

from src.core.schema_validator import NarrativeValidationError
from src.core.user_context import build_user_context, validate_user_context


def test_build_user_context_uses_safe_defaults() -> None:
    context = build_user_context()

    assert context["preferences"]["genre"] == "general"
    assert context["preferences"]["duration_sec"] == 60
    assert context["constraints"]["age_rating"] == "13+"
    assert context["constraints"]["exclusions"] == []
    assert context["identity"]["session_id"] == "session_default"


def test_build_user_context_allows_partial_override() -> None:
    context = build_user_context(
        {
            "preferences": {"language": "en", "rhythm": "fast"},
            "constraints": {"exclusions": ["violence"]},
            "identity": {"session_id": "session_abc123", "user_id": "user_xyz789"},
        }
    )

    assert context["preferences"]["language"] == "en"
    assert context["preferences"]["rhythm"] == "fast"
    assert context["constraints"]["exclusions"] == ["violence"]
    assert context["identity"]["user_id"] == "user_xyz789"


def test_validate_user_context_rejects_unknown_property() -> None:
    with pytest.raises(NarrativeValidationError, match="propriétés non autorisées"):
        validate_user_context(
            {
                "preferences": {
                    "genre": "general",
                    "ambiance": "neutral",
                    "rhythm": "medium",
                    "duration_sec": 60,
                    "language": "fr",
                    "mood": "extra",
                },
                "constraints": {"age_rating": "13+", "culture": "global", "exclusions": []},
                "identity": {"session_id": "session_abcdef"},
            }
        )


def test_validate_user_context_rejects_invalid_enum_and_pattern() -> None:
    with pytest.raises(NarrativeValidationError, match="valeur attendue dans"):
        build_user_context({"preferences": {"genre": "horror"}})

    with pytest.raises(NarrativeValidationError, match="motif attendu"):
        build_user_context({"identity": {"session_id": "bad session id"}})
