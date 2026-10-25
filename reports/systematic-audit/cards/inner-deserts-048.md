# Wish Upon the Stars

Identifiant : `inner-deserts-048`

## Texte de référence

Choose a Manifestation in your Empathic Vessel. Its owner chooses a Manifestation you own in their Empathic Vessel with points equal to or greater than the one you chose. If they can do so, those Manifestations return to the top of their owners' decks.

## Arbitrages confirmés

immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| wish-upon-the-stars-exchanges-vessel-manifestations | pass | pass | pass | pass | pass | pass | pass | not-applicable | pass | pass |

## Parcours UI effectivement exécutés

| Capacité | Résultat | Résolution |
|---|---|---|
| wish-upon-the-stars-exchanges-vessel-manifestations | pass | completed-no-pending-choice |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

result:wish_exchange, target:zone_card

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
