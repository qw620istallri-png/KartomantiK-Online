# Shattered Memory

Identifiant : `inner-deserts-136`

## Texte de référence

Exhaust this card: Exile a target card in a player's Limbo.
Exile this card: You gain 1 🌈 essence.

## Arbitrages confirmés

immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| shattered-memory-exile-limbo-card | pass | pass | pass | pass | pass | pass | pass | not-applicable | pass | not-applicable |
| shattered-memory-sacrifice-for-essence | pass | dedicated-path | dedicated-path | dedicated-path | dedicated-path | dedicated-path | dedicated-path | dedicated-path | dedicated-path | dedicated-path |

## Parcours UI effectivement exécutés

| Capacité | Résultat | Résolution |
|---|---|---|
| shattered-memory-exile-limbo-card | pass | completed-no-pending-choice |
| shattered-memory-sacrifice-for-essence | pass | completed-no-pending-choice |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

cost:exhaustSource, cost:sacrificeSource, result:create_essence, result:move_target, target:zone_card

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
