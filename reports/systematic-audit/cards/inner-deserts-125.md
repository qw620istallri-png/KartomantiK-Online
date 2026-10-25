# Haltan, the Favored

Identifiant : `inner-deserts-125`

## Texte de référence

Support from hand; Float.
As long as Haltan is on the field, you may Exhaust it: Make a target player gain or lose 10 Points.
Exhaust and Sacrifice Haltan: Immediate Effect - Players cannot gain or lose Points until the end of the turn.

## Arbitrages confirmés

immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| exhaust-to-change-points | pass | pass | pass | pass | pass | pass | pass | not-applicable | pass | not-applicable |
| exhaust-sacrifice-to-prevent-point-changes | pass | pass | pass | pass | pass | pass | not-applicable | not-applicable | pass | not-applicable |

## Parcours UI effectivement exécutés

| Capacité | Résultat | Résolution |
|---|---|---|
| exhaust-to-change-points | pass | completed-no-pending-choice |
| exhaust-sacrifice-to-prevent-point-changes | pass | completed-no-pending-choice |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

cost:exhaustSource, cost:sacrificeSource, float, ongoing:prevent_point_changes, result:choose_target_score_delta, support-from-hand, target:player

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
