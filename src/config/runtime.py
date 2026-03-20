"""Couche de configuration runtime unique (providers + secrets + timeouts)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


class ConfigValidationError(ValueError):
    """Erreur de validation de configuration au démarrage."""


@dataclass(slots=True)
class DomainRuntimeConfig:
    provider: str
    model: str | None
    timeout_sec: float
    api_key: str | None


@dataclass(slots=True)
class RuntimeConfig:
    profile: str
    vertical: str
    narrative: DomainRuntimeConfig
    asset: DomainRuntimeConfig
    shot: DomainRuntimeConfig
    audio: DomainRuntimeConfig


_ALLOWED_PROVIDERS: dict[str, set[str]] = {
    "narrative": {"mock_narrative", "openai_narrative"},
    "asset": {"mock_asset", "local_asset"},
    "shot": {"mock_shot", "picsum_shot", "async_shot"},
    "audio": {"mock_audio"},
}


_PROFILE_DEFAULTS: dict[str, dict[str, Any]] = {
    "dev": {
        "vertical": "dev_picsum_story_mock",
        "domains": {
            "narrative": {"provider": "mock_narrative", "model": "mock-narrative-v1", "timeout_sec": 8.0},
            "asset": {"provider": "mock_asset", "model": "mock-asset-v1", "timeout_sec": 8.0},
            "shot": {"provider": "picsum_shot", "model": "picsum-static", "timeout_sec": 10.0},
            "audio": {"provider": "mock_audio", "model": "mock-audio-v1", "timeout_sec": 10.0},
        },
    },
    "prod": {
        "vertical": "prod_openai_story_picsum_shot",
        "domains": {
            "narrative": {"provider": "openai_narrative", "model": "gpt-4.1-mini", "timeout_sec": 20.0},
            "asset": {"provider": "local_asset", "model": "local-asset-v1", "timeout_sec": 12.0},
            "shot": {"provider": "picsum_shot", "model": "picsum-static", "timeout_sec": 15.0},
            "audio": {"provider": "mock_audio", "model": "mock-audio-v1", "timeout_sec": 12.0},
        },
    },
    "local-fallback": {
        "vertical": "local_mock_full",
        "domains": {
            "narrative": {"provider": "mock_narrative", "model": "mock-narrative-v1", "timeout_sec": 8.0},
            "asset": {"provider": "mock_asset", "model": "mock-asset-v1", "timeout_sec": 8.0},
            "shot": {"provider": "mock_shot", "model": "mock-shot-v1", "timeout_sec": 10.0},
            "audio": {"provider": "mock_audio", "model": "mock-audio-v1", "timeout_sec": 10.0},
        },
    },
}

_PROFILE_ALIASES = {
    "local": "local-fallback",
    "demo": "dev",
}


def _resolve_profile(raw_profile: str) -> str:
    normalized = raw_profile.strip().lower()
    return _PROFILE_ALIASES.get(normalized, normalized)


def _resolve_domain(profile_payload: dict[str, Any], *, domain: str) -> DomainRuntimeConfig:
    domain_defaults = profile_payload["domains"][domain]
    provider = str(os.getenv(f"NARRATECH_PROVIDER_{domain.upper()}") or domain_defaults["provider"]).strip()
    model_raw = os.getenv(f"NARRATECH_MODEL_{domain.upper()}")
    model = str(model_raw).strip() if isinstance(model_raw, str) and model_raw.strip() else domain_defaults.get("model")

    timeout_raw = os.getenv(f"NARRATECH_TIMEOUT_{domain.upper()}_SEC")
    timeout_fallback = domain_defaults.get("timeout_sec", 10.0)
    timeout_value: Any = timeout_raw if timeout_raw is not None else timeout_fallback

    api_key: str | None = None
    api_key_raw = os.getenv(f"NARRATECH_API_KEY_{domain.upper()}")
    if isinstance(api_key_raw, str) and api_key_raw.strip():
        api_key = api_key_raw.strip()
    elif domain == "narrative":
        openai_key = os.getenv("OPENAI_API_KEY")
        if isinstance(openai_key, str) and openai_key.strip():
            api_key = openai_key.strip()

    try:
        timeout_sec = float(timeout_value)
    except (TypeError, ValueError):
        timeout_sec = -1.0

    return DomainRuntimeConfig(
        provider=provider,
        model=str(model) if isinstance(model, str) and model else None,
        timeout_sec=timeout_sec,
        api_key=api_key,
    )


def load_runtime_config(profile: str | None = None) -> RuntimeConfig:
    raw_profile = profile or os.getenv("NARRATECH_CONFIG_PROFILE") or os.getenv("NARRATECH_ENV") or "local-fallback"
    resolved_profile = _resolve_profile(str(raw_profile))
    profile_payload = _PROFILE_DEFAULTS.get(resolved_profile)
    if profile_payload is None:
        available = ", ".join(sorted(_PROFILE_DEFAULTS))
        raise ConfigValidationError(
            f"Profil de configuration inconnu '{raw_profile}'. Profils supportés: {available}."
        )

    runtime = RuntimeConfig(
        profile=resolved_profile,
        vertical=str(profile_payload.get("vertical") or resolved_profile),
        narrative=_resolve_domain(profile_payload, domain="narrative"),
        asset=_resolve_domain(profile_payload, domain="asset"),
        shot=_resolve_domain(profile_payload, domain="shot"),
        audio=_resolve_domain(profile_payload, domain="audio"),
    )
    validate_runtime_config(runtime)
    return runtime


def validate_runtime_config(config: RuntimeConfig) -> None:
    errors: list[str] = []

    for domain in ("narrative", "asset", "shot", "audio"):
        domain_config = getattr(config, domain)
        allowed = _ALLOWED_PROVIDERS[domain]
        if domain_config.provider not in allowed:
            allowed_txt = ", ".join(sorted(allowed))
            errors.append(
                f"[{domain}] provider '{domain_config.provider}' invalide (autorisés: {allowed_txt})."
            )

        if domain_config.timeout_sec <= 0:
            errors.append(
                f"[{domain}] timeout invalide ({domain_config.timeout_sec}); utiliser NARRATECH_TIMEOUT_{domain.upper()}_SEC > 0."
            )

    if config.narrative.provider == "openai_narrative" and not config.narrative.api_key:
        errors.append(
            "[narrative] OPENAI_API_KEY (ou NARRATECH_API_KEY_NARRATIVE) est requis quand provider=openai_narrative."
        )

    if errors:
        bullet_list = "\n - " + "\n - ".join(errors)
        raise ConfigValidationError(
            "Configuration runtime invalide. Corrigez les points suivants:" + bullet_list
        )


__all__ = [
    "ConfigValidationError",
    "DomainRuntimeConfig",
    "RuntimeConfig",
    "load_runtime_config",
    "validate_runtime_config",
]
