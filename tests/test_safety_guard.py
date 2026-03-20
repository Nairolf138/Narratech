"""Tests du composant safety (blacklist, validation et audit)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.core.safety import SafetyBlockError, SafetyGuard, load_safety_blacklist


def test_load_safety_blacklist_supports_nested_blacklist_key(tmp_path: Path) -> None:
    path = tmp_path / "safety.json"
    path.write_text(
        json.dumps({"blacklist": {"objects": ["arme"], "people": ["personne_x"]}}, ensure_ascii=False),
        encoding="utf-8",
    )

    result = load_safety_blacklist(path)

    assert result == {"objects": ["arme"], "people": ["personne_x"]}


def test_safety_guard_blocks_prompt_and_writes_audit(isolated_workdir: Path) -> None:
    audit_path = isolated_workdir / "outputs" / "safety_audit.json"
    guard = SafetyGuard(
        blacklist={"topics": ["violence"]},
        audit_store=None,
    )

    with pytest.raises(SafetyBlockError) as exc_info:
        guard.validate_prompt(
            prompt="Raconte une histoire de violence explicite.",
            request_id="req_1",
            session_id="session_1",
        )

    assert "Blocage safety" in str(exc_info.value)
    assert audit_path.exists()
    events = json.loads(audit_path.read_text(encoding="utf-8"))
    assert events[-1]["decision"] == "blocked"
    assert events[-1]["phase"] == "pre_generation_prompt"


def test_safety_guard_blocks_textual_output_and_metadata(isolated_workdir: Path) -> None:
    guard = SafetyGuard(blacklist={"objects": ["pistolet"]})

    with pytest.raises(SafetyBlockError):
        guard.validate_output(
            payload={
                "output": {"synopsis": "Une scène avec pistolet visible."},
                "metadata": {"note": "objet: pistolet"},
            },
            request_id="req_2",
            session_id="session_2",
        )
