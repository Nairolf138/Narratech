"""Utilitaires I/O pour sérialisation déterministe des artefacts JSON."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_json_utf8(path: str | Path, payload: Any) -> Path:
    """Écrit `payload` en JSON UTF-8 avec indentation stable.

    Garanties:
    - encodage UTF-8;
    - indentation à 2 espaces;
    - tri des clés pour un diff stable;
    - création automatique des dossiers parents.
    """
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return destination
