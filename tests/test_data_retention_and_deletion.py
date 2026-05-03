from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.core.project_store import ProjectStore


def test_immutable_audit_trail_generation_export_delete(tmp_path) -> None:
    store = ProjectStore(tmp_path / "store.json")
    gen = store.create_generation(
        prompt="p",
        narrative={"output": {"synopsis": "x"}},
        project_id="prj_1",
        request_id="req_gen_1",
        artifacts={"scene": "outputs/scene.json"},
    )
    store.record_export(request_id="req_exp_1", project_id="prj_1", generation_id=gen.generation_id, export_target="final_video")
    store.hard_delete(request_id="req_del_1", project_id="prj_1")

    audit = store.get_audit_log()
    assert [e.action for e in audit] == ["generation", "export", "hard_delete"]
    assert all(e.request_id.startswith("req_") for e in audit)
    assert all(datetime.fromisoformat(e.occurred_at_utc).tzinfo == timezone.utc for e in audit)
    for idx in range(1, len(audit)):
        assert audit[idx].previous_hash == audit[idx - 1].event_hash


def test_retention_policy_and_hard_delete_non_referencable(tmp_path) -> None:
    store = ProjectStore(tmp_path / "store.json")
    old_created = "2020-01-01T00:00:00+00:00"
    gen = store.create_generation(
        prompt="p",
        narrative={"output": {"synopsis": "old"}},
        project_id="prj_2",
        request_id="req_old",
        artifacts={"scene": "outputs/old_scene.json"},
        metadata={"created_for_test": True},
    )
    store._generations[gen.generation_id].created_at = old_created
    store.set_retention_policy(artifact_retention_days=1, log_retention_days=1)
    report = store.enforce_retention(now=datetime(2026, 5, 3, tzinfo=timezone.utc))
    assert report["cleared_artifacts"] >= 1
    assert store.get_generation(gen.generation_id) is not None
    assert store.get_generation(gen.generation_id).artifacts == {}

    store.hard_delete(request_id="req_hard", project_id="prj_2")
    assert store.get_generation(gen.generation_id) is None
    assert store.list_generations("prj_2") == []
    with pytest.raises(KeyError):
        store.compare_generations("prj_2", gen.generation_id, gen.generation_id)
