# ✅ TODO — Narratech

## Milestones
1. **Foundation**
2. **Pipeline V1**
3. **Quality Gate**
4. **Demo**

## Backlog tickets atomiques

| ID | Milestone | Ticket | DoD (Definition of Done) | Dépendances | Estimation | Priorité |
|---|---|---|---|---|---|---|
| T-001 | Foundation | Définir le schéma JSON narratif v1 | Schéma versionné dans `schemas/narrative.schema.json`, validé avec 3 exemples (valide/invalide), documentation courte des champs obligatoires. | — | M | P0 |
| T-002 | Foundation | Mettre en place le validateur de schéma en CLI | Commande `narratech validate <file>` disponible, code de sortie fiable (0/1), intégrée au README. | T-001 | S | P0 |
| T-003 | Foundation | Créer 10 fixtures d'histoires minimales | 10 fichiers JSON couvrant cas nominal + edge cases, tous passés via le validateur. | T-001, T-002 | S | P1 |
| T-004 | Pipeline V1 | Implémenter Story Engine (mock) | Entrée JSON → sortie plan de scènes déterministe, tests unitaires > 80% sur le module. | T-001, T-003 | M | P0 |
| T-005 | Pipeline V1 | Implémenter Consistency Engine v1 | Détecte incohérences de noms/temps/lieux, retourne rapport structuré avec niveau de sévérité. | T-004 | M | P0 |
| T-006 | Pipeline V1 | Implémenter Asset Generator (mock) | Génère liste d’assets attendus (personnages/décors/props) depuis les scènes, format JSON stable. | T-004 | M | P1 |
| T-007 | Pipeline V1 | Implémenter Shot Generator v1 | Produit shot list avec ordre, durée cible, type de plan, export JSON/CSV. | T-004, T-006 | M | P0 |
| T-008 | Pipeline V1 | Implémenter Video Assembler (stub exécutable) | Pipeline exécutable de bout en bout avec assets mock, sortie vidéo placeholder + logs d’assemblage. | T-006, T-007 | L | P1 |
| T-009 | Quality Gate | Ajouter tests d’intégration E2E pipeline | Un scénario complet passe automatiquement en CI, rapport de durée par étape disponible. | T-005, T-008 | M | P0 |
| T-010 | Quality Gate | Définir Quality Gate (checks bloquants) | Règles bloquantes documentées (schéma, cohérence, shot list), job CI rouge si violation. | T-009 | S | P0 |
| T-011 | Demo | Préparer script de démo "happy path" | Script reproductible en une commande, dataset de démonstration figé, runbook 1 page. | T-010 | S | P1 |
| T-012 | Demo | Générer vidéo de démonstration v1 | Vidéo exportée + artefacts intermédiaires archivés, validée manuellement par l’équipe. | T-011 | M | P1 |

## Next 2 weeks (5 premières tâches à exécuter)
1. **T-001 (P0, M)** — Définir le schéma JSON narratif v1.
2. **T-002 (P0, S)** — Mettre en place le validateur de schéma en CLI.
3. **T-004 (P0, M)** — Implémenter Story Engine (mock).
4. **T-005 (P0, M)** — Implémenter Consistency Engine v1.
5. **T-007 (P0, M)** — Implémenter Shot Generator v1.

> Règle d’ordonnancement: exécuter les tâches P0 dépendantes dès que leurs prérequis sont validés; décaler P1 après stabilisation du pipeline de base.
