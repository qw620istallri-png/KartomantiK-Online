# Nullify Reason

Identifiant : `36l7iw5m5hk1pmr_en`

## Texte de référence

Until the end of the turn, all manifestations that are about to enter the Interzone, the deck and the Limbo of a target player are exiled instead.

## Arbitrages confirmés

simultaneous-order, immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| nullify-reason-exile-incoming | pass | pass | pass | pass | pass | pass | pass | not-applicable | pass | pass |

## Parcours UI effectivement exécutés

| Capacité | Résultat | Résolution |
|---|---|---|
| nullify-reason-exile-incoming | pass | completed-no-pending-choice |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

ongoing:exile_incoming_manifestations, target:player

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
