"""Tests CLI minimaux pour les sous-commandes de Narratech."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.core.story_engine import StoryEngine


def _write_fixture(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_cli_validate_accepts_valid_fixture(tmp_path: Path) -> None:
    """La commande `validate` doit retourner 0 pour un document conforme."""
    valid_file = tmp_path / "scene_valid.json"
    narrative = StoryEngine().generate("Un test de validation CLI.")
    _write_fixture(valid_file, narrative)

    result = subprocess.run(
        [sys.executable, "-m", "src.main", "validate", str(valid_file)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Document narratif valide" in result.stdout


def test_cli_validate_rejects_invalid_fixture(tmp_path: Path) -> None:
    """La commande `validate` doit retourner le code de validation pour un document non conforme."""
    invalid_file = tmp_path / "scene_invalid.json"
    invalid_narrative = StoryEngine().generate("Un test de validation CLI invalide.")
    invalid_narrative.pop("request_id", None)
    _write_fixture(invalid_file, invalid_narrative)

    result = subprocess.run(
        [sys.executable, "-m", "src.main", "validate", str(invalid_file)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 3
    assert "Document narratif invalide" in result.stdout


def test_main_routes_validate_and_default_pipeline(monkeypatch) -> None:
    """`main()` route vers validate puis pipeline par défaut."""
    from src import main as main_module

    called = {"validate": False, "pipeline": False}

    def fake_validate(args: list[str]) -> int:
        called["validate"] = True
        assert args == ["file.json"]
        return 0

    def fake_pipeline(args: list[str]) -> int:
        called["pipeline"] = True
        assert args == []
        return 0

    monkeypatch.setattr(main_module, "_run_validation_cli", fake_validate)
    monkeypatch.setattr(main_module, "_run_pipeline", fake_pipeline)

    monkeypatch.setattr(sys, "argv", ["narratech", "validate", "file.json"])
    assert main_module.main() == 0

    monkeypatch.setattr(sys, "argv", ["narratech"])
    assert main_module.main() == 0

    assert called == {"validate": True, "pipeline": True}


def test_main_routes_generate(monkeypatch) -> None:
    """`main()` route vers `generate`."""
    from src import main as main_module

    called = {"generate": False}

    def fake_generate(args: list[str]) -> int:
        called["generate"] = True
        assert args == ["--prompt", "hello"]
        return 0

    monkeypatch.setattr(main_module, "_run_generate_cli", fake_generate)
    monkeypatch.setattr(sys, "argv", ["narratech", "generate", "--prompt", "hello"])
    assert main_module.main() == 0
    assert called["generate"] is True


def test_run_generate_cli_returns_usage_code_for_missing_args() -> None:
    """`generate` retourne le code usage quand des arguments requis manquent."""
    from src import main as main_module

    assert main_module._run_generate_cli([]) == main_module.EXIT_USAGE_ERROR
