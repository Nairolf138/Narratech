"""Contrat de base pour les adapters providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Mapping


class ProviderError(Exception):
    """Erreur de base pour toutes les erreurs providers normalisées."""


class ProviderTimeout(ProviderError):
    """Le provider n'a pas répondu dans le délai alloué."""


class ProviderAuthError(ProviderError):
    """Authentification ou autorisation invalide côté provider."""


class ProviderRateLimit(ProviderError):
    """Quota dépassé ou throttling renvoyé par le provider."""


class ProviderInvalidResponse(ProviderError):
    """Réponse provider invalide ou hors contrat attendu."""


@dataclass(slots=True)
class ProviderRequest:
    """Entrée minimale d'un appel provider.

    Attributes:
        request_id: Identifiant unique de corrélation.
        payload: Données métier à traiter (déjà validées côté orchestration).
        timeout_sec: Timeout réseau/logique recommandé pour l'opération.
    """

    request_id: str
    payload: Mapping[str, Any]
    timeout_sec: float | None = None


@dataclass(slots=True)
class ProviderResponse:
    """Sortie minimale normalisée d'un provider.

    Attributes:
        data: Données métier retournées par le provider.
        provider_trace: Métadonnées de traçabilité provider.
        latency_ms: Latence mesurée côté adapter, en millisecondes.
        cost_estimate: Estimation de coût de l'opération.
        model_name: Nom du modèle réellement utilisé.
    """

    data: Mapping[str, Any]
    provider_trace: Mapping[str, Any] = field(default_factory=dict)
    latency_ms: int = 0
    cost_estimate: float = 0.0
    model_name: str = "unknown"


@dataclass(slots=True)
class ProviderHealth:
    """Résultat d'un contrôle de disponibilité provider.

    Attributes:
        ok: Indique si le provider peut recevoir du trafic.
        details: Détails techniques de diagnostic (latence, dépendances, etc.).
    """

    ok: bool
    details: Mapping[str, Any] = field(default_factory=dict)


class BaseProvider(ABC):
    """Interface minimale commune à tous les providers.

    Les implémentations doivent lever uniquement des sous-classes de
    :class:`ProviderError` pour les erreurs externes normalisées.
    """

    @abstractmethod
    def configure(self, config: Mapping[str, Any]) -> None:
        """Charge la configuration provider.

        Args:
            config: Paramètres de configuration (secrets, endpoints, options runtime).

        Raises:
            ProviderAuthError: Si les credentials fournis sont invalides.
            ProviderError: Pour toute erreur de configuration non récupérable.
        """

    @abstractmethod
    def generate(self, request: ProviderRequest) -> ProviderResponse:
        """Exécute l'opération principale de génération provider.

        Args:
            request: Requête normalisée avec `request_id` et payload métier.

        Returns:
            ProviderResponse: Résultat typé avec observabilité standard.

        Raises:
            ProviderTimeout: Si l'appel dépasse le délai autorisé.
            ProviderAuthError: Si l'authentification provider échoue.
            ProviderRateLimit: Si le provider applique un throttling.
            ProviderInvalidResponse: Si la réponse ne respecte pas le contrat.
        """

    @abstractmethod
    def healthcheck(self) -> ProviderHealth:
        """Vérifie l'état du provider sans effet de bord métier.

        Returns:
            ProviderHealth: État de disponibilité et informations de diagnostic.

        Raises:
            ProviderError: Si le check échoue de façon non transitoire.
        """
