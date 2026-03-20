# Domaine `narrative`

Ce domaine couvre la génération du document narratif initial à partir du prompt utilisateur.

## Entrée

Composant principal: `StoryEngine.generate` (`src/core/story_engine.py`).

Payload provider (`ProviderRequest.payload`):

```json
{
  "prompt": "Une enquêtrice retrouve un message caché dans un phare.",
  "user_profile": {
    "preferences": {
      "language": "fr",
      "style": "cinematic",
      "rhythm": "medium"
    },
    "constraints": {
      "age_rating": "PG-13"
    },
    "identity": {
      "session_id": "session_demo"
    }
  }
}
```

## Sortie

Sortie logique: un document narratif dans `ProviderResponse.data`, puis persistance dans `outputs/scene.json`.

Exemple minimal de sortie (abrégée):

```json
{
  "schema_version": "narrative.v1",
  "request_id": "req_123",
  "input": {
    "prompt": "Une enquêtrice retrouve un message caché dans un phare."
  },
  "output": {
    "synopsis": "...",
    "characters": [{ "id": "char_001", "name": "Lina" }],
    "scenes": [{ "id": "scene_001", "summary": "..." }],
    "shots": [{ "id": "shot_001", "scene_id": "scene_001", "description": "..." }],
    "audio_plan": {
      "voiceover": { "enabled": true, "script": "...", "language": "fr", "style": "narrative" },
      "ambience": { "enabled": true, "description": "vent et mer", "language": "fr", "style": "ambient" }
    }
  },
  "provider_trace": [
    {
      "stage": "story_generation",
      "provider": "mock_narrative_provider",
      "model": "mock-narrative-v1",
      "latency_ms": 9,
      "cost_estimate": 0.0,
      "retries": 0,
      "status": "success",
      "error": null
    }
  ]
}
```

## Erreurs usuelles

- `ValueError`: prompt vide.
- `ProviderTimeout`, `ProviderRateLimit`: erreurs transitoires provider.
- `ProviderAuthError`: problème d'auth provider.
- `ProviderInvalidResponse`: réponse hors contrat.
- `NarrativeValidationError`: document narratif invalide au regard du schéma.
