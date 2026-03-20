"""Intégrations providers et contrat commun."""

from .base import (
    BaseProvider,
    ProviderAuthError,
    ProviderError,
    ProviderHealth,
    ProviderInvalidResponse,
    ProviderRateLimit,
    ProviderRequest,
    ProviderResponse,
    ProviderTimeout,
)
from .adapter import call_with_normalized_errors, normalize_provider_error
from .contracts import AssetProviderContract, NarrativeProviderContract, ShotProviderContract
from .local_asset_provider import LocalAssetProvider
from .mock_asset_provider import MockAssetProvider
from .mock_narrative_provider import MockNarrativeProvider
from .mock_shot_provider import MockShotProvider
from .picsum_shot_provider import PicsumShotProvider
from .narrative.openai_provider import OpenAINarrativeProvider
from .factory import create_narrative_provider

__all__ = [
    "BaseProvider",
    "ProviderRequest",
    "ProviderResponse",
    "ProviderHealth",
    "ProviderError",
    "ProviderTimeout",
    "ProviderAuthError",
    "ProviderRateLimit",
    "ProviderInvalidResponse",
    "normalize_provider_error",
    "call_with_normalized_errors",
    "NarrativeProviderContract",
    "AssetProviderContract",
    "ShotProviderContract",
    "MockNarrativeProvider",
    "MockAssetProvider",
    "LocalAssetProvider",
    "MockShotProvider",
    "PicsumShotProvider",
    "OpenAINarrativeProvider",
    "create_narrative_provider",
]
