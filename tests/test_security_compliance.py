from __future__ import annotations

import pytest

from src.main import _run_pre_publication_checks
from src.core.pipeline_state import PipelineRuntimeState, PipelineStage


def _state() -> PipelineRuntimeState:
    state = PipelineRuntimeState(
        request_id="req-test",
        current_stage=PipelineStage.SHOTS_GENERATED,
    )
    state.set_degradation(total_shots=1, degraded_shots=0)
    return state


def test_pre_publication_checks_block_on_secret_leak() -> None:
    enriched = {
        "metadata": {
            "consent": {
                "user_consent_for_generation": True,
                "user_consent_for_export": True,
            },
            "provenance": {
                "input_origin": "user_prompt",
                "generation_mode": "automated_pipeline",
                "human_review_required": False,
                "generated_at": "2026-01-01T00:00:00Z",
            },
        },
        "provider_trace": [{"provider": "mock"}],
        "notes": "token leaked: sk-1234567890ABCDEFG",
    }

    with pytest.raises(RuntimeError, match="no_secrets_detected"):
        _run_pre_publication_checks(
            enriched_narrative=enriched,
            consistency_report=[],
            state=_state(),
            schema_narrative_valid=True,
            schema_enriched_valid=True,
        )
