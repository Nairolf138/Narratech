# Provider Contracts — Narratech V1

Ce document définit le **contrat d’interface standard** pour tous les adapters providers du pipeline Narratech.  
Objectif: rendre les providers interchangeables (réel, mock, fallback) avec une couche d’orchestration stable.

---

## 1) Principes communs

- Chaque provider implémente une interface dédiée et **retourne un objet typé** (pas de `dict` libre).
- Les erreurs externes sont **normalisées** via une hiérarchie d’exceptions commune.
- Les appels doivent être instrumentés avec un bloc de métadonnées observabilité.
- Tous les providers supportent les mêmes règles de résilience: timeout, retry borné, circuit-breaker.

### 1.1 Métadonnées obligatoires (observabilité)

Chaque résultat provider inclut:

- `latency_ms` (`int`): latence totale mesurée côté adapter.
- `cost_estimate` (`float`): estimation de coût en devise interne (ex: USD).
- `model_name` (`str`): modèle réellement utilisé (utile en fallback).

Exemple de bloc standard:

```json
{
  "latency_ms": 843,
  "cost_estimate": 0.024,
  "model_name": "gpt-4.1-mini"
}
```

---

## 2) Erreurs normalisées

Tous les adapters lèvent uniquement ces erreurs (ou sous-classes internes mappées):

```python
class ProviderError(Exception):
    pass

class ProviderTimeout(ProviderError):
    """Le provider n’a pas répondu dans le délai alloué."""

class ProviderAuthError(ProviderError):
    """Authentification/autorisation invalide (clé absente, expirée, scope insuffisant)."""

class ProviderRateLimit(ProviderError):
    """Quota dépassé / throttling du provider."""

class ProviderInvalidResponse(ProviderError):
    """Réponse provider invalide: schéma incorrect, champ manquant, contenu incohérent."""
```

### Mapping attendu

- HTTP 401/403 → `ProviderAuthError`
- HTTP 408/504 / timeout socket → `ProviderTimeout`
- HTTP 429 → `ProviderRateLimit`
- JSON invalide / structure hors contrat → `ProviderInvalidResponse`

---

## 3) Résilience attendue (timeout/retry/circuit-breaker)

### 3.1 Timeout

- Timeout réseau par requête obligatoire.
- Valeurs par défaut recommandées:
  - Narrative: `20s`
  - Image/Asset: `45s`
  - Video/Shot: `90s`
  - Audio/TTS: `30s`
  - Render: `120s`

### 3.2 Retry

- Retry uniquement sur erreurs transitoires:
  - `ProviderTimeout`
  - `ProviderRateLimit`
- Stratégie: backoff exponentiel + jitter.
- Recommandation: `max_attempts=3` (1 initial + 2 retries).
- **Ne jamais retry** `ProviderAuthError` ni `ProviderInvalidResponse`.

### 3.3 Circuit-breaker

- Ouvrir le circuit après `5` échecs consécutifs.
- Fenêtre d’observation recommandée: `60s`.
- Cooldown avant semi-ouverture: `30s`.
- En état `open`: échouer vite avec erreur provider interne mappée en `ProviderTimeout` ou erreur d’orchestration explicite.

---

## 4) Interfaces providers

## 4.1 NarrativeProvider

Génère le plan narratif structuré à partir d’un prompt.

### Méthode obligatoire

```python
class NarrativeProvider(Protocol):
    def generate_narrative(
        self,
        *,
        prompt: str,
        duration_sec: int,
        style: str,
        language: str,
        request_id: str,
    ) -> "NarrativeResult":
        ...
```

### Paramètres

- `prompt`: intention utilisateur brute.
- `duration_sec`: durée cible (V1: 30–60).
- `style`: style narratif/visuel.
- `language`: langue de sortie.
- `request_id`: identifiant traçable.

### Retour

```python
@dataclass
class NarrativeResult:
    narrative_json: dict
    provider_trace: dict
    latency_ms: int
    cost_estimate: float
    model_name: str
```

- `narrative_json` doit valider `schemas/narrative.v1.schema.json`.

### Erreurs

`ProviderTimeout`, `ProviderAuthError`, `ProviderRateLimit`, `ProviderInvalidResponse`.

---

## 4.2 AssetProvider (image/assets persistants)

Produit les assets de personnages/environnements réutilisables.

### Méthode obligatoire

```python
class AssetProvider(Protocol):
    def generate_assets(
        self,
        *,
        narrative_json: dict,
        request_id: str,
    ) -> "AssetResult":
        ...
```

### Paramètres

- `narrative_json`: structure narrative validée.
- `request_id`: corrélation logs/outputs.

### Retour

```python
@dataclass
class AssetResult:
    asset_refs: list[dict]
    provider_trace: dict
    latency_ms: int
    cost_estimate: float
    model_name: str
```

- `asset_refs`: liste des ressources générées (uri/path/type/seed éventuel).

### Erreurs

`ProviderTimeout`, `ProviderAuthError`, `ProviderRateLimit`, `ProviderInvalidResponse`.

---

## 4.3 ShotProvider (génération plans vidéo)

Génère les clips vidéo correspondant aux plans narratifs.

### Méthode obligatoire

```python
class ShotProvider(Protocol):
    def generate_shots(
        self,
        *,
        narrative_json: dict,
        asset_refs: list[dict],
        request_id: str,
    ) -> "ShotResult":
        ...
```

### Paramètres

- `narrative_json`: scènes/plans validés.
- `asset_refs`: références assets persistants.
- `request_id`: identifiant de corrélation.

### Retour

```python
@dataclass
class ShotResult:
    clips: list[dict]
    provider_trace: dict
    latency_ms: int
    cost_estimate: float
    model_name: str
```

- `clips`: chemins/URLs des clips et métadonnées (durée, shot_id, fps).

### Erreurs

`ProviderTimeout`, `ProviderAuthError`, `ProviderRateLimit`, `ProviderInvalidResponse`.

---

## 4.4 AudioProvider

Génère la narration voix off et/ou ambiance.

### Méthode obligatoire

```python
class AudioProvider(Protocol):
    def synthesize_audio(
        self,
        *,
        audio_plan: dict,
        request_id: str,
    ) -> "AudioResult":
        ...
```

### Paramètres

- `audio_plan`: plan audio issu du narrative JSON.
- `request_id`: identifiant de traçabilité.

### Retour

```python
@dataclass
class AudioResult:
    tracks: list[dict]
    provider_trace: dict
    latency_ms: int
    cost_estimate: float
    model_name: str
```

- `tracks`: pistes audio produites (voiceover, ambience, timing).

### Erreurs

`ProviderTimeout`, `ProviderAuthError`, `ProviderRateLimit`, `ProviderInvalidResponse`.

---

## 4.5 RenderProvider

Assemble clips + audio en vidéo finale.

### Méthode obligatoire

```python
class RenderProvider(Protocol):
    def render(
        self,
        *,
        clips: list[dict],
        tracks: list[dict],
        render_plan: dict,
        request_id: str,
    ) -> "RenderResult":
        ...
```

### Paramètres

- `clips`: sorties du ShotProvider.
- `tracks`: sorties AudioProvider.
- `render_plan`: paramètres de montage/export.
- `request_id`: identifiant trace.

### Retour

```python
@dataclass
class RenderResult:
    output_path: str
    provider_trace: dict
    latency_ms: int
    cost_estimate: float
    model_name: str
```

### Erreurs

`ProviderTimeout`, `ProviderAuthError`, `ProviderRateLimit`, `ProviderInvalidResponse`.

---

## 5) Exemple d’implémentation “mock” (sans API réelle)

But: valider le pattern d’orchestration + gestion d’erreurs/observabilité localement.

```python
from dataclasses import dataclass
from time import perf_counter
from typing import Protocol

# ---- erreurs normalisées ----
class ProviderError(Exception):
    pass

class ProviderTimeout(ProviderError):
    pass

class ProviderAuthError(ProviderError):
    pass

class ProviderRateLimit(ProviderError):
    pass

class ProviderInvalidResponse(ProviderError):
    pass


# ---- contrat résultat ----
@dataclass
class NarrativeResult:
    narrative_json: dict
    provider_trace: dict
    latency_ms: int
    cost_estimate: float
    model_name: str


class NarrativeProvider(Protocol):
    def generate_narrative(
        self,
        *,
        prompt: str,
        duration_sec: int,
        style: str,
        language: str,
        request_id: str,
    ) -> NarrativeResult:
        ...


class MockNarrativeProvider:
    """Adapter mock déterministe, utile pour tests d’intégration."""

    def __init__(self, *, simulate: str = "ok") -> None:
        self.simulate = simulate  # ok|timeout|auth|rate_limit|invalid

    def generate_narrative(
        self,
        *,
        prompt: str,
        duration_sec: int,
        style: str,
        language: str,
        request_id: str,
    ) -> NarrativeResult:
        t0 = perf_counter()

        if self.simulate == "timeout":
            raise ProviderTimeout("mock timeout")
        if self.simulate == "auth":
            raise ProviderAuthError("mock auth error")
        if self.simulate == "rate_limit":
            raise ProviderRateLimit("mock rate limit")
        if self.simulate == "invalid":
            raise ProviderInvalidResponse("mock invalid response")

        narrative_json = {
            "request_id": request_id,
            "schema_version": "narrative.v1",
            "input": {
                "prompt": prompt,
                "duration_sec": duration_sec,
                "style": style,
                "language": language,
            },
            "synopsis": "Deux survivants se méfient dans un bunker post-apocalyptique.",
            "characters": [
                {"id": "c1", "name": "Nora"},
                {"id": "c2", "name": "Ilyas"}
            ],
            "scenes": []
        }

        latency_ms = int((perf_counter() - t0) * 1000)
        return NarrativeResult(
            narrative_json=narrative_json,
            provider_trace={"provider": "mock", "request_id": request_id},
            latency_ms=latency_ms,
            cost_estimate=0.0,
            model_name="mock-narrative-v1",
        )
```

### Exemple d’usage orchestration

```python
def run_story(provider: NarrativeProvider, req: dict) -> dict:
    try:
        res = provider.generate_narrative(
            prompt=req["prompt"],
            duration_sec=req.get("duration_sec", 45),
            style=req.get("style", "cinematic"),
            language=req.get("language", "fr"),
            request_id=req["request_id"],
        )
        return {
            "ok": True,
            "data": res.narrative_json,
            "obs": {
                "latency_ms": res.latency_ms,
                "cost_estimate": res.cost_estimate,
                "model_name": res.model_name,
            },
        }
    except (ProviderTimeout, ProviderRateLimit):
        # retry/backoff côté orchestrateur
        raise
    except (ProviderAuthError, ProviderInvalidResponse):
        # fail-fast + alert
        raise
```

---

## 6) Checklist de conformité adapter

Un adapter est “contract-compliant” s’il:

- expose toutes les méthodes obligatoires de son interface;
- applique le mapping vers erreurs normalisées;
- renseigne systématiquement `latency_ms`, `cost_estimate`, `model_name`;
- respecte timeout/retry/circuit-breaker définis;
- passe les tests avec un mock provider (succès + 4 modes d’échec).
