"""Contrats spécialisés pour les providers de narration, assets et shots."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Mapping

from .base import ProviderHealth, ProviderRequest, ProviderResponse


class NarrativeProviderContract(ABC):
    """Contrat explicite pour un provider de narration."""

    @abstractmethod
    def configure(self, config: Mapping[str, Any]) -> None:
        """Configure le provider."""

    @abstractmethod
    def generate_narrative(self, request: ProviderRequest) -> ProviderResponse:
        """Génère un document narratif conforme au schéma narratif."""

    @abstractmethod
    def healthcheck(self) -> ProviderHealth:
        """Retourne l'état de santé du provider."""


class AssetProviderContract(ABC):
    """Contrat explicite pour un provider de génération d'assets."""

    @abstractmethod
    def configure(self, config: Mapping[str, Any]) -> None:
        """Configure le provider."""

    @abstractmethod
    def generate_assets(self, request: ProviderRequest) -> ProviderResponse:
        """Génère des références d'assets à partir d'un document enrichi."""

    @abstractmethod
    def healthcheck(self) -> ProviderHealth:
        """Retourne l'état de santé du provider."""


class ShotProviderContract(ABC):
    """Contrat explicite pour un provider de génération de shots/clips."""

    @abstractmethod
    def configure(self, config: Mapping[str, Any]) -> None:
        """Configure le provider."""

    @abstractmethod
    def generate_shots(self, request: ProviderRequest) -> ProviderResponse:
        """Génère des clips de shots à partir du plan de scène."""

    @abstractmethod
    def healthcheck(self) -> ProviderHealth:
        """Retourne l'état de santé du provider."""
