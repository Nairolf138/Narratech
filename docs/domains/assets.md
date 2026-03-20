# Domaine `assets`

Ce domaine produit les assets persistants (personnages, environnements, références visuelles).

## Entrée

Composant principal: `generate` (`src/generation/asset_generator.py`).

Payload provider (`ProviderRequest.payload`):

```json
{
  "request_id": "req_123",
  "output": {
    "synopsis": "...",
    "characters": [{ "id": "char_001", "name": "Lina" }],
    "scenes": [{ "id": "scene_001" }],
    "shots": [{ "id": "shot_001" }]
  },
  "user_profile": {
    "preferences": { "language": "fr" },
    "constraints": { "age_rating": "PG-13" }
  }
}
```

## Sortie

- `assets/<request_id>/assets_manifest.json`
- `output.asset_refs` enrichi dans le document pipeline.

Exemple `asset_refs`:

```json
[
  {
    "id": "asset_001",
    "type": "character",
    "uri": "local://assets/req_123/lina_character.json",
    "metadata_uri": null,
    "seed": 42,
    "generation_params": { "style": "cinematic" },
    "request_id": "req_123",
    "provider_trace": { "provider": "mock_asset_provider", "status": "success" },
    "personalization": { "language": "fr", "age_rating": "PG-13" },
    "latency_ms": 7,
    "cost_estimate": 0.0,
    "model_name": "mock-asset-v1"
  }
]
```

## Erreurs usuelles

- `TypeError`: `scene_doc` non-dict.
- `ValueError`: `scene_doc.output` absent/invalide.
- `ValueError`: `data.assets` provider non-list.
- `ValueError`: URI asset invalide (doit commencer par `local://`).
- Erreurs provider normalisées: `ProviderTimeout`, `ProviderRateLimit`, `ProviderAuthError`, `ProviderInvalidResponse`.
