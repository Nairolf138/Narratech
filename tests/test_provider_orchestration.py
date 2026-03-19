"""Tests d'orchestration retry/fallback pour les providers."""

from __future__ import annotations

from src.core.pipeline_state import PipelineRuntimeState, PipelineStage
from src.main import _execute_with_retry_and_fallback, _generate_shots_with_targeted_retries
from src.providers import MockAssetProvider, MockShotProvider, ProviderRateLimit, ProviderRequest, ProviderTimeout


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


def test_targeted_shot_retries_fallback_to_placeholder() -> None:
    scene_doc = {
        "request_id": "req_shot_1",
        "output": {
            "shots": [
                {"id": "shot_001", "scene_id": "scene_1", "description": "A", "duration_sec": 3.0},
                {"id": "shot_002", "scene_id": "scene_1", "description": "B", "duration_sec": 3.0},
            ]
        },
    }
    state = PipelineRuntimeState(request_id="req_shot_1")

    primary = MockShotProvider()
    primary.configure({"failure_sequence": ["rate_limit", "rate_limit", "rate_limit", "rate_limit", "rate_limit"]})
    secondary = MockShotProvider()
    secondary.configure({"failure_sequence": ["rate_limit", "rate_limit", "rate_limit", "rate_limit"]})

    clips, quality = _generate_shots_with_targeted_retries(
        scene_doc=scene_doc,
        state=state,
        primary_provider=primary,
        secondary_provider=secondary,
        asset_provider=MockAssetProvider(),
    )

    assert len(clips) == 2
    assert quality["degraded_shots"] >= 1
    assert any(clip.get("quality_flag") == "degraded" for clip in clips)
    assert state.retry_events
    assert {event["scope_type"] for event in state.retry_events} >= {"shot", "asset", "scene"}
