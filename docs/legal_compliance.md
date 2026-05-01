# Politique de conformité légale — Narratech

## Objectif

Ce document définit le socle minimal de conformité appliqué avant toute publication/export d’un contenu généré par Narratech.

## Périmètre

La politique couvre les artefacts produits par le pipeline:

- `outputs/scene.json`
- `outputs/scene_enriched.json`
- `outputs/shots/shots_manifest.json`
- `outputs/audio/audio_manifest.json`
- `outputs/final/final_video.mp4`
- `outputs/manifest.json`

## Principes de conformité

1. **Consentement explicite**: un consentement de génération et d’export doit être présent.
2. **Traçabilité de provenance**: l’origine du prompt et le mode de génération doivent être renseignés.
3. **Protection PII / secrets**: aucune fuite de secret technique ou donnée personnelle brute ne doit être exportée dans les artefacts JSON.
3. **Contrats techniques valides**: les schémas narratifs `narrative.v1` et `narrative.enriched.v1` doivent passer.
4. **Blocage préventif**: aucune violation bloquante de cohérence ne doit rester ouverte.

## Checks automatiques minimums avant publication/export

Les checks sont exécutés avant l’assemblage/export final et publiés dans:

- `outputs/legal_compliance_checks.json`
- `outputs/security_compliance_report.json`

Checks couverts:

- `schema_narrative_valid`
- `schema_enriched_valid`
- `consent_fields_present`
- `consent_export_granted`
- `provider_trace_present`
- `no_blocking_consistency_violations`
- `degraded_ratio_within_threshold`
- `provenance_fields_complete`
- `no_secrets_detected`

Le rapport `security_compliance_report.json` indique explicitement:

- le statut (`ok`/`failed`),
- si l’échec est **bloquant**,
- la liste de findings (`path`, `type`) détectés.

Si un check échoue, le pipeline est interrompu.

## Champs obligatoires de métadonnées (consentement/provenance)

Les contrats narratifs acceptent un objet racine `metadata` avec:

- `metadata.consent.user_consent_for_generation` (bool)
- `metadata.consent.user_consent_for_export` (bool)
- `metadata.consent.consent_source` (string)
- `metadata.consent.session_id` (string)
- `metadata.consent.captured_at` (string)
- `metadata.provenance.input_origin` (string)
- `metadata.provenance.generation_mode` (string)
- `metadata.provenance.human_review_required` (bool)
- `metadata.provenance.generated_at` (string)

## Checklist de revue manuelle (cas sensibles)

Revue humaine obligatoire si l’un des signaux suivants est détecté:

- sujets réglementés (santé, finance, juridique),
- présence de personnes identifiables ou de mineurs,
- contenu potentiellement diffamatoire, discriminatoire ou violent,
- demande explicite d’imitation d’une personne réelle,
- incohérences de consentement/provenance.

Checklist de validation:

1. Vérifier que le contexte et le prompt n’exposent pas de données personnelles non autorisées.
2. Vérifier la présence et la cohérence des champs de consentement/provenance.
3. Vérifier l’absence d’éléments sensibles non voulus dans synopsis/shots/audio.
4. Vérifier que la sortie finale respecte les limites de l’usage prévu (démo, interne, public).
5. Décider: **approuvé**, **approuvé avec restrictions**, ou **refusé** (avec justification).
