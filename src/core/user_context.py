"""Schéma d'entrée user/session avec défauts sûrs et validation stricte."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from src.core.schema_validator import NarrativeValidationError, validate_narrative_document


USER_CONTEXT_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "user_context.v1.schema.json"

SAFE_DEFAULT_USER_CONTEXT: dict[str, Any] = {
    "preferences": {
        "genre": "general",
        "ambiance": "neutral",
        "rhythm": "medium",
        "duration_sec": 60,
        "language": "fr",
    },
    "constraints": {
        "age_rating": "13+",
        "culture": "global",
        "exclusions": [],
    },
    "identity": {
        "session_id": "session_default",
    },
}


def build_user_context(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Construit un contexte utilisateur strict avec valeurs par défaut sûres.

    - fusion profonde contrôlée (3 niveaux: racine → section → champ)
    - validation stricte via JSON Schema (`additionalProperties: false`)
    """
    payload = payload or {}
    context = deepcopy(SAFE_DEFAULT_USER_CONTEXT)

    for section in ("preferences", "constraints", "identity"):
        if section in payload:
            section_payload = payload[section]
            if not isinstance(section_payload, dict):
                raise NarrativeValidationError(
                    f"$.{section}: type attendu object, valeur reçue {type(section_payload).__name__}."
                )
            context[section].update(section_payload)

    validate_user_context(context)
    return context


def validate_user_context(document: dict[str, Any]) -> None:
    """Valide un document user-context contre `user_context.v1`.

    Réutilise le validateur de schéma local pour garantir un comportement cohérent.
    """
    validate_narrative_document(document=document, schema_path=USER_CONTEXT_SCHEMA_PATH)
