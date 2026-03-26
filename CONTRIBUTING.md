# Contribuer à Narratech

Merci pour votre contribution ✨

## 1) Pré-requis

- Python **3.11+**
- Installation locale:

```bash
pip install -e .
```

## 2) Workflow recommandé

1. Créer une branche depuis `main` (`feature/...`, `fix/...`, `docs/...`).
2. Implémenter un changement **petit et ciblé**.
3. Ajouter/adapter les tests associés.
4. Vérifier localement (voir section tests).
5. Ouvrir une PR en utilisant le template.

## 3) Conventions de code

### Structure

- Respecter les domaines existants (`src/core`, `src/providers`, `src/generation`, `src/assembly`).
- Éviter les dépendances croisées inutiles entre domaines.

### Style Python

- Suivre PEP 8 et privilégier la lisibilité.
- Ajouter des docstrings courtes sur les fonctions non triviales.
- Préférer des fonctions petites, explicites, testables.
- Ne pas introduire de `try/except` autour des imports.

### Configuration & schémas

- Toute évolution de schéma JSON doit être documentée dans `schemas/CHANGELOG.md`.
- Les changements de config provider doivent rester compatibles avec les profils existants (`config/providers.*.json`) ou être explicitement versionnés.

## 4) Conventions de tests

- Framework: `pytest`.
- Marqueurs stricts activés (`--strict-markers`).
- Ajouter des tests au plus proche du domaine impacté dans `tests/`.
- Pour un changement critique pipeline, prévoir:
  - 1 test unitaire ciblé,
  - et si pertinent 1 test d’intégration/e2e.

### Commandes utiles

```bash
pytest
pytest -m smoke
```

## 5) Qualité & sécurité

Avant PR:

- Vérifier qu’aucun secret/token/clé API n’est présent dans le diff.
- Éviter de logger des données sensibles.
- Documenter clairement les impacts (breaking changes, schémas, config).

## 6) Documentation

Toute évolution fonctionnelle doit s’accompagner de la documentation minimale:

- `README.md` si usage utilisateur impacté,
- `docs/` si impact architecture/domaine,
- `SPEC.md` ou `DECISIONS.md` si décision structurante.

## 7) Critères d’acceptation d’une PR

- Scope clair et justifié.
- Tests pertinents en place et passants.
- Documentation alignée.
- Checklist qualité/sécurité du template PR complétée.
