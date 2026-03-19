"""Journalisation minimale des étapes du pipeline Narratech."""

from __future__ import annotations


PREFIX = "[Narratech]"


def log_step(message: str) -> None:
    """Affiche un message d'étape avec un format constant."""
    text = str(message).strip()
    print(f"{PREFIX} {text}")
