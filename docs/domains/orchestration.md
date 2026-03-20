# Domaine `orchestration`

Ce domaine pilote les transitions d'état, la résilience, et la production des artefacts finaux.

## Entrée

Point d'entrée: `_run_pipeline` (`src/main.py`).

Entrées runtime:
- prompt utilisateur,
- profil utilisateur (`--user-profile` pour `narratech generate`),
- providers chargés via `load_provider_bundle`.

## Sortie

Artefacts principaux:
- `outputs/scene.json`
- `outputs/scene_enriched.json`
- `outputs/consistency_report.json`
- `outputs/shots/shots_manifest.json`
- `outputs/audio/audio_manifest.json`
- `outputs/final/final_video_manifest.txt`
- `outputs/manifest.json`
- `outputs/pipeline_state.json`

États pipeline (`PipelineStage`):
`init -> prompt_loaded -> story_generated -> narrative_validated -> consistency_enriched -> assets_generated -> shots_generated -> final_assembled -> completed` (+ `done_with_warnings` / `failed`).

## Erreurs usuelles

- `SafetyBlockError` en pré/post génération.
- `NarrativeValidationError` sur schéma narratif.
- `ProviderError` sur providers non récupérables.
- `RuntimeError` sur artefacts requis manquants ou checks de conformité en échec.

## Exemple de payload de manifeste final

```json
{
  "request_id": "req_123",
  "status": "completed",
  "final_video_manifest_file": "outputs/final/final_video_manifest.txt",
  "pipeline_state_file": "outputs/pipeline_state.json",
  "provider_benchmark_run_file": "outputs/benchmarks/provider_benchmark_run.json",
  "provider_benchmark_global_file": "outputs/benchmarks/provider_benchmark_global.json"
}
```
