# Domaine `metrics`

Ce domaine couvre les métriques de cohérence, qualité dégradée et benchmark providers.

## Entrée

Sources principales:
- traces `provider_trace` de chaque domaine,
- état runtime `PipelineRuntimeState` (retries, erreurs, ratio dégradé),
- rapport de cohérence (`consistency_report`).

Composants:
- `aggregate_provider_benchmark` / `update_global_provider_benchmark` (`src/core/provider_benchmark.py`),
- `PipelineRuntimeState` (`src/core/pipeline_state.py`),
- checks légaux pré-publication (`_run_pre_publication_checks` dans `src/main.py`).

## Sortie

- `outputs/benchmarks/provider_benchmark_run.json`
- `outputs/benchmarks/provider_benchmark_global.json`
- `outputs/pipeline_state.json`
- `outputs/legal_compliance_checks.json`

Exemple de benchmark par run:

```json
{
  "request_id": "req_123",
  "totals": {
    "calls": 4,
    "latency_ms_total": 2134,
    "cost_estimate_total": 0.042,
    "retries_total": 1,
    "error_count": 0
  },
  "providers": [
    {
      "provider": "mock_narrative_provider",
      "calls": 1,
      "latency_ms_total": 9,
      "latency_ms_avg": 9.0,
      "cost_estimate_total": 0.0,
      "retries_total": 0,
      "error_count": 0,
      "status_counts": { "success": 1 },
      "models": ["mock-narrative-v1"]
    }
  ]
}
```

## Erreurs usuelles

- Traces malformed: ignorées silencieusement (métriques partielles).
- Fichier global benchmark JSON corrompu: reset implicite au prochain run.
- Ratio dégradé > seuil: terminaison en `failed` ou `done_with_warnings` selon policy runtime.
