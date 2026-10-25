# Bloatuba

Identifiant : `vt30v1v8anw5hib_en`

## Texte de référence

When the Bloatuba enters the field, you may Chain from your hand. A target opponent reveals a number of cards from the top of the deck equal to the base power of the Chained manifestation. If they can, the opponent chooses and puts into stalemate a manifestation among those cards, then you reorder the remaining cards and the opponent puts them at the bottom of their deck in the order established by you.

## Arbitrages confirmés

immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| bloatuba-chain-reveals-opponent-top | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

result:chain_from_zone, trigger:enters_field

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
