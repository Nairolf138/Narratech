"""Tests dédiés à la validation du schéma narratif V1."""

from __future__ import annotations

import pytest

from src.core.schema_validator import NarrativeValidationError, validate_narrative_document
from src.core.story_engine import StoryEngine


def _valid_narrative() -> dict:
    return StoryEngine().generate("Une histoire courte et cohérente.")


def test_validate_narrative_document_valid_case() -> None:
    """Un document conforme au schéma doit être accepté."""
    narrative = _valid_narrative()
    validate_narrative_document(narrative)


def test_validate_narrative_document_missing_required_field() -> None:
    """Un champ requis manquant doit être refusé."""
    narrative = _valid_narrative()
    narrative.pop("request_id", None)

    with pytest.raises(NarrativeValidationError, match="champ obligatoire manquant 'request_id'"):
        validate_narrative_document(narrative)


def test_validate_narrative_document_invalid_type() -> None:
    """Un type invalide doit être refusé."""
    narrative = _valid_narrative()
    narrative["output"]["render_plan"]["fps"] = "24"

    with pytest.raises(NarrativeValidationError, match="type attendu integer"):
        validate_narrative_document(narrative)
