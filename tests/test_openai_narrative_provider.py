from __future__ import annotations

import os
import socket
from urllib import error

import pytest

from src.providers.base import (
    ProviderAuthError,
    ProviderInvalidResponse,
    ProviderRateLimit,
    ProviderRequest,
    ProviderTimeout,
)
from src.providers.factory import create_narrative_provider
from src.providers.narrative.openai_provider import OpenAINarrativeProvider


def test_openai_provider_builds_valid_response_and_trace() -> None:
    attempts: list[dict] = []

    def fake_transport(payload: dict, timeout: float, api_key: str, endpoint: str) -> dict:
        attempts.append(payload)
        assert timeout == 8.0
        assert api_key == "test-key"
        assert endpoint == "https://fake-openai.local/v1/responses"
        return {
            "output_text": '{"request_id":"req_1","schema_version":"narrative.v1","input":{"prompt":"Prompt","duration_sec":45,"style":"cinematic","language":"fr"},"output":{"synopsis":"Synopsis","characters":[{"id":"char_1","name":"Alex","role":"protagonist"}],"scenes":[{"id":"scene_1","summary":"Résumé","duration_sec":45}],"shots":[{"id":"shot_1","scene_id":"scene_1","description":"Plan","duration_sec":15.0}],"asset_refs":[],"audio_plan":{"voiceover":{"enabled":true,"language":"fr","script":"Texte"},"ambience":{"enabled":true,"description":"Ambiance"}},"render_plan":{"resolution":"1920x1080","fps":24,"format":"mp4","transitions":["cut"]}},"provider_trace":[{"stage":"story_generation","provider":"openai_narrative_provider","model":"gpt-4.1-mini","trace_id":"trace_x"}]}',
            "usage": {"input_tokens": 123, "output_tokens": 87, "total_tokens": 210},
        }

    provider = OpenAINarrativeProvider(transport=fake_transport)
    provider.configure(
        {
            "api_key": "test-key",
            "endpoint": "https://fake-openai.local/v1/responses",
            "include_prompt_in_trace": True,
        }
    )

    response = provider.generate_narrative(
        ProviderRequest(request_id="req_1", payload={"prompt": "Prompt"}, timeout_sec=8.0)
    )

    assert response.data["request_id"] == "req_1"
    assert response.data["schema_version"] == "narrative.v1"
    assert isinstance(response.data["provider_trace"], list)
    assert response.provider_trace["usage"]["total_tokens"] == 210
    assert "prompt" in response.provider_trace
    assert len(attempts) == 1


def test_openai_provider_remediates_invalid_json() -> None:
    calls = {"count": 0}

    def fake_transport(payload: dict, timeout: float, api_key: str, endpoint: str) -> dict:
        calls["count"] += 1
        if calls["count"] == 1:
            return {"output_text": "not-a-json", "usage": {"total_tokens": 1}}
        return {
            "output_text": '{"request_id":"req_2","schema_version":"narrative.v1","input":{"prompt":"Prompt","duration_sec":45,"style":"cinematic","language":"fr"},"output":{"synopsis":"Synopsis","characters":[{"id":"char_1","name":"Alex","role":"protagonist"}],"scenes":[{"id":"scene_1","summary":"Résumé","duration_sec":45}],"shots":[{"id":"shot_1","scene_id":"scene_1","description":"Plan","duration_sec":15.0}],"asset_refs":[],"audio_plan":{"voiceover":{"enabled":true},"ambience":{"enabled":true}},"render_plan":{"resolution":"1920x1080","fps":24,"format":"mp4"}},"provider_trace":[{"stage":"story_generation","provider":"openai_narrative_provider","model":"gpt-4.1-mini","trace_id":"trace_y"}]}'
        }

    provider = OpenAINarrativeProvider(transport=fake_transport)
    provider.configure({"api_key": "test-key", "max_remediation_attempts": 1})

    response = provider.generate_narrative(
        ProviderRequest(request_id="req_2", payload={"prompt": "Prompt"}, timeout_sec=8.0)
    )

    assert response.data["request_id"] == "req_2"
    assert calls["count"] == 2


def test_openai_provider_raises_when_api_key_missing() -> None:
    provider = OpenAINarrativeProvider(transport=lambda *_: {})

    with pytest.raises(ProviderAuthError):
        provider.configure({})


def test_factory_selects_openai_provider_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NARRATECH_NARRATIVE_PROVIDER", "openai_narrative")
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")

    provider = create_narrative_provider({"type": "mock_narrative", "config": {}})

    assert isinstance(provider, OpenAINarrativeProvider)

    monkeypatch.delenv("NARRATECH_NARRATIVE_PROVIDER")
    monkeypatch.delenv("OPENAI_API_KEY")


def test_openai_provider_fails_after_exhausted_remediation() -> None:
    provider = OpenAINarrativeProvider(transport=lambda *_: {"output_text": "{}"})
    provider.configure({"api_key": "test-key", "max_remediation_attempts": 0})

    with pytest.raises(ProviderInvalidResponse):
        provider.generate_narrative(ProviderRequest(request_id="req_3", payload={"prompt": "Prompt"}))


def test_openai_provider_retries_with_exponential_backoff_and_jitter(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}
    sleeps: list[float] = []

    def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    def fake_transport(payload: dict, timeout: float, api_key: str, endpoint: str) -> dict:
        calls["count"] += 1
        if calls["count"] < 3:
            raise ProviderTimeout("temporary timeout")
        return {
            "output_text": '{"request_id":"req_4","schema_version":"narrative.v1","input":{"prompt":"Prompt","duration_sec":45,"style":"cinematic","language":"fr"},"output":{"synopsis":"Synopsis","characters":[{"id":"char_1","name":"Alex","role":"protagonist"}],"scenes":[{"id":"scene_1","summary":"Résumé","duration_sec":45}],"shots":[{"id":"shot_1","scene_id":"scene_1","description":"Plan","duration_sec":15.0}],"asset_refs":[],"audio_plan":{"voiceover":{"enabled":true},"ambience":{"enabled":true}},"render_plan":{"resolution":"1920x1080","fps":24,"format":"mp4"}},"provider_trace":[{"stage":"story_generation","provider":"openai_narrative_provider","model":"gpt-4.1-mini","trace_id":"trace_retry"}]}'
        }

    monkeypatch.setattr("src.providers.narrative.openai_provider.time.sleep", fake_sleep)
    monkeypatch.setattr("src.providers.narrative.openai_provider.random.uniform", lambda _a, _b: 0.0)

    provider = OpenAINarrativeProvider(transport=fake_transport)
    provider.configure(
        {
            "api_key": "test-key",
            "retry_max_attempts": 2,
            "retry_base_delay_sec": 0.1,
            "retry_max_delay_sec": 1.0,
            "retry_jitter_sec": 0.2,
        }
    )

    provider.generate_narrative(ProviderRequest(request_id="req_4", payload={"prompt": "Prompt"}))

    assert calls["count"] == 3
    assert sleeps == [0.1, 0.2]


def test_openai_provider_circuit_breaker_opens_after_consecutive_failures() -> None:
    provider = OpenAINarrativeProvider(transport=lambda *_: (_ for _ in ()).throw(ProviderRateLimit("quota")))
    provider.configure(
        {
            "api_key": "test-key",
            "retry_max_attempts": 0,
            "circuit_breaker_enabled": True,
            "circuit_breaker_failure_threshold": 1,
            "circuit_breaker_open_sec": 60.0,
        }
    )

    with pytest.raises(ProviderRateLimit, match="quota"):
        provider.generate_narrative(ProviderRequest(request_id="req_cb_1", payload={"prompt": "Prompt"}))

    with pytest.raises(ProviderRateLimit, match="Circuit breaker"):
        provider.generate_narrative(ProviderRequest(request_id="req_cb_2", payload={"prompt": "Prompt"}))


def test_openai_provider_maps_transport_errors_to_unified_provider_errors() -> None:
    provider_timeout = OpenAINarrativeProvider(
        transport=lambda *_: (_ for _ in ()).throw(error.URLError(socket.timeout("timed out")))
    )
    provider_timeout.configure({"api_key": "test-key", "retry_max_attempts": 0})
    with pytest.raises(ProviderTimeout):
        provider_timeout.generate_narrative(
            ProviderRequest(request_id="req_map_1", payload={"prompt": "Prompt"}, timeout_sec=2.0)
        )

    provider_http = OpenAINarrativeProvider(
        transport=lambda *_: (_ for _ in ()).throw(
            error.HTTPError(url="https://api.openai.com/v1/responses", code=429, msg="Too Many Requests", hdrs=None, fp=None)
        )
    )
    provider_http.configure({"api_key": "test-key", "retry_max_attempts": 0})
    with pytest.raises(ProviderRateLimit):
        provider_http.generate_narrative(
            ProviderRequest(request_id="req_map_2", payload={"prompt": "Prompt"}, timeout_sec=2.0)
        )


@pytest.fixture(autouse=True)
def _cleanup_env() -> None:
    previous = os.environ.get("OPENAI_API_KEY")
    yield
    if previous is None and "OPENAI_API_KEY" in os.environ:
        del os.environ["OPENAI_API_KEY"]
