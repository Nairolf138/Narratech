# 🎬 Narratech — Generative Narrative Engine

Prototype d’un système capable de générer automatiquement une mini-séquence vidéo narrative cohérente à partir d’un simple prompt utilisateur.

---

## 🎯 Vision

Créer le premier prototype fonctionnel d’un **studio narratif automatisé** :

> Un système capable de transformer une idée en contenu audiovisuel structuré, cohérent et monté.

Ce projet ne vise pas la perfection visuelle, mais la **cohérence narrative et systémique**.

---


## 🧪 Verticale de démonstration (figée)

Une seule verticale est supportée pour la démo produit:

- **Narration mock** (`MockNarrativeProvider`)
- **Assets mock** (`MockAssetProvider`)
- **Shots semi-réels** via URLs d'images Picsum (`PicsumShotProvider`)

Cette verticale est pilotée par `config/providers.demo.json` avec `NARRATECH_ENV=demo`.

---

## ▶️ Runbook démo (court)

### Pré-requis

- Python 3.11+
- Dépendances installées (`pip install -e .`)

### Commande unique

```bash
python scripts/run_demo_happy_path.py "Votre prompt"
```

> Sans argument, le script utilise un prompt happy path figé.

### Artefacts attendus

- `outputs/manifest.json`
- `outputs/scene.json`
- `outputs/scene_enriched.json`
- `outputs/consistency_report.json`
- `outputs/shots/shots_manifest.json`
- `outputs/final/final_video_manifest.txt`

### Critères de succès de démo

- **Temps total** ≤ 30s
- **Nombre de shots** = 3
- **% placeholders max** ≤ 20%
- **Cohérence minimale**: score ≥ 0.80 (dérivé du `consistency_report`)

---


## 🖥️ Prototype UI minimal (web)

Un prototype UI local est disponible pour couvrir :

1. formulaire préférences + prompt,
2. lecteur vidéo du rendu final,
3. formulaire feedback post-visionnage,
4. échange standardisé via API locale + fichiers JSONL.

### Lancer l'UI

```bash
python scripts/ui_prototype_server.py
```

Puis ouvrir `http://127.0.0.1:8080`.

### Fichiers d'échange écrits

- `outputs/ui_exchange/generation_requests.jsonl`
- `outputs/ui_exchange/post_watch_feedback.jsonl`

Le lecteur vidéo tente de charger `outputs/final/final_video.mp4`.

---

## 🧠 Concept
Narratech est un **orchestrateur**, pas un modèle d’IA.

Il connecte plusieurs briques existantes :

- LLM (narration)
- Génération d’images (assets)
- Génération vidéo (plans)
- Synthèse vocale (voix)
- Montage automatisé

👉 Objectif : automatiser un pipeline de création audiovisuelle.

---

## 🧩 Architecture

```
[User Prompt]
      ↓
[Story Engine]
      ↓
[Consistency Engine]
      ↓
[Asset Generator]
      ↓
[Shot Generator]
      ↓
[Video Assembler]
      ↓
[Final Video]
```

---

## ⚙️ Modules

### 🧠 Story Engine

Génère une structure narrative exploitable :

- synopsis
- personnages
- découpage scènes → plans

---

### 🧠 Consistency Engine (CORE)

Maintient la cohérence globale :

- personnages persistants
- style visuel
- règles de lumière

👉 Injecte ces contraintes dans chaque génération.

---

### 🎨 Asset Generator

Crée les éléments persistants :

- personnages
- environnements

Stockés comme références pour toutes les scènes.

---

### 🎥 Shot Generator

Génère les plans vidéo :

- basé sur prompts enrichis
- clips courts (3–10s)

---

### ✂️ Video Assembler

Assemble les plans :

- ordre narratif
- transitions simples

---

### 🔊 Audio Engine

Ajoute :

- narration voix off
- ambiance sonore basique

---


## 📚 Documentation détaillée

- Vue pipeline end-to-end: `docs/pipeline_end_to_end.md`
- Guide d’intégration provider: `docs/provider_addition_guide.md`
- Domaines:
  - `docs/domains/narrative.md`
  - `docs/domains/assets.md`
  - `docs/domains/shots.md`
  - `docs/domains/audio.md`
  - `docs/domains/orchestration.md`
  - `docs/domains/safety.md`
  - `docs/domains/metrics.md`

## 📁 Structure du projet

Arborescence **réellement présente** (vérifiée le **2026-03-20**) :

```bash
find . \
  \( -path './.git' -o -path './.venv' -o -path './venv' -o -path './node_modules' \
     -o -path './__pycache__' -o -path './.pytest_cache' -o -path './.mypy_cache' \
     -o -path './dist' -o -path './build' -o -path './.next' -o -path './coverage' \) -prune \
  -o -print | sed 's#^\./##' | sort
```

### Structure racine (source de vérité)

```text
.
.github/
assets/
config/
docs/
outputs/
schemas/
scripts/
src/
tests/
DECISIONS.md
README.md
SPEC.md
TODO.md
example_prompt.txt
main.py
pyproject.toml
pytest.ini
```

### Détail des répertoires de référence (source de vérité)

- `src/providers/` : implémentations providers + contrat Python local (`contracts.py`).
- `schemas/` : contrats JSON Schema versionnés (source de vérité “contracts” côté schémas).
- `src/providers/contracts.py` : contrat provider côté code (il n’existe pas de dossier racine `contracts/` à ce jour).
- `tests/` : tests unitaires/intégration/e2e.
- `docs/` : documentation fonctionnelle et technique.

### Détail complet (fichiers versionnés présents)

```bash
rg --files | sort
```

```text
.
.github/
.github/workflows/
.github/workflows/ci.yml
DECISIONS.md
README.md
SPEC.md
TODO.md
assets/
assets/.gitkeep
config/
config/providers.demo.json
config/providers.local.json
docs/
docs/consistency_rules.md
docs/orchestration_flow.md
docs/provider_contracts.md
example_prompt.txt
main.py
outputs/
outputs/.gitkeep
outputs/final/
outputs/final/.gitkeep
outputs/scene.json
outputs/scene_enriched.json
outputs/shots/
outputs/shots/.gitkeep
pyproject.toml
pytest.ini
schemas/
schemas/CHANGELOG.md
schemas/narrative.enriched.v1.schema.json
schemas/narrative.v1.schema.json
scripts/
scripts/run_demo_happy_path.py
src/
src/__init__.py
src/assembly/
src/assembly/__init__.py
src/assembly/audio_engine.py
src/assembly/video_assembler.py
src/config/
src/config/__init__.py
src/config/providers.py
src/core/
src/core/__init__.py
src/core/consistency_engine.py
src/core/input_loader.py
src/core/io_utils.py
src/core/logger.py
src/core/pipeline_state.py
src/core/schema_validator.py
src/core/story_engine.py
src/generation
src/generation/__init__.py
src/generation/asset_generator.py
src/generation/shot_generator.py
src/main.py
src/providers
src/providers/__init__.py
src/providers/adapter.py
src/providers/base.py
src/providers/contracts.py
src/providers/mock_asset_provider.py
src/providers/mock_narrative_provider.py
src/providers/mock_shot_provider.py
src/providers/picsum_shot_provider.py
tests/
tests/ci/
tests/ci/check_coverage_thresholds.py
tests/conftest.py
tests/e2e/
tests/e2e/test_smoke_pipeline.py
tests/test_cli.py
tests/test_consistency_engine.py
tests/test_pipeline_blocking.py
tests/test_pipeline_state_integration.py
tests/test_provider_config.py
tests/test_provider_orchestration.py
tests/test_required_artifacts.py
tests/test_schema_validator.py
tests/test_smoke_pipeline_mock.py
```

_Convention “source de vérité” : en cas d’écart entre la documentation et le dépôt, la vérité est (dans cet ordre) : (1) structure racine ci-dessus, (2) contenus de `src/providers/`, `schemas/` (contrats), `tests/`, `docs/`, puis (3) le reste du README._

_Note de maintenance : régénérer cette section à chaque changement de structure (ajout/suppression/déplacement de fichiers ou dossiers), idéalement dans la même PR._

---

## 🚀 MVP

Critères de validation :

- [ ] Prompt → vidéo automatique
- [ ] Cohérence visuelle minimale
- [ ] Structure narrative identifiable
- [ ] Personnages reconnaissables

---

## ✅ Definition of Done (DoD)

Une tâche est considérée "Done" uniquement si les points suivants sont validés:

- Schéma narratif valide (`python main.py validate outputs/scene.json`).
- Tests unitaires core verts (au minimum `tests/test_schema_validator.py`, `tests/test_consistency_engine.py`, `tests/test_pipeline_blocking.py`).
- Smoke pipeline vert (`tests/test_smoke_pipeline_mock.py`).
- Invariants garantis par tests:
  - topologie scènes/shots inchangée après enrichissement,
  - tri narratif stable,
  - manifests obligatoires présents et cohérents.
- Seuils de couverture atteints pour les modules critiques:
  - `src/core` ≥ 85%,
  - `src/generation` ≥ 80%,
  - minimum global pytest-cov ≥ 82%.
- Artefacts obligatoires générés correctement dans les tests et en pipeline:
  - `outputs/manifest.json`,
  - `outputs/shots/shots_manifest.json`.
- CI bloquante: tout échec de ces checks met le job en rouge.


## ⚠️ Contraintes

- Latence élevée acceptée
- Résultats non déterministes
- Dépendance APIs externes

---

## 🧠 Risques

### Cohérence visuelle
Problème principal

### Variabilité IA
Nécessite sélection et retries

### Coût
Limiter durée et résolution

---

## 🛠️ Stack suggérée

- LLM : OpenAI / équivalent
- Image : Stable Diffusion
- Vidéo : Runway / Sora
- Audio : ElevenLabs
- Montage : ffmpeg

---

## 🗺️ Roadmap

### V1
- Pipeline complet
- 1 scène cohérente

### V2
- Multi-scènes
- meilleure cohérence

### V3
- génération dynamique utilisateur

---

## 🎭 Philosophie

Priorité à :

- cohérence
- structure narrative
- automatisation

Pas à :

- qualité visuelle parfaite
- réalisme total

---

## 📌 Ambition

Explorer la transition de :

> génération de contenu → génération de narration cohérente

---

## ⚡ Disclaimer

Prototype expérimental.

Objectif :
- tester
- comprendre
- démontrer

Pas :
- scaler
- industrialiser

---

## 🧠 Auteur

Nairolf138

Quelqu’un qui a décidé consciemment d'ajouter de la difficulte a sa vie pour construire un studio de cinéma avec du code.

---

## 📐 Schema Contract

Le contrat V1 est défini dans `schemas/narrative.v1.schema.json` et couvre :

- input minimal (`prompt`) + options (`duration_sec`, `style`, `language`)
- output structuré (`synopsis`, `characters[]`, `scenes[]`, `shots[]`, `asset_refs[]`, `audio_plan`, `render_plan`)
- contraintes V1 (`1 scène`, `1–2 personnages`, `30–60s`)
- traçabilité (`request_id`, `schema_version`, `provider_trace`)

### 🗂️ Mapping artefact ↔ schéma

- `outputs/scene.json` ➜ `schemas/narrative.v1.schema.json` (sortie StoryEngine non enrichie).
- `outputs/scene_enriched.json` ➜ `schemas/narrative.enriched.v1.schema.json` (sortie ConsistencyEngine enrichie avec `output.shots[*].consistency_constraints` et `output.shots[*].enriched_prompt`).

### ✅ Exemple valide

```json
{
  "request_id": "req_20260319_001",
  "schema_version": "narrative.v1",
  "input": {
    "prompt": "post-apocalyptic bunker, two survivors, tension",
    "duration_sec": 45,
    "style": "cinematic",
    "language": "fr"
  },
  "output": {
    "synopsis": "Deux survivants hésitent à ouvrir une porte blindée après un bruit extérieur.",
    "characters": [
      { "id": "c1", "name": "Mara", "role": "leader" },
      { "id": "c2", "name": "Ilan", "role": "technician" }
    ],
    "scenes": [
      { "id": "s1", "summary": "Confrontation silencieuse dans le bunker", "duration_sec": 45 }
    ],
    "shots": [
      { "id": "sh1", "scene_id": "s1", "description": "Gros plan sur la poignée qui tremble", "duration_sec": 6.5 },
      { "id": "sh2", "scene_id": "s1", "description": "Champ/contre-champ tendu entre les deux survivants", "duration_sec": 8.0 }
    ],
    "asset_refs": [
      { "id": "a_char_mara", "type": "character", "uri": "s3://assets/mara_v1.png" },
      { "id": "a_env_bunker", "type": "environment", "uri": "s3://assets/bunker_v3.png" }
    ],
    "audio_plan": {
      "voiceover": { "enabled": true, "language": "fr", "script": "N'ouvre pas. Pas encore." },
      "ambience": { "enabled": true, "description": "vent lointain, vibration métallique" }
    },
    "render_plan": {
      "resolution": "1920x1080",
      "fps": 24,
      "format": "mp4",
      "transitions": ["cut", "fade"]
    }
  },
  "provider_trace": [
    {
      "stage": "story_engine",
      "provider": "openai",
      "model": "gpt-4.1",
      "trace_id": "tr_story_001",
      "latency_ms": 1420
    },
    {
      "stage": "shot_generator",
      "provider": "sora",
      "model": "sora-v1",
      "trace_id": "tr_shot_002",
      "latency_ms": 29850
    }
  ]
}
```

### ❌ Exemple invalide

```json
{
  "request_id": "",
  "schema_version": "narrative.v2",
  "input": {
    "prompt": "",
    "duration_sec": 90
  },
  "output": {
    "synopsis": "",
    "characters": [
      { "id": "c1", "name": "A", "role": "r" },
      { "id": "c2", "name": "B", "role": "r" },
      { "id": "c3", "name": "C", "role": "r" }
    ],
    "scenes": [
      { "id": "s1", "summary": "...", "duration_sec": 40 },
      { "id": "s2", "summary": "...", "duration_sec": 40 }
    ],
    "shots": [],
    "asset_refs": [],
    "audio_plan": {},
    "render_plan": {}
  },
  "provider_trace": []
}
```

Pourquoi invalide : `request_id` et `prompt` vides, mauvaise version (`narrative.v2`), `duration_sec` hors limites, 3 personnages, 2 scènes, `shots` vide, `audio_plan`/`render_plan` incomplets, et `provider_trace` vide.


## 🧪 Exécution locale propre

### Prérequis
- Python 3.11+ (testé avec Python 3.12).
- Aucun service externe requis pour le run minimal.
- Dépendances Python déclarées par le projet : définies dans `pyproject.toml` (installation locale via `pip install -e .`).

### Commandes exactes — mode dev (sans installation)
```bash
# depuis la racine du dépôt
python3 -m venv .venv_clean
source .venv_clean/bin/activate
python -m pip install --upgrade pip

# exécution du pipeline par défaut
python main.py

# validation d'un document narratif
python main.py validate outputs/scene.json
```

Chemins vérifiés (fichiers présents dans le dépôt) : `main.py`, `outputs/scene.json`, `pyproject.toml`.

### Commandes exactes — mode installé (script console)
```bash
# depuis la racine du dépôt
python3 -m venv .venv_clean
source .venv_clean/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .

# exécution du pipeline par défaut
narratech

# validation d'un document narratif
narratech validate outputs/scene.json
```

Chemins vérifiés (fichiers présents dans le dépôt) : `main.py`, `outputs/scene.json`, `pyproject.toml`.

### Lancer le smoke test local
```bash
# depuis la racine du dépôt (dans le même venv)
python -m pytest -k smoke
```

Ce smoke test exécute un flux de bout en bout avec un pipeline mock local, sans appel réseau.
Fichier de test correspondant présent : `tests/test_smoke_pipeline_mock.py` (et version e2e : `tests/e2e/test_smoke_pipeline.py`).

### Configuration minimale
- Variables d'environnement : aucune requise.
- Fichiers requis : aucun fichier de configuration externe.
- Arguments : optionnels ; sans argument, le prompt par défaut interne est utilisé.

### Résultat attendu
- Code de sortie `0`.
- Logs de démarrage avec les étapes `[Narratech] ...`.
- Artefacts générés à l’exécution (non tous versionnés dans Git) :
  - `outputs/prompt.txt`
  - `outputs/scene.json`
  - `outputs/scene_enriched.json`
  - `outputs/shots/shots_manifest.json`
  - `outputs/final/final_video.txt`
  - `outputs/manifest.json`

---

## ✅ Validation du schéma narratif

Narratech valide désormais les documents narratifs contre `schemas/narrative.v1.schema.json`.
Le pipeline valide ensuite aussi `outputs/scene_enriched.json` contre `schemas/narrative.enriched.v1.schema.json` juste après enrichissement.

### Commande CLI

```bash
# mode dev
python main.py validate outputs/scene.json

# mode installé
narratech validate outputs/scene.json
```

### Exemples

- **Document valide**

```bash
$ python main.py validate outputs/scene.json
Document narratif valide: outputs/scene.json
```

- **Champ obligatoire manquant**

```bash
$ python main.py validate outputs/scene_missing.json
Document narratif invalide: $: champ obligatoire manquant 'request_id'.
```

- **Type invalide**

```bash
$ python main.py validate outputs/scene_invalid.json
Document narratif invalide: $.output.render_plan.fps: type attendu integer, valeur reçue str.
```

### Codes de retour

- `0` : validation réussie.
- `1` : validation échouée (fichier invalide, JSON malformé, fichier introuvable, ou non-conformité au schéma).

### Validation automatique dans le pipeline

Après `StoryEngine().generate(...)`, Narratech valide `scene.json` via `schemas/narrative.v1.schema.json`.
Après `enrich(...)`, Narratech valide `scene_enriched.json` via `schemas/narrative.enriched.v1.schema.json`.
Si la validation échoue, le pipeline s’arrête immédiatement avec un code de retour `1`.
