# Donmo, the Truth-Bender

Identifiant : `inner-deserts-121`

## Texte de référence

Cannot be used as tribute.
As long as Donmo is in the Interzone, you may Exhaust it: Restore one target Exhausted card for each Temperament, other than Donmo.
As long as Donmo is on the field, at the end of the turn each opponent gains 5 Points for each Exhausted card under your control.

## Arbitrages confirmés

immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| donmo-restores-exhausted-cards | pass | pass | pass | pass | pass | pass | pass | pass | pass | not-applicable |
| donmo-gives-opponents-points-for-exhausted | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |

## Parcours UI effectivement exécutés

| Capacité | Résultat | Résolution |
|---|---|---|
| donmo-restores-exhausted-cards | pass | completed-no-pending-choice |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

cost:exhaustSource, result:restore_exhausted_targets, result:score_each_opponent, trigger:end_of_turn

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
