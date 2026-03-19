"""Journalisation minimale des étapes du pipeline Narratech."""

from __future__ import annotations

from src.core.pipeline_state import PipelineTransitionEvent

PREFIX = "[Narratech]"


def log_step(message: str) -> None:
    """Affiche un message d'étape avec un format constant."""
    text = str(message).strip()
    print(f"{PREFIX} {text}")


def log_transition(event: PipelineTransitionEvent) -> None:
    """Journalise une transition d'état avec timestamp et raison."""
    print(
        (
            f"{PREFIX} transition={event.from_stage.value}->{event.to_stage.value} "
            f"request_id={event.request_id} timestamp={event.timestamp} reason={event.reason}"
        )
    )
