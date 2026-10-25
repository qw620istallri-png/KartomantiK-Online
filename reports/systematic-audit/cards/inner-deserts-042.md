# Ababash, the Ambassador

Identifiant : `inner-deserts-042`

## Texte de référence

As long as Ababash is on the field, you may Exhaust it: Look at the top 3 cards of a target player's deck. You may exile one of those cards. Distribute any number of the remaining cards on the top and bottom of the deck.

## Arbitrages confirmés

immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| ababash-look-at-top-three | pass | pass | pass | pass | pass | pass | pass | not-applicable | pass | not-applicable |

## Parcours UI effectivement exécutés

| Capacité | Résultat | Résolution |
|---|---|---|
| ababash-look-at-top-three | pass | completed-no-pending-choice |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

cost:exhaustSource, result:reorder_top_decks, target:player

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
