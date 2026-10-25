# Cirrocumulus

Identifiant : `inner-deserts-080`

## Texte de référence

Support from hand; Float.
As long as Cirrocumulus is in the Interzone, you may sacrifice it: Resolve as an Immediate Effect a target card or effect you control on the Stack.

## Arbitrages confirmés

immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| sacrifice-to-resolve-controlled-stack-item | pass | pass | pass | pass | pass | pass | pass | not-applicable | pass | not-applicable |

## Parcours UI effectivement exécutés

| Capacité | Résultat | Résolution |
|---|---|---|
| sacrifice-to-resolve-controlled-stack-item | pass | completed-no-pending-choice |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

cost:sacrificeSource, float, result:resolve_target_stack_immediately, support-from-hand, target:stack_item

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
