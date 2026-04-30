"""Gestion du flux de feedback utilisateur inter-générations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from src.core.io_utils import write_json_utf8

DEFAULT_FEEDBACK_HISTORY_PATH = Path("outputs/feedback_history.json")
DEFAULT_FEEDBACK_AUDIT_PATH = Path("outputs/feedback_audit.json")
DEFAULT_UI_FEEDBACK_PATH = Path("outputs/ui_exchange/post_watch_feedback.jsonl")


@dataclass(slots=True)
class SessionAdjustments:
    """Ajustements calculés à réutiliser sur la génération suivante."""

    rhythm: str
    style: str
    story: str
    instructions: list[str]
    rationale: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "rhythm": self.rhythm,
            "style": self.style,
            "story": self.story,
            "instructions": list(self.instructions),
            "rationale": list(self.rationale),
        }


class FeedbackStore:
    """Persistance JSON structurée du feedback, liée à chaque génération."""

    def __init__(self, path: Path | str = DEFAULT_FEEDBACK_HISTORY_PATH, max_items_per_session: int = 20) -> None:
        self.path = Path(path)
        self.max_items_per_session = max(1, max_items_per_session)

    def _load(self) -> dict[str, list[dict[str, Any]]]:
        if not self.path.exists():
            return {}
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {}
        return {
            str(session_id): list(entries)
            for session_id, entries in raw.items()
            if isinstance(entries, list)
        }

    def append(self, *, session_id: str, event: dict[str, Any]) -> None:
        history = self._load()
        entries = history.setdefault(session_id, [])
        entries.append(event)
        history[session_id] = entries[-self.max_items_per_session :]
        write_json_utf8(self.path.as_posix(), history)

    def recent(self, *, session_id: str) -> list[dict[str, Any]]:
        return list(self._load().get(session_id, []))


class FeedbackAuditStore:
    """Journal d'audit des décisions d'ajustement automatiques."""

    def __init__(self, path: Path | str = DEFAULT_FEEDBACK_AUDIT_PATH, max_items: int = 200) -> None:
        self.path = Path(path)
        self.max_items = max(1, max_items)

    def _load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        return list(raw) if isinstance(raw, list) else []

    def append(self, event: dict[str, Any]) -> None:
        events = self._load()
        events.append(event)
        write_json_utf8(self.path.as_posix(), events[-self.max_items :])

    def recent(self) -> list[dict[str, Any]]:
        return self._load()


class FeedbackEngine:
    """Capture feedback + règles d'ajustement + audit."""

    def __init__(
        self,
        feedback_store: FeedbackStore | None = None,
        audit_store: FeedbackAuditStore | None = None,
    ) -> None:
        self.feedback_store = feedback_store or FeedbackStore()
        self.audit_store = audit_store or FeedbackAuditStore()

    def build_user_context_from_ui_feedback(
        self,
        *,
        path: Path | str = DEFAULT_UI_FEEDBACK_PATH,
        max_events: int = 20,
    ) -> dict[str, Any]:
        target = Path(path)
        if not target.exists():
            return {
                "source": target.as_posix(),
                "event_count": 0,
                "average_global_note": 0.0,
                "preference_signals": {
                    "wants_more_tension": False,
                    "confusing_arcs": False,
                    "repetitive_tropes": False,
                },
            }

        events: list[dict[str, Any]] = []
        for line in target.read_text(encoding="utf-8").splitlines():
            raw_line = line.strip()
            if not raw_line:
                continue
            payload = json.loads(raw_line)
            if isinstance(payload, dict):
                events.append(payload)
        recent = events[-max(1, max_events) :]
        normalized = [self._normalize_feedback_payload(event) for event in recent]

        notes = [item["global_note"] for item in normalized]
        avg_note = round(sum(notes) / len(notes), 3) if notes else 0.0
        comment_blob = " ".join(item["commentaire"] for item in normalized).lower()
        avg_story = self._average_dimension(normalized, "histoire")
        avg_style = self._average_dimension(normalized, "style")
        avg_rhythm = self._average_dimension(normalized, "rythme")

        return {
            "source": target.as_posix(),
            "event_count": len(normalized),
            "average_global_note": avg_note,
            "dimensions_average": {
                "histoire": avg_story,
                "style": avg_style,
                "rythme": avg_rhythm,
            },
            "preference_signals": {
                "wants_more_tension": avg_rhythm >= 4.0 or "plus de tension" in comment_blob,
                "confusing_arcs": avg_story <= 2.0 or "confus" in comment_blob,
                "repetitive_tropes": "répétitif" in comment_blob or "repetitif" in comment_blob,
            },
        }

    def _average_dimension(self, normalized: list[dict[str, Any]], key: str) -> float:
        values = [item["dimensions"][key] for item in normalized]
        return round(sum(values) / len(values), 3) if values else 0.0

    def _normalize_feedback_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        dimensions = payload.get("dimensions") if isinstance(payload.get("dimensions"), dict) else {}
        return {
            "global_note": max(0, min(int(payload.get("global_note", 0) or 0), 5)),
            "dimensions": {
                "histoire": max(0, min(int(dimensions.get("histoire", 0) or 0), 5)),
                "style": max(0, min(int(dimensions.get("style", 0) or 0), 5)),
                "rythme": max(0, min(int(dimensions.get("rythme", 0) or 0), 5)),
            },
            "commentaire": str(payload.get("commentaire", "")).strip(),
        }

    def capture_feedback(
        self,
        *,
        request_id: str,
        session_id: str,
        feedback_payload: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if not isinstance(feedback_payload, dict):
            return None

        global_note = int(feedback_payload.get("global_note", 0) or 0)
        dimensions = feedback_payload.get("dimensions")
        if not isinstance(dimensions, dict):
            return None

        score_story = int(dimensions.get("histoire", 0) or 0)
        score_style = int(dimensions.get("style", 0) or 0)
        score_rhythm = int(dimensions.get("rythme", 0) or 0)

        event = {
            "timestamp": datetime.now(UTC).isoformat(),
            "request_id": request_id,
            "session_id": session_id,
            "feedback": {
                "global_note": max(0, min(global_note, 5)),
                "dimensions": {
                    "histoire": max(0, min(score_story, 5)),
                    "style": max(0, min(score_style, 5)),
                    "rythme": max(0, min(score_rhythm, 5)),
                },
                "commentaire": str(feedback_payload.get("commentaire", "")).strip(),
            },
        }
        self.feedback_store.append(session_id=session_id, event=event)
        return event

    def derive_adjustments(self, *, feedback_event: dict[str, Any]) -> SessionAdjustments:
        feedback = feedback_event.get("feedback", {}) if isinstance(feedback_event, dict) else {}
        dimensions = feedback.get("dimensions", {}) if isinstance(feedback, dict) else {}

        story_score = int(dimensions.get("histoire", 0) or 0)
        style_score = int(dimensions.get("style", 0) or 0)
        rhythm_score = int(dimensions.get("rythme", 0) or 0)

        story = "maintain"
        style = "maintain"
        rhythm = "maintain"
        instructions: list[str] = []
        rationale: list[str] = []

        if story_score <= 2:
            story = "clarify"
            instructions.append("Renforcer la continuité causale entre les scènes et rappeler l'objectif narratif.")
            rationale.append("Score histoire faible: meilleure lisibilité des arcs requise.")

        if style_score <= 2:
            style = "stabilize"
            instructions.append("Uniformiser le ton et limiter les variations de style entre scènes.")
            rationale.append("Score style faible: stabilisation stylistique demandée.")

        if rhythm_score <= 2:
            rhythm = "slow_down"
            instructions.append("Allonger les transitions et réduire les ruptures de rythme abruptes.")
            rationale.append("Score rythme faible: cadence à lisser.")
        elif rhythm_score >= 4:
            rhythm = "speed_up"
            instructions.append("Accélérer légèrement la montée dramatique sur la seconde moitié.")
            rationale.append("Score rythme élevé: autoriser une cadence plus dynamique.")

        if not instructions:
            instructions.append("Conserver la direction actuelle avec des micro-ajustements ciblés.")
            rationale.append("Feedback global positif: maintien de la stratégie actuelle.")

        return SessionAdjustments(
            rhythm=rhythm,
            style=style,
            story=story,
            instructions=instructions,
            rationale=rationale,
        )

    def latest_adjustments_for_session(self, *, session_id: str) -> SessionAdjustments | None:
        events = self.feedback_store.recent(session_id=session_id)
        if not events:
            return None
        last_event = events[-1]
        return self.derive_adjustments(feedback_event=last_event)

    def audit_adjustments(
        self,
        *,
        request_id: str,
        session_id: str,
        source_request_id: str,
        adjustments: SessionAdjustments,
    ) -> dict[str, Any]:
        event = {
            "timestamp": datetime.now(UTC).isoformat(),
            "request_id": request_id,
            "session_id": session_id,
            "source_request_id": source_request_id,
            "decisions": adjustments.to_dict(),
        }
        self.audit_store.append(event)
        return event


def load_feedback_input(path: Path | str = Path("outputs/feedback_input.json")) -> dict[str, Any] | None:
    """Charge un feedback brut éventuel (optionnel) depuis un fichier d'entrée."""
    target = Path(path)
    if not target.exists():
        return None
    payload = json.loads(target.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None
