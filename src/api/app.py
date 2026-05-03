from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query

from src.core.project_store import DEFAULT_PROJECT_STORE
from src.core.schema_validator import (
    NarrativeValidationError,
    SCHEMAS_DIR,
    validate_narrative_document,
)

app = FastAPI(title="Narratech API", version="0.1.0")

_REQUESTS: dict[str, dict[str, Any]] = {}


def _build_minimal_narrative(*, request_id: str, prompt: str) -> dict[str, Any]:
    return {
        "request_id": request_id,
        "schema_version": "narrative.v1",
        "input": {"prompt": prompt, "duration_sec": 30, "style": "cinematic", "language": "fr"},
        "output": {
            "synopsis": f"Synopsis généré par API prototype: {prompt[:80]}",
            "characters": [{"id": "char_1", "name": "Narrateur", "role": "protagonist", "description": "Voix guide."}],
            "scenes": [{"id": "scene_1", "summary": "Introduction du sujet.", "duration_sec": 30}],
            "shots": [{"id": "shot_1", "scene_id": "scene_1", "description": "Plan large narratif", "duration_sec": 4.0}],
            "asset_refs": [],
            "audio_plan": {"voiceover": {"enabled": True, "language": "fr", "script": "Texte provisoire."}, "ambience": {"enabled": False}},
            "render_plan": {"resolution": "1080p", "fps": 24, "format": "mp4", "transitions": ["cut"]},
        },
        "provider_trace": [{"stage": "narrative_generation", "provider": "api_prototype", "model": "mock-model", "modele": "mock-model", "trace_id": "trace_local", "latency_ms": 0, "cost_estimate": 0.0, "retries": 0, "status": "success", "error": ""}],
    }


def _validate_user_context(payload: dict[str, Any]) -> None:
    schema_path = SCHEMAS_DIR / "user_context.v1.schema.json"
    candidate = payload.get("user_context")
    if candidate is None:
        return
    validate_narrative_document(candidate, schema_path=schema_path)


@app.post("/v1/generations")
def create_generation(payload: dict[str, Any]) -> dict[str, Any]:
    prompt = payload.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        raise HTTPException(status_code=400, detail="Champ 'prompt' requis (string non vide).")

    try:
        _validate_user_context(payload)
    except NarrativeValidationError as exc:
        raise HTTPException(status_code=400, detail=f"Payload invalide: {exc}") from exc

    request_id = f"req_{uuid4().hex}"
    narrative = _build_minimal_narrative(request_id=request_id, prompt=prompt.strip())
    try:
        validate_narrative_document(narrative)
    except NarrativeValidationError as exc:
        raise HTTPException(status_code=500, detail=f"Réponse invalide: {exc}") from exc

    generation = DEFAULT_PROJECT_STORE.create_generation(
        prompt=prompt.strip(),
        narrative=narrative,
        project_id=payload.get("project_id"),
        request_id=request_id,
        user_id=payload.get("user_id"),
        metadata={"status": "succeeded"},
        artifacts={"scene": f"outputs/{request_id}/scene.json", "final_video": "outputs/final/final_video.mp4"},
    )

    _REQUESTS[request_id] = {
        "request_id": request_id,
        "status": "succeeded",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "project_id": generation.project_id,
        "generation_id": generation.generation_id,
        "version": generation.version,
        "narrative": narrative,
    }
    return {
        "request_id": request_id,
        "status": "accepted",
        "project_id": generation.project_id,
        "generation_id": generation.generation_id,
        "version": generation.version,
    }


@app.get("/v1/generations/{request_id}")
def get_generation(request_id: str) -> dict[str, Any]:
    item = _REQUESTS.get(request_id)
    if item is None:
        raise HTTPException(status_code=404, detail="request_id inconnu")
    return item


@app.get("/v1/projects/{project_id}/generations")
def list_project_generations(project_id: str) -> dict[str, Any]:
    generations = DEFAULT_PROJECT_STORE.list_generations(project_id)
    return {
        "project_id": project_id,
        "count": len(generations),
        "items": [
            {
                "generation_id": g.generation_id,
                "version": g.version,
                "created_at": g.created_at,
                "prompt": g.prompt,
                "artifacts": g.artifacts,
            }
            for g in generations
        ],
    }


@app.post("/v1/projects/{project_id}/generations/{generation_id}/replay")
def replay_generation(project_id: str, generation_id: str) -> dict[str, Any]:
    source = DEFAULT_PROJECT_STORE.get_generation(generation_id)
    if source is None or source.project_id != project_id:
        raise HTTPException(status_code=404, detail="generation inconnue pour ce projet")
    replay = DEFAULT_PROJECT_STORE.create_generation(
        prompt=source.prompt,
        narrative=source.narrative,
        project_id=project_id,
        metadata={"replay_of": generation_id},
        artifacts=source.artifacts,
    )
    return {"project_id": project_id, "generation_id": replay.generation_id, "version": replay.version, "replay_of": generation_id}


@app.post("/v1/projects/{project_id}/generations/{generation_id}/export")
def export_generation(project_id: str, generation_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    request_id = payload.get("request_id") or f"req_{uuid4().hex}"
    export_target = payload.get("export_target", "final_video")
    try:
        DEFAULT_PROJECT_STORE.record_export(
            request_id=request_id,
            project_id=project_id,
            generation_id=generation_id,
            export_target=export_target,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "export_recorded", "request_id": request_id}


@app.delete("/v1/projects/{project_id}")
def hard_delete_project(project_id: str, user_id: str | None = Query(None), request_id: str | None = Query(None)) -> dict[str, Any]:
    try:
        deleted = DEFAULT_PROJECT_STORE.hard_delete(
            request_id=request_id or f"req_{uuid4().hex}",
            project_id=project_id,
            user_id=user_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {"status": "deleted", **deleted}


@app.get("/v1/projects/{project_id}/compare")
def compare_generations(project_id: str, left: str = Query(...), right: str = Query(...)) -> dict[str, Any]:
    try:
        return DEFAULT_PROJECT_STORE.compare_generations(project_id, left, right)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
