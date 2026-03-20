"""Suites de tests de contrat communes pour providers mock et providers réels activables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable

import pytest

from src.providers import (
    AsyncShotProvider,
    LocalAssetProvider,
    MockAssetProvider,
    MockAudioProvider,
    MockNarrativeProvider,
    MockShotProvider,
    OpenAINarrativeProvider,
    ProviderInvalidResponse,
    ProviderRateLimit,
    ProviderRequest,
    ProviderResponse,
    ProviderTimeout,
)


def _real_contract_tests_enabled() -> bool:
    return os.getenv("NARRATECH_ENABLE_REAL_PROVIDER_CONTRACT_TESTS", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


@dataclass(frozen=True)
class ProviderContractCase:
    name: str
    kind: str
    mode: str
    invoke: Callable[[Any, ProviderRequest], ProviderResponse]
    build_provider: Callable[[], Any]
    success_payload: dict[str, Any]
    expected_data_key: str
    timeout_payload: dict[str, Any]
    rate_limit_payload: dict[str, Any]
    invalid_payload: dict[str, Any]


def _invoke_narrative(provider: Any, request: ProviderRequest) -> ProviderResponse:
    return provider.generate_narrative(request)


def _invoke_assets(provider: Any, request: ProviderRequest) -> ProviderResponse:
    return provider.generate_assets(request)


def _invoke_shots(provider: Any, request: ProviderRequest) -> ProviderResponse:
    return provider.generate_shots(request)


def _invoke_audio(provider: Any, request: ProviderRequest) -> ProviderResponse:
    return provider.synthesize_audio(request)


def _base_narrative_payload() -> dict[str, Any]:
    return {"prompt": "Un court récit cohérent."}


def _base_asset_payload() -> dict[str, Any]:
    return {
        "request_id": "req_contract_asset",
        "output": {
            "characters": [{"id": "char_1", "name": "Alex", "role": "protagonist"}],
            "scenes": [{"id": "scene_1", "summary": "Un laboratoire discret"}],
            "shots": [{"id": "shot_1", "description": "Entrée", "duration_sec": 3.0}],
        },
    }


def _base_shot_payload() -> dict[str, Any]:
    return {
        "output": {
            "shots": [
                {"id": "shot_1", "description": "Panoramique", "duration_sec": 3.0},
                {"id": "shot_2", "description": "Gros plan", "duration_sec": 2.0},
            ]
        },
        "asset_refs": [{"id": "asset_1"}],
    }


def _base_audio_payload() -> dict[str, Any]:
    return {
        "request_id": "req_contract_audio",
        "mode": "voiceover",
        "narrative_text": "Texte narratif cohérent.",
        "language": "fr",
        "style": "cinematic",
        "shots": [{"id": "shot_1", "duration_sec": 2.5}],
    }


def _fake_openai_success_transport(_payload: dict[str, Any], _timeout: float, _api_key: str, _endpoint: str) -> dict[str, Any]:
    return {
        "output_text": '{"request_id":"req_contract","schema_version":"narrative.v1","input":{"prompt":"Prompt","duration_sec":45,"style":"cinematic","language":"fr"},"output":{"synopsis":"Synopsis","characters":[{"id":"char_1","name":"Alex","role":"protagonist"}],"scenes":[{"id":"scene_1","summary":"Résumé","duration_sec":45}],"shots":[{"id":"shot_1","scene_id":"scene_1","description":"Plan","duration_sec":15.0}],"asset_refs":[],"audio_plan":{"voiceover":{"enabled":true},"ambience":{"enabled":true}},"render_plan":{"resolution":"1920x1080","fps":24,"format":"mp4"}},"provider_trace":[{"stage":"story_generation","provider":"openai_narrative_provider","model":"gpt-4.1-mini","trace_id":"trace_contract"}]}'
    }


def _build_mock_cases() -> list[ProviderContractCase]:
    return [
        ProviderContractCase(
            name="narrative_mock",
            kind="narrative",
            mode="mock",
            invoke=_invoke_narrative,
            build_provider=MockNarrativeProvider,
            success_payload=_base_narrative_payload(),
            expected_data_key="output",
            timeout_payload=_base_narrative_payload(),
            rate_limit_payload=_base_narrative_payload(),
            invalid_payload={},
        ),
        ProviderContractCase(
            name="asset_mock",
            kind="asset",
            mode="mock",
            invoke=_invoke_assets,
            build_provider=MockAssetProvider,
            success_payload=_base_asset_payload(),
            expected_data_key="assets",
            timeout_payload=_base_asset_payload(),
            rate_limit_payload=_base_asset_payload(),
            invalid_payload={"request_id": "x"},
        ),
        ProviderContractCase(
            name="shot_mock",
            kind="shot",
            mode="mock",
            invoke=_invoke_shots,
            build_provider=MockShotProvider,
            success_payload=_base_shot_payload(),
            expected_data_key="clips",
            timeout_payload=_base_shot_payload(),
            rate_limit_payload=_base_shot_payload(),
            invalid_payload={"output": {}},
        ),
        ProviderContractCase(
            name="audio_mock",
            kind="audio",
            mode="mock",
            invoke=_invoke_audio,
            build_provider=MockAudioProvider,
            success_payload=_base_audio_payload(),
            expected_data_key="audio_file",
            timeout_payload=_base_audio_payload(),
            rate_limit_payload=_base_audio_payload(),
            invalid_payload={"mode": "voiceover"},
        ),
    ]


def _build_real_cases() -> list[ProviderContractCase]:
    return [
        ProviderContractCase(
            name="narrative_openai",
            kind="narrative",
            mode="real",
            invoke=_invoke_narrative,
            build_provider=lambda: OpenAINarrativeProvider(transport=_fake_openai_success_transport),
            success_payload=_base_narrative_payload(),
            expected_data_key="output",
            timeout_payload=_base_narrative_payload(),
            rate_limit_payload=_base_narrative_payload(),
            invalid_payload={},
        ),
        ProviderContractCase(
            name="asset_local",
            kind="asset",
            mode="real",
            invoke=_invoke_assets,
            build_provider=LocalAssetProvider,
            success_payload=_base_asset_payload(),
            expected_data_key="assets",
            timeout_payload=_base_asset_payload(),
            rate_limit_payload=_base_asset_payload(),
            invalid_payload={"request_id": "x"},
        ),
        ProviderContractCase(
            name="shot_async",
            kind="shot",
            mode="real",
            invoke=_invoke_shots,
            build_provider=AsyncShotProvider,
            success_payload=_base_shot_payload(),
            expected_data_key="clips",
            timeout_payload=_base_shot_payload(),
            rate_limit_payload=_base_shot_payload(),
            invalid_payload={"asset_refs": []},
        ),
    ]


ALL_CASES = _build_mock_cases() + _build_real_cases()


@pytest.fixture(params=ALL_CASES, ids=lambda case: case.name)
def provider_case(request: pytest.FixtureRequest) -> ProviderContractCase:
    case = request.param
    if case.mode == "real" and not _real_contract_tests_enabled():
        pytest.skip("Providers réels désactivés (NARRATECH_ENABLE_REAL_PROVIDER_CONTRACT_TESTS != true)")
    return case


def _configure_success_provider(case: ProviderContractCase) -> Any:
    provider = case.build_provider()
    if case.name == "narrative_openai":
        provider.configure({"api_key": "test-key", "retry_max_attempts": 0, "max_remediation_attempts": 0})
    elif case.name == "shot_async":
        provider.configure({"backend": "local", "poll_interval_sec": 0.0, "retry_backoff_base_sec": 0.0})
    else:
        provider.configure({})
    return provider


def _configure_timeout_provider(case: ProviderContractCase) -> Any:
    if case.mode == "mock":
        provider = case.build_provider()
        provider.configure({"failure_sequence": ["timeout"]})
        return provider

    if case.name == "narrative_openai":
        provider = OpenAINarrativeProvider(transport=lambda *_: (_ for _ in ()).throw(ProviderTimeout("timeout")))
        provider.configure({"api_key": "test-key", "retry_max_attempts": 0})
        return provider

    if case.name == "asset_local":
        provider = LocalAssetProvider(
            transport=lambda **_: (_ for _ in ()).throw(ProviderTimeout("timeout"))
        )
        provider.configure({"mode": "api"})
        return provider

    if case.name == "shot_async":
        provider = AsyncShotProvider()
        provider.configure({"backend": "runway", "max_poll_attempts": 1, "poll_interval_sec": 0.0, "adapter_config": {"polls_before_completed": 50}})
        return provider

    raise AssertionError(f"Cas timeout non géré: {case.name}")


def _configure_rate_limit_provider(case: ProviderContractCase) -> Any:
    if case.mode == "mock":
        provider = case.build_provider()
        provider.configure({"failure_sequence": ["rate_limit"]})
        return provider

    if case.name == "narrative_openai":
        provider = OpenAINarrativeProvider(transport=lambda *_: (_ for _ in ()).throw(ProviderRateLimit("quota")))
        provider.configure({"api_key": "test-key", "retry_max_attempts": 0})
        return provider

    if case.name == "asset_local":
        provider = LocalAssetProvider(
            transport=lambda **_: (_ for _ in ()).throw(ProviderRateLimit("quota"))
        )
        provider.configure({"mode": "api"})
        return provider

    if case.name == "shot_async":
        class _RateLimitAdapter:
            def configure(self, _config: Any) -> None:
                return None

            def submit_render(self, **_kwargs: Any) -> Any:
                raise ProviderRateLimit("quota")

            def get_render_status(self, _job_id: str) -> Any:
                raise AssertionError("Non appelé")

        provider = AsyncShotProvider()
        provider.configure({"backend": "local"})
        provider._adapter = _RateLimitAdapter()  # noqa: SLF001
        return provider

    raise AssertionError(f"Cas rate_limit non géré: {case.name}")


@pytest.mark.parametrize("request_id", ["req_contract_a"])
def test_provider_contract_success_and_conformity(provider_case: ProviderContractCase, request_id: str) -> None:
    provider = _configure_success_provider(provider_case)

    response = provider_case.invoke(
        provider,
        ProviderRequest(request_id=request_id, payload=provider_case.success_payload, timeout_sec=1.0),
    )

    assert isinstance(response, ProviderResponse)
    assert isinstance(response.data, dict)
    assert provider_case.expected_data_key in response.data
    assert isinstance(response.provider_trace, dict)
    assert isinstance(response.provider_trace.get("provider"), str)
    assert isinstance(response.provider_trace.get("stage"), str)
    assert isinstance(response.provider_trace.get("trace_id"), str)
    assert isinstance(response.provider_trace.get("model"), str)
    assert isinstance(response.model_name, str) and response.model_name
    assert isinstance(response.latency_ms, int)
    assert isinstance(response.cost_estimate, float)


def test_provider_contract_timeout(provider_case: ProviderContractCase) -> None:
    provider = _configure_timeout_provider(provider_case)

    with pytest.raises(ProviderTimeout):
        provider_case.invoke(
            provider,
            ProviderRequest(request_id="req_timeout", payload=provider_case.timeout_payload, timeout_sec=0.01),
        )


def test_provider_contract_rate_limit(provider_case: ProviderContractCase) -> None:
    provider = _configure_rate_limit_provider(provider_case)

    with pytest.raises(ProviderRateLimit):
        provider_case.invoke(
            provider,
            ProviderRequest(request_id="req_rate", payload=provider_case.rate_limit_payload, timeout_sec=1.0),
        )


def test_provider_contract_invalid_output(provider_case: ProviderContractCase) -> None:
    provider = _configure_success_provider(provider_case)

    with pytest.raises(ProviderInvalidResponse):
        provider_case.invoke(
            provider,
            ProviderRequest(request_id="req_invalid", payload=provider_case.invalid_payload, timeout_sec=1.0),
        )
