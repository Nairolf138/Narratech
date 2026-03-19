"""Couche commune d'adaptation pour appels provider et normalisation d'erreurs."""

from __future__ import annotations

from typing import Callable, TypeVar

from .base import (
    ProviderAuthError,
    ProviderError,
    ProviderInvalidResponse,
    ProviderRateLimit,
    ProviderTimeout,
)

T = TypeVar("T")


def normalize_provider_error(error: Exception) -> ProviderError:
    """Normalise toute exception provider vers le contrat d'erreurs interne."""
    if isinstance(error, ProviderError):
        return error

    message = str(error).lower()
    if isinstance(error, TimeoutError) or "timeout" in message:
        return ProviderTimeout(str(error) or "Provider timeout")
    if "rate" in message and "limit" in message:
        return ProviderRateLimit(str(error) or "Provider rate limited")
    if "auth" in message or "credential" in message or "forbidden" in message:
        return ProviderAuthError(str(error) or "Provider authentication error")
    if isinstance(error, (ValueError, TypeError, KeyError)):
        return ProviderInvalidResponse(str(error) or "Provider invalid response")

    return ProviderError(str(error) or "Provider error")


def call_with_normalized_errors(action: Callable[[], T]) -> T:
    """Exécute un appel provider en garantissant des erreurs normalisées."""
    try:
        return action()
    except Exception as exc:  # pragma: no cover - mapping validated by tests
        raise normalize_provider_error(exc) from exc
