"""Tests d'orchestration retry/fallback pour les providers."""

from __future__ import annotations

from src.core.pipeline_state import PipelineRuntimeState, PipelineStage
from src.main import _execute_with_retry_and_fallback
from src.providers import MockAssetProvider, ProviderRateLimit, ProviderRequest, ProviderTimeout


def test_execute_with_retry_recovers_after_timeout() -> None:
    provider = MockAssetProvider()
    provider.configure({"failure_sequence": ["timeout", "ok"]})

    result = _execute_with_retry_and_fallback(
        action=lambda active: active.generate(
            request=ProviderRequest(
                request_id="req_1",
                payload={"output": {"characters": [], "scenes": []}},
                timeout_sec=1.0,
            )
        ),
        provider=provider,
        state=PipelineRuntimeState(request_id="req_test_retry_1"),
        stage=PipelineStage.ASSETS_GENERATED,
        retries=1,
    )

    assert result.data.get("assets") is not None


def test_execute_with_retry_uses_fallback_after_rate_limit() -> None:
    primary = MockAssetProvider()
    primary.configure({"failure_sequence": ["rate_limit", "rate_limit"]})

    fallback = MockAssetProvider()
    fallback.configure({"failure_sequence": ["ok"]})

    response = _execute_with_retry_and_fallback(
        action=lambda active: active.generate(
            request=ProviderRequest(
                request_id="req_2",
                payload={"output": {"characters": [], "scenes": []}},
                timeout_sec=1.0,
            )
        ),
        provider=primary,
        state=PipelineRuntimeState(request_id="req_test_retry_2"),
        stage=PipelineStage.ASSETS_GENERATED,
        fallback_provider=fallback,
        retries=1,
    )

    assert response.provider_trace.get("provider") == "mock_asset_provider"
    assert response.data.get("assets") is not None


def test_execute_with_retry_raises_when_no_fallback() -> None:
    provider = MockAssetProvider()
    provider.configure({"failure_sequence": ["rate_limit", "rate_limit"]})

    try:
        _execute_with_retry_and_fallback(
            action=lambda active: active.generate(
                request=ProviderRequest(
                    request_id="req_3",
                    payload={"output": {"characters": [], "scenes": []}},
                    timeout_sec=1.0,
                )
            ),
            provider=provider,
            state=PipelineRuntimeState(request_id="req_test_retry_3"),
            stage=PipelineStage.ASSETS_GENERATED,
            retries=1,
        )
    except ProviderRateLimit:
        assert True
    except ProviderTimeout:
        assert False, "Expected ProviderRateLimit"
    else:
        assert False, "Expected a provider exception"
