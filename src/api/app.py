from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException

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
            "synopsis": "Synopsis généré par API prototype.",
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

    _REQUESTS[request_id] = {
        "request_id": request_id,
        "status": "succeeded",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "narrative": narrative,
    }
    return {"request_id": request_id, "status": "accepted"}


@app.get("/v1/generations/{request_id}")
def get_generation(request_id: str) -> dict[str, Any]:
    item = _REQUESTS.get(request_id)
    if item is None:
        raise HTTPException(status_code=404, detail="request_id inconnu")
    return item
