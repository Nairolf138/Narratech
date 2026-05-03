from __future__ import annotations

import json
from hashlib import sha256
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
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
    user_id: str | None = None


@dataclass(slots=True)
class RetentionPolicy:
    artifact_retention_days: int = 30
    log_retention_days: int = 365


@dataclass(slots=True)
class AuditEvent:
    event_id: str
    request_id: str
    action: str
    project_id: str
    generation_id: str | None
    occurred_at_utc: str
    details: dict[str, Any] = field(default_factory=dict)
    previous_hash: str = ""
    event_hash: str = ""


class ProjectStore:
    """Store simple avec persistance JSON pour projets/générations/artefacts indexés."""

    def __init__(self, store_path: Path) -> None:
        self._store_path = store_path
        self._projects: dict[str, ProjectRecord] = {}
        self._generations: dict[str, GenerationRecord] = {}
        self._by_project: dict[str, list[str]] = {}
        self._artifact_index: dict[str, dict[str, str]] = {}
        self._audit_log: list[AuditEvent] = []
        self._retention_policy = RetentionPolicy()
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
        retention = payload.get("retention_policy", {})
        self._retention_policy = RetentionPolicy(
            artifact_retention_days=int(retention.get("artifact_retention_days", 30)),
            log_retention_days=int(retention.get("log_retention_days", 365)),
        )
        for item in payload.get("audit_log", []):
            self._audit_log.append(AuditEvent(**item))

    def _save(self) -> None:
        self._store_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "projects": {pid: asdict(record) for pid, record in self._projects.items()},
            "generations": {gid: asdict(record) for gid, record in self._generations.items()},
            "by_project": self._by_project,
            "artifact_index": self._artifact_index,
            "retention_policy": asdict(self._retention_policy),
            "audit_log": [asdict(event) for event in self._audit_log],
        }
        self._store_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _append_audit_event(self, *, request_id: str, action: str, project_id: str, generation_id: str | None, details: dict[str, Any] | None = None) -> None:
        occurred_at = self._now()
        previous_hash = self._audit_log[-1].event_hash if self._audit_log else "GENESIS"
        body = f"{request_id}|{action}|{project_id}|{generation_id or ''}|{occurred_at}|{json.dumps(details or {}, sort_keys=True)}|{previous_hash}"
        event_hash = sha256(body.encode("utf-8")).hexdigest()
        self._audit_log.append(
            AuditEvent(
                event_id=f"evt_{uuid4().hex[:12]}",
                request_id=request_id,
                action=action,
                project_id=project_id,
                generation_id=generation_id,
                occurred_at_utc=occurred_at,
                details=details or {},
                previous_hash=previous_hash,
                event_hash=event_hash,
            )
        )

    def set_retention_policy(self, *, artifact_retention_days: int, log_retention_days: int) -> None:
        self._retention_policy = RetentionPolicy(
            artifact_retention_days=max(0, artifact_retention_days),
            log_retention_days=max(1, log_retention_days),
        )
        self._save()

    def create_generation(self, *, prompt: str, narrative: dict[str, Any], project_id: str | None = None, metadata: dict[str, Any] | None = None, artifacts: dict[str, str] | None = None, request_id: str | None = None, user_id: str | None = None) -> GenerationRecord:
        pid = project_id or f"prj_{uuid4().hex[:12]}"
        if pid not in self._projects:
            self._projects[pid] = ProjectRecord(project_id=pid, created_at=self._now(), user_id=user_id)
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
        self._append_audit_event(
            request_id=request_id or f"req_{uuid4().hex}",
            action="generation",
            project_id=pid,
            generation_id=gid,
            details={"artifact_count": len(record.artifacts)},
        )
        self._save()
        return record

    def record_export(self, *, request_id: str, project_id: str, generation_id: str, export_target: str) -> None:
        if generation_id not in self._generations or self._generations[generation_id].project_id != project_id:
            raise KeyError("generation introuvable pour ce projet")
        self._append_audit_event(
            request_id=request_id,
            action="export",
            project_id=project_id,
            generation_id=generation_id,
            details={"export_target": export_target},
        )
        self._save()

    def hard_delete(self, *, request_id: str, project_id: str, user_id: str | None = None) -> dict[str, int]:
        project = self._projects.get(project_id)
        if project is None:
            raise KeyError("projet introuvable")
        if user_id is not None and project.user_id is not None and user_id != project.user_id:
            raise PermissionError("suppression refusée: user_id non autorisé")

        generation_ids = list(self._by_project.get(project_id, []))
        for gid in generation_ids:
            self._generations.pop(gid, None)
        self._by_project.pop(project_id, None)
        self._artifact_index.pop(project_id, None)
        self._projects.pop(project_id, None)

        self._append_audit_event(request_id=request_id, action="hard_delete", project_id=project_id, generation_id=None, details={"deleted_generations": len(generation_ids)})
        self._save()
        return {"deleted_generations": len(generation_ids)}

    def enforce_retention(self, *, now: datetime | None = None) -> dict[str, int]:
        ref = now or datetime.now(timezone.utc)
        artifacts_cutoff = ref - timedelta(days=self._retention_policy.artifact_retention_days)
        logs_cutoff = ref - timedelta(days=self._retention_policy.log_retention_days)
        cleared_artifacts = 0
        for generation in self._generations.values():
            created = datetime.fromisoformat(generation.created_at)
            if created < artifacts_cutoff and generation.artifacts:
                cleared_artifacts += len(generation.artifacts)
                generation.artifacts = {}
        for pid, index in self._artifact_index.items():
            keys = list(index.keys())
            for key in keys:
                gid = key.split(":", 1)[0]
                generation = self._generations.get(gid)
                if generation is None or not generation.artifacts:
                    index.pop(key, None)

        self._audit_log = [event for event in self._audit_log if datetime.fromisoformat(event.occurred_at_utc) >= logs_cutoff]
        self._save()
        return {"cleared_artifacts": cleared_artifacts}

    def get_audit_log(self) -> list[AuditEvent]:
        return list(self._audit_log)

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
