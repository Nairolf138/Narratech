# Observability providers

## Schéma unifié `provider_trace`

Tous les providers (Narrative, Asset, Shot, Audio) publient désormais un objet `provider_trace` avec les champs obligatoires suivants :

- `provider` (`string`) : nom technique du provider.
- `model` (`string`) : identifiant du modèle/runtime utilisé.
- `modele` (`string`) : alias FR de `model` pour uniformisation documentaire.
- `latency_ms` (`int`) : latence mesurée côté adapter/provider.
- `cost_estimate` (`float`) : estimation du coût de l'appel.
- `retries` (`int`) : nombre de retries réalisés avant succès.
- `status` (`string`) : statut final (`success`, `degraded`, `failed`, etc.).
- `error` (`string`) : message d'erreur final (chaîne vide si succès).

Des champs additionnels sont autorisés (`trace_id`, `stage`, `usage`, `personalization_applied`, etc.) mais les champs ci-dessus sont la base contractuelle benchmark.

## Exemples

```json
{
  "provider": "mock_shot_provider",
  "model": "mock-shot-v1",
  "modele": "mock-shot-v1",
  "latency_ms": 8,
  "cost_estimate": 0.0015,
  "retries": 1,
  "status": "success",
  "error": "",
  "stage": "shot_generation",
  "trace_id": "trace_123abc"
}
```

## Agrégation benchmark

### 1) Benchmark par run

- Fichier: `outputs/benchmarks/provider_benchmark_run.json`
- Source: traces collectées dans les artefacts narratif/assets/shots/audio.
- Métriques agrégées:
  - `calls`
  - `latency_ms_total`
  - `latency_ms_avg`
  - `cost_estimate_total`
  - `retries_total`
  - `error_count`
  - `status_counts`
  - `models`

### 2) Benchmark global (historique runs)

- Fichier: `outputs/benchmarks/provider_benchmark_global.json`
- Comportement: append des résultats de chaque run dans `runs`, puis recalcul des totaux globaux.
- Totaux globaux:
  - `runs`
  - `calls`
  - `latency_ms_total`
  - `latency_ms_avg_per_call`
  - `cost_estimate_total`
  - `retries_total`
  - `error_count`

## Intégration manifeste pipeline

Le `outputs/manifest.json` référence:

- `provider_benchmark_run_file`
- `provider_benchmark_global_file`
- `provider_benchmark_totals`
- `provider_benchmark_global_totals`
