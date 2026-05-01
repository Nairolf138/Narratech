# API Contracts — Narratech Prototype

## Endpoints

### `POST /v1/generations`
Crée une demande de génération.

Payload minimal:
```json
{
  "prompt": "Raconte une aventure.",
  "user_context": {
    "preferences": {"genre": "sci-fi", "ambiance": "uplifting", "rhythm": "medium", "duration_sec": 30, "language": "fr"},
    "constraints": {"age_rating": "all", "culture": "global", "exclusions": []},
    "identity": {"session_id": "session_001"}
  }
}
```

Validation:
- `prompt` string non vide.
- `user_context` validé via `schemas/user_context.v1.schema.json`.

Réponse 200:
```json
{"request_id": "req_xxx", "status": "accepted"}
```

### `GET /v1/generations/{request_id}`
Retourne le statut + résultat narratif.

Réponse 200:
```json
{
  "request_id": "req_xxx",
  "status": "succeeded",
  "created_at": "2026-05-01T00:00:00+00:00",
  "narrative": {"...": "..."}
}
```

Validation:
- `narrative` est validé via `schemas/narrative.v1.schema.json` avant stockage.

## Intégration UI prototype

`scripts/ui_prototype_server.py` supporte un mode API:
- `NARRATECH_UI_API_MODE=1`
- `NARRATECH_API_BASE_URL=http://127.0.0.1:8000`

Dans ce mode, `POST /api/generation-request` est proxyfié vers `POST /v1/generations`.
