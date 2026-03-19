# 🧠 DECISIONS — Narratech

## 🔧 Provider Abstraction Policy

1. Aucun provider ne doit être utilisé directement dans la logique métier
2. Tous les providers doivent passer par un adapter
3. Les modules utilisent des interfaces abstraites :
   - NarrativeProvider
   - VideoProvider
   - ImageProvider
   - AudioProvider

---

## 🔁 Remplacement des providers

- Changer de provider ne doit PAS casser :
  - le schéma narratif
  - le pipeline
  - les modules internes

---

## ⚙️ Architecture

Narratech est :
- un orchestrateur
- un système modulaire
- indépendant des APIs externes

---

## 🚫 Interdictions

- Pas de logique spécifique à Sora / Runway dans le core
- Pas de dépendance forte à un provider

---

## 🎯 Priorité

Cohérence système > performance brute
