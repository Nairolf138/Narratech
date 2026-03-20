from __future__ import annotations

import json
from pathlib import Path

from src.core.feedback_engine import FeedbackAuditStore, FeedbackEngine, FeedbackStore


def test_feedback_capture_and_adjustments_are_structured(tmp_path: Path) -> None:
    store = FeedbackStore(path=tmp_path / "feedback_history.json")
    audit_store = FeedbackAuditStore(path=tmp_path / "feedback_audit.json")
    engine = FeedbackEngine(feedback_store=store, audit_store=audit_store)

    feedback_event = engine.capture_feedback(
        request_id="req_001",
        session_id="session_abc",
        feedback_payload={
            "global_note": 2,
            "dimensions": {"histoire": 1, "style": 2, "rythme": 1},
            "commentaire": "histoire confuse",
        },
    )

    assert feedback_event is not None
    adjustments = engine.derive_adjustments(feedback_event=feedback_event)
    assert adjustments.story == "clarify"
    assert adjustments.style == "stabilize"
    assert adjustments.rhythm == "slow_down"
    assert adjustments.instructions

    audit_event = engine.audit_adjustments(
        request_id="req_001",
        session_id="session_abc",
        source_request_id="req_001",
        adjustments=adjustments,
    )
    assert audit_event["decisions"]["story"] == "clarify"

    history = json.loads((tmp_path / "feedback_history.json").read_text(encoding="utf-8"))
    assert history["session_abc"][0]["request_id"] == "req_001"


def test_latest_adjustments_use_last_feedback_event(tmp_path: Path) -> None:
    store = FeedbackStore(path=tmp_path / "feedback_history.json")
    engine = FeedbackEngine(feedback_store=store)

    engine.capture_feedback(
        request_id="req_001",
        session_id="session_1",
        feedback_payload={"global_note": 4, "dimensions": {"histoire": 4, "style": 4, "rythme": 4}},
    )
    engine.capture_feedback(
        request_id="req_002",
        session_id="session_1",
        feedback_payload={"global_note": 1, "dimensions": {"histoire": 1, "style": 1, "rythme": 1}},
    )

    latest = engine.latest_adjustments_for_session(session_id="session_1")
    assert latest is not None
    assert latest.story == "clarify"
    assert latest.style == "stabilize"
    assert latest.rhythm == "slow_down"
