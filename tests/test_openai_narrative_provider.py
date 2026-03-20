from __future__ import annotations

import os

import pytest

from src.providers.base import ProviderAuthError, ProviderInvalidResponse, ProviderRequest
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


@pytest.fixture(autouse=True)
def _cleanup_env() -> None:
    previous = os.environ.get("OPENAI_API_KEY")
    yield
    if previous is None and "OPENAI_API_KEY" in os.environ:
        del os.environ["OPENAI_API_KEY"]
