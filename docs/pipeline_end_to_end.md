# Pipeline de bout en bout (simple)

```mermaid
flowchart TD
    A[Prompt + User Profile] --> B[Safety pre-check]
    B --> C[Narrative Provider]
    C --> D[Schema Validation]
    D --> E[Consistency Enrichment]
    E --> F[Feedback preprocessing\n(post_watch_feedback.jsonl -> user_context)]
    F --> G[Recommendation Engine\n(policy_version + applied_signals)]
    G --> H[Asset Provider]
    H --> I[Shot Provider\n(retry + fallback + placeholder)]
    I --> J[Audio Provider]
    J --> K[Video Assembler]
    K --> L[Safety post-check + Compliance checks]
    L --> M[Manifest + Benchmarks + Pipeline state]
```

## Artefacts clés par étape

- `C`: `outputs/scene.json`
- `E`: `outputs/scene_enriched.json`, `outputs/consistency_report.json`
- `F`: `outputs/ui_exchange/post_watch_feedback.jsonl` (source) + `user_context` injecté dans `outputs/recommendation.json`
- `G`: `outputs/recommendation.json` + enrichissement `scene_enriched.metadata.recommendation`
- `H`: `assets/<request_id>/assets_manifest.json`
- `I`: `outputs/shots/shots_manifest.json`
- `J`: `outputs/audio/audio_manifest.json`
- `K`: `outputs/final/final_video_manifest.txt`
- `M`: `outputs/manifest.json`, `outputs/pipeline_state.json`, `outputs/benchmarks/*.json`

## Boucle feedback → user_context → génération

1. Les feedbacks UI post-watch sont stockés en JSONL dans `outputs/ui_exchange/post_watch_feedback.jsonl`.
2. `FeedbackEngine.build_user_context_from_ui_feedback` normalise ces événements (clamp des notes, moyennes dimensions, extraction de signaux).
3. `RecommendationEngine` consomme `user_context.preference_signals` + métriques de cohérence pour produire des recommandations stables.
4. La version de policy (`recommendation_policy_version`) et les signaux appliqués (`applied_signals`) sont propagés:
   - dans `outputs/recommendation.json`,
   - dans `scene_enriched.metadata.recommendation`,
   - et dans `scene_enriched.provider_trace` comme trace de décision.
5. Au run suivant, la même entrée feedback normalisée mène à la même recommandation (tests de non-régression).
