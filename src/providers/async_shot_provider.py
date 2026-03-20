"""ShotProvider concret avec rendu asynchrone + adaptateurs multiples."""

from __future__ import annotations

import time
from collections.abc import Mapping
from uuid import uuid4

from src.providers.adapter import call_with_normalized_errors
from src.providers.base import BaseProvider, ProviderHealth, ProviderInvalidResponse, ProviderRequest, ProviderResponse, ProviderTimeout
from src.providers.contracts import ShotProviderContract
from src.providers.video_render_adapters import (
    KlingVideoRenderAdapter,
    LocalVideoRenderAdapter,
    RunwayVideoRenderAdapter,
    VideoRenderAdapter,
)


class AsyncShotProvider(BaseProvider, ShotProviderContract):
    """Génère des clips via un backend de rendu asynchrone (local/Kling/Runway)."""

    def __init__(self) -> None:
        self._config: dict[str, object] = {
            "backend": "local",
            "poll_interval_sec": 0.01,
            "max_poll_attempts": 10,
            "prompt_template": (
                "Create cinematic shot for '{shot_id}': {description}. "
                "Duration={duration_sec}s. Style={style}. Assets={asset_hints}."
            ),
            "default_style": "documentary-realistic",
        }
        self._adapter: VideoRenderAdapter = LocalVideoRenderAdapter()

    def configure(self, config: Mapping[str, object]) -> None:
        merged = dict(self._config)
        merged.update(dict(config))
        self._config = merged

        backend = str(self._config.get("backend") or "local").lower()
        if backend == "kling":
            self._adapter = KlingVideoRenderAdapter()
        elif backend == "runway":
            self._adapter = RunwayVideoRenderAdapter()
        else:
            self._adapter = LocalVideoRenderAdapter()

        adapter_config = self._config.get("adapter_config")
        if isinstance(adapter_config, dict):
            self._adapter.configure(adapter_config)

    def generate_shots(self, request: ProviderRequest) -> ProviderResponse:
        return call_with_normalized_errors(lambda: self._generate_shots_impl(request))

    def _extract_shots_manifest(self, payload: Mapping[str, object]) -> list[dict[str, object]]:
        manifest = payload.get("shots_manifest")
        if isinstance(manifest, dict):
            clips = manifest.get("clips")
            if isinstance(clips, list):
                return [item for item in clips if isinstance(item, dict)]
            shots = manifest.get("shots")
            if isinstance(shots, list):
                return [item for item in shots if isinstance(item, dict)]

        output = payload.get("output")
        if isinstance(output, dict) and isinstance(output.get("shots"), list):
            return [item for item in output["shots"] if isinstance(item, dict)]

        raise ProviderInvalidResponse("payload.shots_manifest (ou payload.output.shots) doit être fourni")

    def _map_prompt(self, shot: Mapping[str, object], order: int, asset_ids: list[str]) -> str:
        shot_id = str(shot.get("id") or shot.get("shot_id") or f"shot_{order:03d}")
        description = str(shot.get("enriched_prompt") or shot.get("description") or "")
        duration = float(shot.get("duration_sec") or shot.get("duration") or 0.0)
        style = str(shot.get("style") or self._config.get("default_style") or "neutral")
        template = str(self._config.get("prompt_template") or "{description}")

        return template.format(
            shot_id=shot_id,
            description=description,
            duration_sec=duration,
            style=style,
            asset_hints=",".join(asset_ids) if asset_ids else "none",
        )

    def _generate_shots_impl(self, request: ProviderRequest) -> ProviderResponse:
        if not isinstance(request.payload, Mapping):
            raise ProviderInvalidResponse("payload doit être un objet")

        request_payload = request.payload
        shots_manifest = self._extract_shots_manifest(request_payload)
        asset_refs = request_payload.get("asset_refs", [])
        if not isinstance(asset_refs, list):
            raise ProviderInvalidResponse("payload.asset_refs doit être une liste")
        asset_ids = [
            str(asset.get("id"))
            for asset in asset_refs
            if isinstance(asset, dict) and asset.get("id") is not None
        ]

        start = time.perf_counter()
        poll_interval_sec = float(self._config.get("poll_interval_sec") or 0.01)
        max_poll_attempts = int(self._config.get("max_poll_attempts") or 10)

        clips: list[dict[str, object]] = []
        backend = str(self._config.get("backend") or "local")

        for order, shot in enumerate(shots_manifest, start=1):
            shot_id = str(shot.get("id") or shot.get("shot_id") or f"shot_{order:03d}")
            duration = float(shot.get("duration_sec") or shot.get("duration") or 0.0)
            prompt = self._map_prompt(shot, order, asset_ids)

            submission = self._adapter.submit_render(
                prompt=prompt,
                shot_id=shot_id,
                duration_sec=duration,
                request_id=request.request_id,
            )

            final_status = None
            for _ in range(max_poll_attempts):
                status = self._adapter.get_render_status(submission.job_id)
                if status.status == "completed":
                    final_status = status
                    break
                if status.status == "failed":
                    raise ProviderInvalidResponse(f"Rendu échoué pour shot '{shot_id}'")
                time.sleep(poll_interval_sec)

            if final_status is None:
                raise ProviderTimeout(f"Timeout polling rendu shot '{shot_id}'")

            metadata = dict(final_status.technical_metadata or {})
            metadata["provider_job_id"] = submission.job_id
            metadata["provider_job_ref"] = submission.provider_job_ref
            metadata["submitted_at_epoch_ms"] = submission.submitted_at_epoch_ms

            clips.append(
                {
                    "order": order,
                    "shot_id": shot_id,
                    "duration": duration,
                    "prompt": prompt,
                    "description_enriched": str(shot.get("enriched_prompt") or shot.get("description") or ""),
                    "file_name": f"shot_{order:03d}_{shot_id}.mp4",
                    "clip_uri": final_status.clip_uri,
                    "local_path": final_status.local_path,
                    "asset_dependencies": asset_ids,
                    "technical_metadata": metadata,
                }
            )

        latency_ms = int((time.perf_counter() - start) * 1000)
        model_name = f"{backend}-video-render-v1"
        return ProviderResponse(
            data={"clips": clips},
            provider_trace={
                "stage": "shot_generation",
                "provider": "async_shot_provider",
                "backend": backend,
                "model": model_name,
                "trace_id": f"trace_{uuid4().hex[:12]}",
                "clip_count": len(clips),
            },
            latency_ms=latency_ms,
            cost_estimate=0.02 * len(clips),
            model_name=model_name,
        )

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        return self.generate_shots(request)

    def healthcheck(self) -> ProviderHealth:
        return ProviderHealth(ok=True, details={"provider": "async_shot_provider", "backend": self._config.get("backend", "local")})
