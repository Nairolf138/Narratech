"""Utilitaires I/O pour sérialisation déterministe des artefacts JSON."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


_SENSITIVE_KEYWORDS = (
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "session",
    "ssn",
    "email",
    "phone",
)
_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN (RSA|EC|OPENSSH|PRIVATE) KEY-----"),
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
)


def sanitize_pii_and_secrets(payload: Any) -> Any:
    """Retourne une copie du payload avec secrets/PII usuels masqués."""

    def _sanitize(value: Any, parent_key: str = "") -> Any:
        if isinstance(value, dict):
            return {
                key: _sanitize(subvalue, parent_key=key)
                for key, subvalue in value.items()
            }
        if isinstance(value, list):
            return [_sanitize(item, parent_key=parent_key) for item in value]
        if isinstance(value, str):
            lowered_key = parent_key.lower()
            if any(keyword in lowered_key for keyword in _SENSITIVE_KEYWORDS):
                return "[REDACTED]"
            sanitized = value
            for pattern in _SECRET_PATTERNS:
                sanitized = pattern.sub("[REDACTED]", sanitized)
            sanitized = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[REDACTED_EMAIL]", sanitized)
            sanitized = re.sub(r"\b(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{3}\)?[\s.-]?)\d{3}[\s.-]?\d{4}\b", "[REDACTED_PHONE]", sanitized)
            return sanitized
        return value

    return _sanitize(payload)


def write_json_utf8(path: str | Path, payload: Any) -> Path:
    """Écrit `payload` en JSON UTF-8 avec indentation stable.

    Garanties:
    - encodage UTF-8;
    - indentation à 2 espaces;
    - tri des clés pour un diff stable;
    - création automatique des dossiers parents.
    """
    destination = Path(path)
    sanitized_payload = sanitize_pii_and_secrets(payload)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(sanitized_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return destination
