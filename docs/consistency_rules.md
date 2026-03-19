# Consistency Rules — Narratech V1

Ce document définit des **règles de cohérence testables** pour la génération image/vidéo, ainsi qu’un format standard de **consistency packet** à injecter dans chaque prompt.

---

## 1) Persistance des personnages

Objectif: garantir qu’un même personnage reste identifiable d’un plan à l’autre.

### 1.1 Champs obligatoires (par personnage)

- `character_id` (string stable)
- `display_name` (nom affiché)
- `core_traits` (3 à 6 traits comportementaux/physiques stables)
- `signature_clothing` (pièces vestimentaires distinctives)
- `color_palette` (3 à 6 couleurs dominantes, format hex)

### 1.2 Règles testables

1. **Nom constant**
   - Règle: `display_name` ne change pas entre scènes, sauf alias explicitement déclaré.
   - Test: comparer le `display_name` courant avec le packet de référence.
   - Critère de succès: égalité stricte ou présence dans `allowed_aliases`.

2. **Traits stables**
   - Règle: au moins 70% des `core_traits` de référence sont présents dans la scène courante.
   - Test: intersection normalisée des traits.
   - Critère de succès: `overlap_ratio >= 0.70`.

3. **Vêtements signature**
   - Règle: au moins 2 éléments de `signature_clothing` restent visibles (ou mentionnés comme hors-champ avec justification narrative).
   - Test: comptage des éléments détectés ou explicitement justifiés.
   - Critère de succès: `visible_or_justified_count >= 2`.

4. **Palette couleur cohérente**
   - Règle: la palette personnage conserve son identité visuelle.
   - Test: distance de couleur moyenne (Delta E ou distance RGB normalisée) entre palette de référence et palette détectée.
   - Critère de succès: `avg_color_distance <= threshold` (seuil recommandé: 15 en Delta E).

---

## 2) Continuité visuelle

Objectif: maintenir la cohérence de la direction artistique entre plans.

### 2.1 Champs obligatoires

- `lighting_profile` (ex: golden hour soft, neon high contrast)
- `period_style` (époque/référentiel historique)
- `mood_tone` (ambiance émotionnelle dominante)
- `camera_style` (ex: handheld, locked-off, cinematic dolly)

### 2.2 Règles testables

1. **Lumière cohérente**
   - Règle: température de couleur, direction principale et niveau de contraste restent compatibles.
   - Test: score de similarité lumière entre scène N et N+1.
   - Critère de succès: `lighting_similarity >= 0.80`.

2. **Époque respectée**
   - Règle: pas d’objets, vêtements ou architecture anachroniques hors intention explicite.
   - Test: détection d’éléments interdits via liste `period_banned_items`.
   - Critère de succès: `anachronism_count == 0`.

3. **Ambiance stable**
   - Règle: `mood_tone` ne bascule pas brutalement sans transition narrative.
   - Test: classification d’ambiance + validation d’une `transition_reason` si changement fort.
   - Critère de succès: variation <= seuil, ou justification présente.

---

## 3) Continuité narrative

Objectif: conserver une progression dramatique claire et ordonnée.

### 3.1 Champs obligatoires

- `scene_goal` (objectif dramatique de la scène)
- `tension_level` (échelle 0–10)
- `action_sequence` (liste ordonnée des beats)

### 3.2 Règles testables

1. **Objectif de scène explicite**
   - Règle: chaque scène déclare un objectif aligné avec l’arc en cours.
   - Test: champ non vide + validation contre `arc_goal`.
   - Critère de succès: `scene_goal_valid == true`.

2. **Tension maîtrisée**
   - Règle: la tension évolue de façon progressive, sauf rupture voulue.
   - Test: `abs(tension[n+1] - tension[n]) <= 3` ou présence de `twist_flag=true`.
   - Critère de succès: variation dans seuil ou twist documenté.

3. **Ordre des actions respecté**
   - Règle: les actions clés suivent `action_sequence` sans inversion causale.
   - Test: vérification de précédence (A avant B).
   - Critère de succès: aucune violation des dépendances.

---

## 4) Format du “consistency packet” (à injecter dans chaque prompt)

Le packet doit être injecté en texte structuré (JSON/YAML) dans **tous** les prompts image/vidéo.

### 4.1 Schéma minimal (JSON)

```json
{
  "consistency_packet_version": "1.0",
  "project_id": "string",
  "sequence_id": "string",
  "scene_id": "string",
  "characters": [
    {
      "character_id": "char_001",
      "display_name": "Mila",
      "allowed_aliases": ["Agent Mila"],
      "core_traits": ["déterminée", "calme", "analytique"],
      "signature_clothing": ["manteau beige", "écharpe rouge"],
      "color_palette": ["#D9C2A7", "#A63D40", "#2F3E46"]
    }
  ],
  "visual_continuity": {
    "lighting_profile": "golden hour soft",
    "period_style": "Europe urbaine contemporaine (années 2020)",
    "mood_tone": "tension contenue",
    "camera_style": "cinematic handheld",
    "period_banned_items": ["smartphone 1990", "voiture futuriste"]
  },
  "narrative_continuity": {
    "arc_goal": "identifier la source du signal",
    "scene_goal": "infiltrer la gare sans alerter",
    "tension_level": 6,
    "action_sequence": [
      "repérage entrée nord",
      "diversion quai 2",
      "passage contrôle",
      "accès salle technique"
    ],
    "twist_flag": false,
    "transition_reason": ""
  },
  "quality_gates": {
    "traits_min_overlap": 0.7,
    "lighting_min_similarity": 0.8,
    "max_tension_jump": 3,
    "max_anachronism_count": 0
  }
}
```

### 4.2 Règle d’injection prompt

- Préfixer chaque prompt avec:
  1) le `consistency_packet` courant,
  2) les contraintes `quality_gates`,
  3) une consigne explicite: «respect strict de la continuité inter-scènes».  
- En retry, conserver le même packet et n’ajuster que les champs de correction (`retry_focus`, `violation_targets`).

---

## 5) Violation examples (pour guider les retries)

Utiliser ces exemples pour produire des retries ciblés et non destructifs.

### 5.1 Personnage — nom/identité

- **Violation**: “Mila” devient “Lina” sans justification.
- **Retry focus**: `display_name_lock`.
- **Instruction retry**: “Conserver strictement le nom ‘Mila’ et ignorer toute variante non listée.”

### 5.2 Personnage — vêtements

- **Violation**: disparition de l’écharpe rouge signature.
- **Retry focus**: `signature_clothing_visibility`.
- **Instruction retry**: “Rendre visibles au moins 2 éléments vestimentaires signature, dont l’écharpe rouge.”

### 5.3 Visuel — lumière

- **Violation**: passage brutal d’une lumière ‘golden hour soft’ à un éclairage néon dur.
- **Retry focus**: `lighting_profile_match`.
- **Instruction retry**: “Aligner température/couleur/contraste sur ‘golden hour soft’ (sans néon).”

### 5.4 Visuel — époque

- **Violation**: présence d’un objet anachronique (hologramme futuriste) dans un contexte contemporain réaliste.
- **Retry focus**: `period_anachronism_removal`.
- **Instruction retry**: “Supprimer tout objet anachronique listé dans `period_banned_items`.”

### 5.5 Narratif — ordre des actions

- **Violation**: “accès salle technique” avant “passage contrôle”.
- **Retry focus**: `action_precedence`.
- **Instruction retry**: “Respecter l’ordre causal de `action_sequence` sans inversion.”

### 5.6 Narratif — tension

- **Violation**: tension 3 → 9 sans twist.
- **Retry focus**: `tension_curve_smoothing`.
- **Instruction retry**: “Limiter la variation de tension au seuil autorisé ou déclarer un twist explicite.”

---

## 6) Checklist rapide d’acceptation

- [ ] `consistency_packet` présent dans le prompt.
- [ ] Tous les champs obligatoires renseignés.
- [ ] `quality_gates` explicitement appliqués.
- [ ] Aucune violation bloquante (nom, anachronisme, ordre causal).
- [ ] En cas de retry: correction ciblée sans réécriture totale de la scène.
