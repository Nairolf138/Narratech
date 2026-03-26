# 🗺️ Roadmap publique Narratech

Cette roadmap est **priorisée** pour donner de la visibilité produit/technique.

## MVP — Stabiliser la démo verticale (priorité haute)

Objectif: rendre la démo fiable, rapide et mesurable.

1. **Fiabilisation pipeline happy path**
   - Réduire les erreurs intermittentes providers mock/picsum.
   - Standardiser les artefacts `outputs/*` attendus.
2. **Observabilité minimale exploitable**
   - Logs structurés sur chaque étape (entrée/sortie + latence).
   - Rapport de cohérence systématique.
3. **Qualité de base CI**
   - Exécution des tests essentiels sur chaque PR.
   - Garde-fous sur schémas et contrats providers.
4. **Sécurité opérationnelle minimale**
   - Vérification anti-secrets dans le flux de contribution.
   - Clarification des données autorisées dans logs/outputs.

## V1 — Industrialiser le socle (priorité moyenne)

Objectif: passer d’un prototype démo à un socle extensible.

1. **Abstraction providers renforcée**
   - Contrats plus stricts (narrative/assets/shots/audio).
   - Gestion explicite des timeouts/retries/fallbacks.
2. **Personnalisation narrative**
   - Meilleure exploitation de `user_context` et feedback.
   - Règles de recommandation versionnées.
3. **Orchestration robuste**
   - États pipeline explicites et reprise sur erreur.
   - Traçabilité bout-en-bout d’une génération.
4. **Documentation développeur complète**
   - Guides d’ajout de provider + runbooks de debug.
   - Exemples de scénarios de tests par domaine.

## V2 — Échelle produit (priorité stratégique)

Objectif: préparer une version orientée usage réel multi-verticales.

1. **Multi-verticales narratives**
   - Support de plusieurs styles/domaines (éducation, marketing, etc.).
2. **Qualité média améliorée**
   - Montage enrichi (transitions, audio mix, variations de rythme).
3. **Boucle d’amélioration continue**
   - Exploitation systématique du feedback utilisateur.
   - Benchmarks qualité/coût/latence comparables par provider.
4. **Conformité et gouvernance**
   - Contrôles renforcés sécurité, conformité légale, auditabilité.

---

## Principes de priorisation

- **Impact utilisateur** > complexité technique.
- **Réduction du risque produit** avant ajout massif de features.
- **Mesurabilité** obligatoire (temps, cohérence, taux de succès).
