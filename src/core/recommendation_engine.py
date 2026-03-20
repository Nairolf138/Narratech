"""Composant heuristique de recommandations pour ajuster les prompts narratifs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from src.core.io_utils import write_json_utf8

DEFAULT_HISTORY_PATH = Path("outputs/recommendation_history.json")


@dataclass(slots=True)
class PromptRecommendation:
    """Recommandations calculées pour le prochain prompt."""

    tension: str
    arcs: str
    trope_variety: str
    recommended_instructions: list[str]
    rationale: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "tension": self.tension,
            "arcs": self.arcs,
            "trope_variety": self.trope_variety,
            "recommended_instructions": list(self.recommended_instructions),
            "rationale": list(self.rationale),
        }


class RecommendationHistoryStore:
    """Stockage JSON minimal des recommandations par utilisateur."""

    def __init__(self, path: Path | str = DEFAULT_HISTORY_PATH, max_items_per_user: int = 10) -> None:
        self.path = Path(path)
        self.max_items_per_user = max(1, max_items_per_user)

    def _load(self) -> dict[str, list[dict[str, Any]]]:
        if not self.path.exists():
            return {}
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {}
        return {
            str(user_id): list(entries)
            for user_id, entries in raw.items()
            if isinstance(entries, list)
        }

    def append(self, *, user_id: str, event: dict[str, Any]) -> None:
        history = self._load()
        entries = history.setdefault(user_id, [])
        entries.append(event)
        history[user_id] = entries[-self.max_items_per_user :]
        write_json_utf8(self.path.as_posix(), history)

    def recent(self, *, user_id: str) -> list[dict[str, Any]]:
        history = self._load()
        return list(history.get(user_id, []))


class RecommendationEngine:
    """Moteur de règles heuristiques avant un modèle ML plus avancé."""

    def __init__(self, history_store: RecommendationHistoryStore | None = None) -> None:
        self.history_store = history_store or RecommendationHistoryStore()

    def recommend(
        self,
        *,
        user_id: str,
        generated_content: dict[str, Any],
        user_feedback: dict[str, Any] | None,
        coherence_metrics: dict[str, Any] | None,
        request_id: str | None = None,
    ) -> PromptRecommendation:
        feedback = user_feedback or {}
        metrics = coherence_metrics or {}

        instructions: list[str] = []
        rationale: list[str] = []

        coherence_score = float(metrics.get("coherence_score", 1.0))
        tension_jump = float(metrics.get("max_tension_jump", 0.0))
        trope_repetition = float(metrics.get("trope_repetition_ratio", 0.0))

        tension = "maintain"
        arcs = "maintain"
        trope_variety = "maintain"

        if coherence_score < 0.75 or tension_jump > 3.0:
            tension = "decrease"
            arcs = "stabilize"
            instructions.append("Réduire les pics de tension entre scènes successives.")
            instructions.append("Expliciter les transitions de cause à effet entre les arcs.")
            rationale.append("Cohérence narrative faible ou sauts de tension trop élevés.")

        if bool(feedback.get("wants_more_tension")):
            tension = "increase"
            instructions.append("Augmenter graduellement la tension dramatique jusqu'au climax.")
            rationale.append("Feedback utilisateur: plus de tension souhaitée.")

        if bool(feedback.get("confusing_arcs")):
            arcs = "clarify"
            instructions.append("Ajouter un rappel court de l'objectif d'arc au début de chaque scène.")
            rationale.append("Feedback utilisateur: arcs jugés confus.")

        if trope_repetition >= 0.4 or bool(feedback.get("repetitive_tropes")):
            trope_variety = "increase"
            instructions.append("Varier les tropes secondaires et éviter la répétition d'un même motif.")
            rationale.append("Répétition de tropes détectée ou signalée.")

        if not instructions:
            instructions.append("Conserver la progression actuelle, avec micro-variations de rythme.")
            rationale.append("Aucune alerte majeure: baseline conservatrice.")

        recommendation = PromptRecommendation(
            tension=tension,
            arcs=arcs,
            trope_variety=trope_variety,
            recommended_instructions=instructions,
            rationale=rationale,
        )

        output = generated_content.get("output", {}) if isinstance(generated_content, dict) else {}
        shots = output.get("shots", []) if isinstance(output, dict) else []
        event = {
            "timestamp": datetime.now(UTC).isoformat(),
            "request_id": request_id,
            "coherence_score": coherence_score,
            "shot_count": len(shots) if isinstance(shots, list) else 0,
            "recommendation": recommendation.to_dict(),
        }
        self.history_store.append(user_id=user_id, event=event)

        return recommendation
