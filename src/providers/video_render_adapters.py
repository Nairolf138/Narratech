"""Adaptateurs de rendu vidéo pour ShotProvider asynchrone."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from uuid import uuid4


@dataclass(slots=True)
class RenderSubmission:
    """Réponse normalisée d'une soumission de rendu vidéo."""

    job_id: str
    provider_job_ref: str
    submitted_at_epoch_ms: int


@dataclass(slots=True)
class RenderStatus:
    """État normalisé d'un rendu vidéo en cours."""

    status: str
    clip_uri: str | None = None
    local_path: str | None = None
    technical_metadata: Mapping[str, object] | None = None


class VideoRenderAdapter(ABC):
    """Interface commune aux adaptateurs fournisseurs vidéo."""

    @abstractmethod
    def configure(self, config: Mapping[str, object]) -> None:
        """Charge la configuration de l'adaptateur."""

    @abstractmethod
    def submit_render(self, *, prompt: str, shot_id: str, duration_sec: float, request_id: str) -> RenderSubmission:
        """Soumet un rendu asynchrone pour un shot."""

    @abstractmethod
    def get_render_status(self, job_id: str) -> RenderStatus:
        """Retourne l'état d'avancement d'un rendu asynchrone."""


class _InMemoryAsyncAdapter(VideoRenderAdapter):
    """Base commune simulant un backend asynchrone avec polling."""

    provider_name = "in_memory"

    def __init__(self) -> None:
        self._config: dict[str, object] = {
            "polls_before_completed": 2,
            "fps": 24,
            "width": 1280,
            "height": 720,
            "codec": "h264",
            "base_uri": "memory://renders",
            "base_path": "outputs/shots/renders",
        }
        self._jobs: dict[str, dict[str, object]] = {}

    def configure(self, config: Mapping[str, object]) -> None:
        merged = dict(self._config)
        merged.update(dict(config))
        self._config = merged

    def submit_render(self, *, prompt: str, shot_id: str, duration_sec: float, request_id: str) -> RenderSubmission:
        job_id = f"{self.provider_name}_job_{uuid4().hex[:10]}"
        now_ms = int(time.time() * 1000)
        self._jobs[job_id] = {
            "prompt": prompt,
            "shot_id": shot_id,
            "duration_sec": duration_sec,
            "request_id": request_id,
            "poll_count": 0,
        }
        return RenderSubmission(
            job_id=job_id,
            provider_job_ref=f"{self.provider_name}:{job_id}",
            submitted_at_epoch_ms=now_ms,
        )

    def get_render_status(self, job_id: str) -> RenderStatus:
        job = self._jobs.get(job_id)
        if job is None:
            return RenderStatus(status="failed", technical_metadata={"reason": "unknown_job"})

        job["poll_count"] = int(job.get("poll_count", 0)) + 1
        polls_before_completed = int(self._config.get("polls_before_completed") or 2)
        if int(job["poll_count"]) < polls_before_completed:
            return RenderStatus(status="running")

        shot_id = str(job.get("shot_id") or "shot_unknown")
        request_id = str(job.get("request_id") or "request_unknown")
        base_uri = str(self._config.get("base_uri") or "memory://renders").rstrip("/")
        base_path = str(self._config.get("base_path") or "outputs/shots/renders").rstrip("/")

        clip_uri = f"{base_uri}/{request_id}/{shot_id}.mp4"
        local_path = f"{base_path}/{request_id}/{shot_id}.mp4"
        technical_metadata = {
            "fps": int(self._config.get("fps") or 24),
            "width": int(self._config.get("width") or 1280),
            "height": int(self._config.get("height") or 720),
            "codec": str(self._config.get("codec") or "h264"),
            "poll_attempts": int(job["poll_count"]),
            "provider_name": self.provider_name,
        }
        return RenderStatus(
            status="completed",
            clip_uri=clip_uri,
            local_path=local_path,
            technical_metadata=technical_metadata,
        )


class LocalVideoRenderAdapter(_InMemoryAsyncAdapter):
    """Adaptateur local simulé, utile pour tests/intégration offline."""

    provider_name = "local"


class KlingVideoRenderAdapter(_InMemoryAsyncAdapter):
    """Adaptateur Kling (simulation contractuelle dans V1)."""

    provider_name = "kling"


class RunwayVideoRenderAdapter(_InMemoryAsyncAdapter):
    """Adaptateur Runway (simulation contractuelle dans V1)."""

    provider_name = "runway"
