# Pipeline de bout en bout (simple)

```mermaid
flowchart TD
    A[Prompt + User Profile] --> B[Safety pre-check]
    B --> C[Narrative Provider]
    C --> D[Schema Validation]
    D --> E[Consistency Enrichment]
    E --> F[Asset Provider]
    F --> G[Shot Provider\n(retry + fallback + placeholder)]
    G --> H[Audio Provider]
    H --> I[Video Assembler]
    I --> J[Safety post-check + Compliance checks]
    J --> K[Manifest + Benchmarks + Pipeline state]
```

## Artefacts clés par étape

- `C`: `outputs/scene.json`
- `E`: `outputs/scene_enriched.json`, `outputs/consistency_report.json`
- `F`: `assets/<request_id>/assets_manifest.json`
- `G`: `outputs/shots/shots_manifest.json`
- `H`: `outputs/audio/audio_manifest.json`
- `I`: `outputs/final/final_video_manifest.txt`
- `K`: `outputs/manifest.json`, `outputs/pipeline_state.json`, `outputs/benchmarks/*.json`
