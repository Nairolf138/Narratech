"""Point d'entrée principal de l'application Narratech."""

from __future__ import annotations

import logging


logger = logging.getLogger(__name__)


def main() -> None:
    """Démarre l'application."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    logger.info("Démarrage de Narratech")


if __name__ == "__main__":
    main()
