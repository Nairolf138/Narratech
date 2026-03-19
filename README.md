# 🎬 Cineforge — Generative Narrative Engine

Prototype d’un système capable de générer automatiquement une mini-séquence vidéo narrative cohérente à partir d’un simple prompt utilisateur.

---

## 🎯 Vision

Créer le premier prototype fonctionnel d’un **studio narratif automatisé** :

> Un système capable de transformer une idée en contenu audiovisuel structuré, cohérent et monté.

Ce projet ne vise pas la perfection visuelle, mais la **cohérence narrative et systémique**.

---

## 🧠 Concept

Cineforge est un **orchestrateur**, pas un modèle d’IA.

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
