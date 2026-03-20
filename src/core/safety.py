"""Composant Safety: blacklist configurable + validations + audit."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from src.core.io_utils import write_json_utf8

DEFAULT_SAFETY_AUDIT_PATH = Path("outputs/safety_audit.json")
DEFAULT_SAFETY_BLACKLIST_PATH = Path("config/safety_blacklist.json")


@dataclass(frozen=True, slots=True)
class SafetyViolation:
    """Violation safety détectée pendant une validation."""

    phase: str
    path: str
    category: str
    term: str
    excerpt: str


class SafetyBlockError(RuntimeError):
    """Erreur levée quand une règle Safety impose un blocage."""

    def __init__(self, message: str, event: dict[str, Any]) -> None:
        super().__init__(message)
        self.event = event


class SafetyAuditStore:
    """Persistance du journal d'audit safety."""

    def __init__(self, path: Path | str = DEFAULT_SAFETY_AUDIT_PATH, max_items: int = 500) -> None:
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


class SafetyGuard:
    """Valide prompts/outputs contre une blacklist configurable."""

    def __init__(
        self,
        *,
        blacklist: dict[str, list[str]] | None = None,
        audit_store: SafetyAuditStore | None = None,
        block_message_template: str | None = None,
    ) -> None:
        self.blacklist = {
            category: [str(term).strip() for term in terms if isinstance(term, str) and term.strip()]
            for category, terms in (blacklist or {}).items()
            if isinstance(category, str) and isinstance(terms, list)
        }
        self.audit_store = audit_store or SafetyAuditStore()
        self.block_message_template = (
            block_message_template
            or "Blocage safety: contenu interdit détecté ({category}: '{term}') dans {phase}."
        )

    @classmethod
    def from_environment(cls) -> "SafetyGuard":
        path = Path(
            (Path.cwd() / ".narratech_safety_blacklist_path").read_text(encoding="utf-8").strip()
        ) if Path(".narratech_safety_blacklist_path").exists() else DEFAULT_SAFETY_BLACKLIST_PATH
        blacklist = load_safety_blacklist(path)
        return cls(blacklist=blacklist)

    def validate_prompt(self, *, prompt: str, request_id: str, session_id: str) -> None:
        self._validate_text(
            phase="pre_generation_prompt",
            text=prompt,
            path="$.prompt",
            request_id=request_id,
            session_id=session_id,
        )

    def validate_output(self, *, payload: dict[str, Any], request_id: str, session_id: str) -> None:
        violations = self._scan_payload(payload, path="$.output")
        if not violations:
            return
        self._block(phase="post_generation_output", violations=violations, request_id=request_id, session_id=session_id)

    def _validate_text(self, *, phase: str, text: str, path: str, request_id: str, session_id: str) -> None:
        violations = self._scan_text(text=text, path=path, phase=phase)
        if not violations:
            return
        self._block(phase=phase, violations=violations, request_id=request_id, session_id=session_id)

    def _scan_payload(self, payload: Any, *, path: str) -> list[SafetyViolation]:
        violations: list[SafetyViolation] = []
        if isinstance(payload, str):
            violations.extend(self._scan_text(text=payload, path=path, phase="post_generation_output"))
        elif isinstance(payload, dict):
            for key, value in payload.items():
                if isinstance(key, str):
                    violations.extend(self._scan_payload(value, path=f"{path}.{key}"))
        elif isinstance(payload, list):
            for index, value in enumerate(payload):
                violations.extend(self._scan_payload(value, path=f"{path}[{index}]"))
        return violations

    def _scan_text(self, *, text: str, path: str, phase: str) -> list[SafetyViolation]:
        lowered = text.lower()
        violations: list[SafetyViolation] = []
        for category, terms in self.blacklist.items():
            for term in terms:
                normalized = term.lower()
                if normalized in lowered:
                    violations.append(
                        SafetyViolation(
                            phase=phase,
                            path=path,
                            category=category,
                            term=term,
                            excerpt=text[:220],
                        )
                    )
        return violations

    def _block(self, *, phase: str, violations: list[SafetyViolation], request_id: str, session_id: str) -> None:
        first = violations[0]
        event = {
            "timestamp": datetime.now(UTC).isoformat(),
            "request_id": request_id,
            "session_id": session_id,
            "phase": phase,
            "decision": "blocked",
            "message": self.block_message_template.format(
                category=first.category,
                term=first.term,
                phase=phase,
                path=first.path,
            ),
            "violations": [
                {
                    "phase": item.phase,
                    "path": item.path,
                    "category": item.category,
                    "term": item.term,
                    "excerpt": item.excerpt,
                }
                for item in violations
            ],
        }
        self.audit_store.append(event)
        raise SafetyBlockError(event["message"], event)


def load_safety_blacklist(path: Path | str = DEFAULT_SAFETY_BLACKLIST_PATH) -> dict[str, list[str]]:
    """Charge la blacklist configurable depuis un fichier JSON (optionnel)."""
    target = Path(path)
    if not target.exists():
        return {}
    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {}

    raw_blacklist = payload.get("blacklist", payload)
    if not isinstance(raw_blacklist, dict):
        return {}

    return {
        str(category): [str(term) for term in terms if isinstance(term, str)]
        for category, terms in raw_blacklist.items()
        if isinstance(terms, list)
    }
