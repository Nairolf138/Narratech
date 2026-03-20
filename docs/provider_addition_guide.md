# Guide pas à pas — ajouter un nouveau provider

Ce guide décrit le chemin minimal pour intégrer un provider (narrative, asset, shot ou audio) dans Narratech.

## 1) Choisir le domaine provider

- Narrative: implémente `generate_narrative`.
- Asset: implémente `generate_assets`.
- Shot: implémente `generate_shots`.
- Audio: implémente `synthesize_audio`.

Référence interfaces: `src/providers/contracts.py` + `src/providers/base.py`.

## 2) Créer la classe provider

Créer un fichier dans `src/providers/` (ou sous-package dédié) qui:

1. hérite de `BaseProvider`,
2. implémente `configure`, `generate`, `healthcheck`,
3. implémente aussi la méthode spécialisée du contrat ciblé (`generate_shots`, etc.),
4. retourne un `ProviderResponse` conforme (`data`, `provider_trace`, `latency_ms`, `cost_estimate`, `model_name`).

Exemple minimal (shape):

```python
class MyShotProvider(BaseProvider, ShotProviderContract):
    def configure(self, config: Mapping[str, Any]) -> None:
        ...

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        return self.generate_shots(request)

    def generate_shots(self, request: ProviderRequest) -> ProviderResponse:
        # produire data={"clips": [...]}
        return ProviderResponse(data={"clips": [...]}, provider_trace={...}, latency_ms=120, cost_estimate=0.01, model_name="my-model")

    def healthcheck(self) -> ProviderHealth:
        return ProviderHealth(ok=True, details={"provider": "my_shot"})
```

## 3) Normaliser les erreurs

Mapper toutes les erreurs externes vers:
- `ProviderTimeout`
- `ProviderAuthError`
- `ProviderRateLimit`
- `ProviderInvalidResponse`
- (sinon) `ProviderError`

L'orchestration utilise ces classes pour retry/fallback.

## 4) Enregistrer le provider dans la config

Ajouter le type dans `_PROVIDER_REGISTRY` (`src/config/providers.py`), par exemple:

```python
_PROVIDER_REGISTRY = {
    ...,
    "my_shot": MyShotProvider,
}
```

Si provider narratif piloté par factory dédiée, ajouter aussi l'entrée dans `src/providers/factory.py`.

## 5) Brancher la configuration runtime

Configurer la valeur provider dans le profil runtime (`config/providers.local.json` ou `config/providers.demo.json`, selon l'environnement) + variables d'environnement éventuelles (API key, endpoint).

## 6) Ajouter des tests

Minimum recommandé:

- test de configuration (`tests/test_provider_config.py`),
- test contrat provider (`tests/test_provider_contract_suites.py`),
- test orchestration fallback/retry si concerné (`tests/test_provider_orchestration.py`),
- test domaine spécifique (ex: `tests/test_audio_provider.py`, `tests/test_async_shot_provider.py`).

## 7) Vérifier en local

- exécuter tests ciblés,
- lancer un run pipeline (smoke/demo),
- valider les artefacts et traces `provider_trace`.

## 8) Définir stratégie de fallback

Dans `load_provider_bundle`, définir:
- provider primaire,
- provider fallback,
- `fallback_policy` (`enabled`, `trigger_on`, `activate_after_attempt`).

## 9) Valider observabilité

Vérifier que chaque appel renseigne correctement:
- `provider`, `model`, `latency_ms`, `cost_estimate`, `retries`, `status`, `error`.

Ces champs alimentent `outputs/benchmarks/provider_benchmark_run.json`.
