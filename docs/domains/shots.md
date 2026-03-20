# Domaine `shots`

Ce domaine transforme le plan de shots en clips (ou placeholders) assemblables.

## Entrée

Composants principaux:
- `generate` (`src/generation/shot_generator.py`)
- retries/fallback ciblés dans `main.py`.

Payload provider (`ProviderRequest.payload`):

```json
{
  "request_id": "req_123",
  "output": {
    "shots": [
      {
        "id": "shot_001",
        "scene_id": "scene_001",
        "description": "Travelling avant dans le phare",
        "duration_sec": 6
      }
    ]
  },
  "asset_refs": [
    { "id": "asset_001", "type": "character", "uri": "local://assets/req_123/lina_character.json" }
  ],
  "user_profile": {
    "preferences": { "language": "fr", "rhythm": "medium" }
  }
}
```

## Sortie

- `outputs/shots/shots_manifest.json`
- fichiers `outputs/shots/shot_XXX_*.txt`
- `output.clips` enrichi.

Exemple de clip produit:

```json
{
  "path": "outputs/shots/shot_001_shot_001.txt",
  "shot_id": "shot_001",
  "request_id": "req_123",
  "duration": 6.0,
  "order": 1,
  "provider_trace": { "provider": "picsum_shot_provider", "status": "success" },
  "latency_ms": 1200,
  "cost_estimate": 0.02,
  "model_name": "picsum-shot-v1",
  "asset_dependencies": ["asset_001"],
  "clip_uri": "https://...",
  "local_path": null,
  "technical_metadata": { "fps": 24 }
}
```

## Erreurs usuelles

- `TypeError` / `ValueError` sur contrat `scene_doc.output`.
- `ValueError` si `data.clips` n'est pas une liste.
- `ProviderTimeout`, `ProviderRateLimit` (retry/fallback activés).
- `ProviderError` si provider ne renvoie aucun clip.
- Dégradation possible: placeholder clip avec `quality_flag = "degraded"`.
