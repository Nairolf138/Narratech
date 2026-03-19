# 🎬 Narratech — Generative Narrative Engine

Prototype d’un système capable de générer automatiquement une mini-séquence vidéo narrative cohérente à partir d’un simple prompt utilisateur.

---

## 🎯 Vision

Créer le premier prototype fonctionnel d’un **studio narratif automatisé** :

> Un système capable de transformer une idée en contenu audiovisuel structuré, cohérent et monté.

Ce projet ne vise pas la perfection visuelle, mais la **cohérence narrative et systémique**.

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

## 📁 Structure du projet

```
/project-root
  /core
    story_engine.py
    consistency_engine.py
  /generation
    asset_generator.py
    shot_generator.py
  /assembly
    video_assembler.py
    audio_engine.py
  /data
    prompts/
    outputs/
    assets/
  /config
    settings.json
  main.py
  README.md
```

---

## 🚀 MVP

Critères de validation :

- [ ] Prompt → vidéo automatique
- [ ] Cohérence visuelle minimale
- [ ] Structure narrative identifiable
- [ ] Personnages reconnaissables

---

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
