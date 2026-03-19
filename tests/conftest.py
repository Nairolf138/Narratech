"""Fixtures partagées pour les tests smoke du pipeline."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def minimal_prompt() -> str:
    """Prompt stable minimal pour un run deterministic."""
    return "Un détective découvre un message codé dans un carnet."


@pytest.fixture
def isolated_workdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isole les écritures disque du pipeline dans un dossier temporaire."""
    monkeypatch.chdir(tmp_path)
    return tmp_path
