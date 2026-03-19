"""Chargement déterministe du prompt utilisateur."""

from __future__ import annotations

DEFAULT_PROMPT = "Raconte une courte histoire de science-fiction en 3 phrases."


def load_prompt(argv: list[str]) -> str:
    """Retourne le prompt issu des arguments, sinon un prompt par défaut.

    Règle simple et déterministe:
    - si au moins un argument texte est fourni, il est utilisé comme prompt;
    - sinon, on utilise un prompt hardcodé.
    """
    return argv[0] if argv else DEFAULT_PROMPT
