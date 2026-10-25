# Regurgitating Catacomb

Identifiant : `inner-deserts-067`

## Texte de référence

When Regurgitating Catacomb enters the field, put 3 Bone Counters on it.
Remove a Bone Counter from Regurgitating Catacomb and Exhaust it: Put in Support under your control a target Manifestation from your Limbo discarded this turn.
If that Manifestation wins the Confrontation or would leave the Confrontation Zone due to cards or effects, exile it.

## Arbitrages confirmés

immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| catacomb-bone-counters | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |
| catacomb-raise-discarded-manifestation | pass | pass | pass | pass | pass | pass | pass | not-applicable | pass | not-applicable |

## Parcours UI effectivement exécutés

| Capacité | Résultat | Résolution |
|---|---|---|
| catacomb-raise-discarded-manifestation | pass | completed-no-pending-choice |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

cost:exhaustSource, result:add_counter_source, result:play_limbo_target_as_support, target:zone_card, trigger:enters_field

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
