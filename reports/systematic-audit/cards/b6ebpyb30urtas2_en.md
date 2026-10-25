# Freenya, Heartless Songstress

Identifiant : `b6ebpyb30urtas2_en`

## Texte de référence

As long as Freenya is on the field, whenever you play a Will from hand, you can play a Will from the Limbo without paying its tribute cost.
If the Wills played this way from the Limbo would enter a Limbo, a hand or a deck, exile them instead.

## Arbitrages confirmés

immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| freenya-free-limbo-will | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

result:grant_limbo_will_play, trigger:card_played

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`
- `tests/test_frontend.cjs`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
