"""Point d'entrée principal de l'application Narratech."""

from __future__ import annotations

import logging
import sys


from src.core.input_loader import load_prompt
from src.core.consistency_engine import enrich
from src.core.story_engine import StoryEngine


logger = logging.getLogger(__name__)


def main() -> None:
    """Démarre l'application."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    prompt = load_prompt(sys.argv[1:])
    preview = (prompt[:120] + "…") if len(prompt) > 120 else prompt
    logger.info("Démarrage de Narratech")
    logger.info("Prompt reçu: %s", preview)

    engine = StoryEngine()
    narrative = engine.generate(prompt)
    enriched_narrative = enrich(narrative)

    logger.info("Narration générée: %s", narrative["request_id"])
    logger.info("Fichier écrit: outputs/scene.json")
    logger.info("Fichier enrichi écrit: outputs/scene_enriched.json")
    logger.debug("Shots enrichis: %s", len(enriched_narrative.get("output", {}).get("shots", [])))


if __name__ == "__main__":
    main()
