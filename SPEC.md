# 📘 SPEC — Narratech V1

## 🎯 Objectif V1
Transformer un prompt utilisateur en une micro-scène cohérente via un pipeline automatisé.

---

## 🔹 Input
```json
{
  "prompt": "post-apocalyptic bunker, two survivors, tension"
}
```

---

## 🔹 Output
- JSON narratif structuré
- Clips vidéo (ou placeholders)
- Vidéo finale assemblée

---

## 🧩 Pipeline
1. Story Engine
2. Consistency Engine
3. Asset Generator
4. Shot Generator
5. Video Assembler

---

## 🔌 Providers (V1)

### Narrative Provider
- OpenAI (LLM)

### Video Provider
- Primary: Sora
- Alternatives: Runway, Veo

### Image / Asset Provider
- Stable Diffusion or equivalent
- Can fallback to video provider

### Audio Provider
- TTS provider (ex: ElevenLabs)
- Replaceable

### Rendering
- ffmpeg (local)

---

## ⚠️ Contraintes
- 1 scène
- 1–2 personnages
- 30–60 secondes
- Cohérence > qualité visuelle
