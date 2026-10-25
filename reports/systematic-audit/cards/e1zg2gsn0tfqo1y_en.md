# Ergorath, Scribe of the Limbo

Identifiant : `e1zg2gsn0tfqo1y_en`

## Texte de référence

As long as Ergorath is on the field, you may play Wills from your Limbo by paying 1 {H} instead of their normal tribute cost.
If the Wills played this way are about to enter a Limbo, a hand or a deck, exile them instead.
If at the end of the turn Ergorath is in the Interzone, its controller loses 10 points, then it is shuffled into its owner's deck.

## Arbitrages confirmés

immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| ergorath-play-wills-from-limbo | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |
| ergorath-interzone-penalty | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

passive:play_wills_from_limbo_hollow_tribute, result:lose_points_shuffle_source_into_deck, trigger:end_of_turn

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`
- `tests/test_frontend.cjs`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
