# Domaine `audio`

Ce domaine génère la voix off et l'ambiance depuis `output.audio_plan`.

## Entrée

Composant principal: `build_from_audio_plan` (`src/assembly/audio_engine.py`).

Contrat attendu dans `scene_doc.output.audio_plan`:

```json
{
  "voiceover": {
    "enabled": true,
    "script": "Lina entre dans le phare en pleine tempête.",
    "language": "fr",
    "style": "narrative",
    "voice": "warm_female"
  },
  "ambience": {
    "enabled": true,
    "description": "vent côtier, grincements de bois",
    "language": "fr",
    "style": "ambient"
  }
}
```

## Sortie

- `outputs/audio/audio_manifest.json`
- `output.audio_artifacts`
- `output.audio_manifest_file`

Exemple `audio_artifacts`:

```json
[
  {
    "kind": "voiceover",
    "enabled": true,
    "language": "fr",
    "path": "outputs/audio/req_123_voiceover.txt",
    "description": "Lina entre dans le phare en pleine tempête.",
    "metadata": { "provider": "mock_audio_provider", "sample_rate": 24000 },
    "timestamps": [{ "shot_id": "shot_001", "start_sec": 0.0, "end_sec": 3.2 }],
    "provider_trace": { "provider": "mock_audio_provider", "status": "success" },
    "latency_ms": 6,
    "cost_estimate": 0.0,
    "model_name": "mock-audio-v1"
  }
]
```

## Erreurs usuelles

- `TypeError` si `scene_doc` n'est pas un dict.
- `AudioContractError` si:
  - `scene_doc.output` absent/invalide,
  - `audio_plan` absent/invalide,
  - `voiceover` ou `ambience` absents/non-objets.
- Erreurs provider normalisées (`ProviderError` et sous-classes).
