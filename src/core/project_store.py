from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


@dataclass(slots=True)
class GenerationRecord:
    project_id: str
    generation_id: str
    version: int
    prompt: str
    created_at: str
    narrative: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class ProjectRecord:
    project_id: str
    created_at: str
    latest_version: int = 0
    generation_ids: list[str] = field(default_factory=list)


class ProjectStore:
    """Store simple avec persistance JSON pour projets/générations/artefacts indexés."""

    def __init__(self, store_path: Path) -> None:
        self._store_path = store_path
        self._projects: dict[str, ProjectRecord] = {}
        self._generations: dict[str, GenerationRecord] = {}
        self._by_project: dict[str, list[str]] = {}
        self._artifact_index: dict[str, dict[str, str]] = {}
        self._load()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _load(self) -> None:
        if not self._store_path.exists():
            return
        payload = json.loads(self._store_path.read_text(encoding="utf-8"))
        for pid, project in payload.get("projects", {}).items():
            self._projects[pid] = ProjectRecord(**project)
        for gid, generation in payload.get("generations", {}).items():
            self._generations[gid] = GenerationRecord(**generation)
        self._by_project = payload.get("by_project", {})
        self._artifact_index = payload.get("artifact_index", {})

    def _save(self) -> None:
        self._store_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "projects": {pid: asdict(record) for pid, record in self._projects.items()},
            "generations": {gid: asdict(record) for gid, record in self._generations.items()},
            "by_project": self._by_project,
            "artifact_index": self._artifact_index,
        }
        self._store_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def create_generation(self, *, prompt: str, narrative: dict[str, Any], project_id: str | None = None, metadata: dict[str, Any] | None = None, artifacts: dict[str, str] | None = None) -> GenerationRecord:
        pid = project_id or f"prj_{uuid4().hex[:12]}"
        if pid not in self._projects:
            self._projects[pid] = ProjectRecord(project_id=pid, created_at=self._now())
            self._by_project[pid] = []
            self._artifact_index[pid] = {}

        project = self._projects[pid]
        project.latest_version += 1
        gid = f"gen_{uuid4().hex[:12]}"
        record = GenerationRecord(
            project_id=pid,
            generation_id=gid,
            version=project.latest_version,
            prompt=prompt,
            created_at=self._now(),
            narrative=narrative,
            metadata=metadata or {},
            artifacts=artifacts or {},
        )
        self._generations[gid] = record
        self._by_project[pid].append(gid)
        project.generation_ids.append(gid)
        for k, v in record.artifacts.items():
            self._artifact_index[pid][f"{gid}:{k}"] = v
        self._save()
        return record

    def get_generation(self, generation_id: str) -> GenerationRecord | None:
        return self._generations.get(generation_id)

    def list_generations(self, project_id: str) -> list[GenerationRecord]:
        return [self._generations[gid] for gid in self._by_project.get(project_id, []) if gid in self._generations]

    def compare_generations(self, project_id: str, left_generation_id: str, right_generation_id: str) -> dict[str, Any]:
        left = self._generations.get(left_generation_id)
        right = self._generations.get(right_generation_id)
        if left is None or right is None or left.project_id != project_id or right.project_id != project_id:
            raise KeyError("generation introuvable pour ce projet")
        left_synopsis = left.narrative.get("output", {}).get("synopsis", "")
        right_synopsis = right.narrative.get("output", {}).get("synopsis", "")
        return {
            "project_id": project_id,
            "left": {"generation_id": left.generation_id, "version": left.version, "synopsis": left_synopsis},
            "right": {"generation_id": right.generation_id, "version": right.version, "synopsis": right_synopsis},
            "diff": {
                "version_delta": right.version - left.version,
                "synopsis_changed": left_synopsis != right_synopsis,
                "artifacts_left": sorted(left.artifacts.keys()),
                "artifacts_right": sorted(right.artifacts.keys()),
            },
        }


DEFAULT_PROJECT_STORE = ProjectStore(Path("outputs/project_store/store.json"))
