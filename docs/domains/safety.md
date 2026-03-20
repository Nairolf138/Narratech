# Domaine `safety`

Ce domaine filtre les contenus interdits via blacklist configurable + audit.

## Entrée

Composant principal: `SafetyGuard` (`src/core/safety.py`).

Sources d'entrée:
- prompt brut (`validate_prompt`),
- payload output enrichi (`validate_output`),
- blacklist JSON (`config/safety_blacklist.json` ou chemin défini dans `.narratech_safety_blacklist_path`).

Exemple blacklist:

```json
{
  "blacklist": {
    "violence_extreme": ["décapitation", "torture explicite"],
    "self_harm": ["comment se blesser", "guide suicide"]
  }
}
```

## Sortie

- Journal d'audit: `outputs/safety_audit.json` (événements append-only bornés).
- En cas de violation: exception `SafetyBlockError` avec `event` structuré.

Exemple d'événement d'audit:

```json
{
  "timestamp": "2026-03-20T12:34:56.000000+00:00",
  "request_id": "req_123",
  "session_id": "session_demo",
  "phase": "post_generation_output",
  "decision": "blocked",
  "message": "Blocage safety: contenu interdit détecté (...)",
  "violations": [
    {
      "phase": "post_generation_output",
      "path": "$.output.shots[0].description",
      "category": "violence_extreme",
      "term": "torture explicite",
      "excerpt": "..."
    }
  ]
}
```

## Erreurs usuelles

- `SafetyBlockError`: blocage métier explicite.
- JSON blacklist invalide: blacklist ignorée (retour `{}`), donc vigilance de configuration.
