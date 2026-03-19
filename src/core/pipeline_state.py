"""Modèle d'état du pipeline Narratech."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


def _utc_now_iso() -> str:
    """Retourne un timestamp ISO-8601 en UTC."""
    return datetime.now(UTC).isoformat()


class PipelineStage(StrEnum):
    """États possibles du pipeline de génération."""

    INIT = "init"
    PROMPT_LOADED = "prompt_loaded"
    STORY_GENERATED = "story_generated"
    NARRATIVE_VALIDATED = "narrative_validated"
    CONSISTENCY_ENRICHED = "consistency_enriched"
    ASSETS_GENERATED = "assets_generated"
    SHOTS_GENERATED = "shots_generated"
    FINAL_ASSEMBLED = "final_assembled"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(slots=True)
class PipelineTransitionEvent:
    """Événement de transition entre deux états du pipeline."""

    request_id: str
    from_stage: PipelineStage
    to_stage: PipelineStage
    reason: str
    timestamp: str = field(default_factory=_utc_now_iso)


@dataclass(slots=True)
class PipelineRuntimeState:
    """État runtime persistant du pipeline."""

    request_id: str
    current_stage: PipelineStage = PipelineStage.INIT
    transitions: list[PipelineTransitionEvent] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)
    retries: dict[str, int] = field(default_factory=dict)
    failed_stage: str | None = None

    def transition(self, *, to_stage: PipelineStage, reason: str) -> PipelineTransitionEvent:
        """Applique une transition d'état et retourne l'événement associé."""
        event = PipelineTransitionEvent(
            request_id=self.request_id,
            from_stage=self.current_stage,
            to_stage=to_stage,
            reason=reason,
        )
        self.current_stage = to_stage
        self.transitions.append(event)
        return event

    def register_retry(self, *, stage: PipelineStage, reason: str) -> None:
        """Incrémente le compteur de retry pour une étape."""
        stage_key = stage.value
        self.retries[stage_key] = self.retries.get(stage_key, 0) + 1
        self.errors.append(
            {
                "timestamp": _utc_now_iso(),
                "stage": stage_key,
                "reason": f"retry: {reason}",
            }
        )

    def register_error(self, *, stage: PipelineStage, reason: str) -> None:
        """Enregistre une erreur métier/technique."""
        self.errors.append(
            {
                "timestamp": _utc_now_iso(),
                "stage": stage.value,
                "reason": reason,
            }
        )

    def mark_failed(self, *, stage: PipelineStage, reason: str) -> PipelineTransitionEvent:
        """Marque l'échec global du pipeline."""
        self.failed_stage = stage.value
        self.register_error(stage=stage, reason=reason)
        return self.transition(to_stage=PipelineStage.FAILED, reason=reason)

    def to_dict(self) -> dict:
        """Sérialise l'état runtime dans un format JSON stable."""
        return {
            "request_id": self.request_id,
            "current_stage": self.current_stage.value,
            "failed_stage": self.failed_stage,
            "errors": list(self.errors),
            "retries": dict(self.retries),
            "transitions": [
                {
                    "request_id": event.request_id,
                    "from_stage": event.from_stage.value,
                    "to_stage": event.to_stage.value,
                    "reason": event.reason,
                    "timestamp": event.timestamp,
                }
                for event in self.transitions
            ],
        }
