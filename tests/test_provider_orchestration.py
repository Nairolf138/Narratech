"""Tests d'orchestration retry/fallback et de contrat providers."""

from __future__ import annotations

import pytest

from src.core.pipeline_state import PipelineRuntimeState, PipelineStage
from src.core.story_engine import StoryEngine
from src.main import _execute_with_retry_and_fallback, _generate_shots_with_targeted_retries
from src.providers import (
    AssetProviderContract,
    MockAssetProvider,
    MockNarrativeProvider,
    MockShotProvider,
    NarrativeProviderContract,
    ProviderInvalidResponse,
    ProviderRateLimit,
    ProviderRequest,
    ProviderTimeout,
    ShotProviderContract,
)
from src.core.schema_validator import validate_narrative_document
from src.providers.narrative.openai_provider import OpenAINarrativeProvider
from src.providers.adapter import call_with_normalized_errors


@pytest.mark.parametrize(
    ("provider", "method_name", "payload", "expected_key"),
    [
        (MockNarrativeProvider(), "generate_narrative", {"prompt": "Un prompt valide"}, "output"),
        (MockAssetProvider(), "generate_assets", {"request_id": "req_contract", "output": {"characters": [], "scenes": []}}, "assets"),
        (MockShotProvider(), "generate_shots", {"request_id": "req_contract", "output": {"shots": []}}, "clips"),
    ],
)
def test_provider_contracts_return_expected_types_and_observability(
    provider: NarrativeProviderContract | AssetProviderContract | ShotProviderContract,
    method_name: str,
    payload: dict,
    expected_key: str,
) -> None:
    response = getattr(provider, method_name)(
        ProviderRequest(request_id="req_contract", payload=payload, timeout_sec=1.0)
    )

    assert isinstance(response.data, dict)
    assert expected_key in response.data
    assert isinstance(response.provider_trace, dict)
    assert response.provider_trace.get("provider")
    assert response.provider_trace.get("stage")
    assert response.provider_trace.get("trace_id")
    assert response.provider_trace.get("model")
    assert isinstance(response.model_name, str) and response.model_name
    assert isinstance(response.latency_ms, int)
    assert isinstance(response.cost_estimate, float)


def test_provider_contracts_raise_expected_error_types() -> None:
    with pytest.raises(ProviderInvalidResponse):
        MockNarrativeProvider().generate_narrative(ProviderRequest(request_id="req_err_1", payload={}))

    with pytest.raises(ProviderInvalidResponse):
        MockAssetProvider().generate_assets(ProviderRequest(request_id="req_err_2", payload={"request_id": "x"}))

    with pytest.raises(ProviderInvalidResponse):
        MockShotProvider().generate_shots(ProviderRequest(request_id="req_err_3", payload={"output": {}}))


def test_provider_error_adapter_normalizes_runtime_error() -> None:
    with pytest.raises(ProviderTimeout):
        call_with_normalized_errors(lambda: (_ for _ in ()).throw(RuntimeError("network timeout")))


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
    assert response.provider_trace.get("fallback_mode") is True
    assert response.provider_trace.get("fallback_reason") == "ProviderRateLimit"


def test_execute_with_retry_applies_configurable_fallback_policy() -> None:
    provider = MockAssetProvider()
    provider.configure({"failure_sequence": ["timeout"]})

    fallback = MockAssetProvider()
    fallback.configure({"failure_sequence": ["ok"]})

    with pytest.raises(ProviderTimeout):
        _execute_with_retry_and_fallback(
            action=lambda active: active.generate(
                request=ProviderRequest(
                    request_id="req_policy_1",
                    payload={"output": {"characters": [], "scenes": []}},
                    timeout_sec=1.0,
                )
            ),
            provider=provider,
            state=PipelineRuntimeState(request_id="req_policy_1"),
            stage=PipelineStage.ASSETS_GENERATED,
            fallback_provider=fallback,
            fallback_policy={"enabled": True, "trigger_on": ["ProviderRateLimit"]},
            retries=0,
        )


def test_execute_with_retry_cloud_to_local_fallback_respects_narrative_schema() -> None:
    primary = OpenAINarrativeProvider(
        transport=lambda *_args: (_ for _ in ()).throw(ProviderRateLimit("cloud quota exceeded"))
    )
    primary.configure({"api_key": "test-key", "retry_max_attempts": 0})
    fallback = MockNarrativeProvider()

    response = _execute_with_retry_and_fallback(
        action=lambda active: StoryEngine(provider=active).generate(
            prompt="Une histoire concise",
            request_id="req_story_fallback",
        ),
        provider=primary,
        state=PipelineRuntimeState(request_id="req_story_fallback"),
        stage=PipelineStage.STORY_GENERATED,
        fallback_provider=fallback,
        fallback_policy={"enabled": True, "trigger_on": ["ProviderRateLimit"]},
        response_validator=validate_narrative_document,
        retries=0,
    )

    validate_narrative_document(response)
    trace = response.get("provider_trace")
    assert isinstance(trace, list) and trace
    assert trace[-1].get("fallback_mode") is True
    assert trace[-1].get("fallback_reason") == "ProviderRateLimit"


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
        asset_refs=[{"id": "asset_character_001"}, {"id": "asset_environment_001"}],
    )

    assert len(clips) == 2
    assert quality["degraded_shots"] >= 1
    assert any(clip.get("quality_flag") == "degraded" for clip in clips)
    assert state.retry_events
    assert {event["scope_type"] for event in state.retry_events} >= {"shot", "asset", "scene"}
