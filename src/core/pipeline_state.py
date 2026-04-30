"""Modèle d'état du pipeline Narratech."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
import json
from pathlib import Path


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
    DONE_WITH_WARNINGS = "done_with_warnings"
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
    retry_events: list[dict[str, str | int]] = field(default_factory=list)
    degraded_shots: int = 0
    total_shots: int = 0
    failed_stage: str | None = None

    @property
    def degraded_ratio(self) -> float:
        """Retourne le ratio de shots dégradés."""
        if self.total_shots <= 0:
            return 0.0
        return self.degraded_shots / self.total_shots

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

    def register_retry_event(
        self,
        *,
        stage: PipelineStage,
        reason: str,
        scope_type: str,
        scope_id: str,
        attempt: int,
    ) -> None:
        """Enregistre le détail d'un retry ciblé."""
        self.register_retry(stage=stage, reason=reason)
        self.retry_events.append(
            {
                "timestamp": _utc_now_iso(),
                "stage": stage.value,
                "scope_type": scope_type,
                "scope_id": scope_id,
                "attempt": attempt,
                "reason": reason,
            }
        )

    def set_degradation(self, *, total_shots: int, degraded_shots: int) -> None:
        """Met à jour les métriques de qualité dégradée."""
        self.total_shots = max(0, total_shots)
        self.degraded_shots = max(0, min(degraded_shots, self.total_shots))

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
            "retry_events": list(self.retry_events),
            "degraded_shots": self.degraded_shots,
            "total_shots": self.total_shots,
            "degraded_ratio": self.degraded_ratio,
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

    @classmethod
    def from_dict(cls, payload: dict) -> PipelineRuntimeState:
        """Construit l'état depuis une structure JSON."""
        transitions: list[PipelineTransitionEvent] = []
        for raw_event in payload.get("transitions", []):
            if not isinstance(raw_event, dict):
                continue
            transitions.append(
                PipelineTransitionEvent(
                    request_id=str(raw_event.get("request_id", payload.get("request_id", ""))),
                    from_stage=PipelineStage(str(raw_event.get("from_stage", PipelineStage.INIT.value))),
                    to_stage=PipelineStage(str(raw_event.get("to_stage", PipelineStage.INIT.value))),
                    reason=str(raw_event.get("reason", "")),
                    timestamp=str(raw_event.get("timestamp", _utc_now_iso())),
                )
            )

        return cls(
            request_id=str(payload.get("request_id", "")),
            current_stage=PipelineStage(str(payload.get("current_stage", PipelineStage.INIT.value))),
            transitions=transitions,
            errors=[item for item in payload.get("errors", []) if isinstance(item, dict)],
            retries={str(k): int(v) for k, v in dict(payload.get("retries", {})).items()},
            retry_events=[item for item in payload.get("retry_events", []) if isinstance(item, dict)],
            degraded_shots=int(payload.get("degraded_shots", 0)),
            total_shots=int(payload.get("total_shots", 0)),
            failed_stage=str(payload.get("failed_stage")) if payload.get("failed_stage") else None,
        )

    @staticmethod
    def read_json_file(path: str | Path) -> dict | list:
        """Lit un fichier JSON."""
        with Path(path).open("r", encoding="utf-8") as stream:
            payload = json.load(stream)
        return payload
