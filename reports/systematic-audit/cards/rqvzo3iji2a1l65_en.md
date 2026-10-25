# Atavic Volatility

Identifiant : `rqvzo3iji2a1l65_en`

## Texte de référence

This card is {Y} and can be played before the Revelation.
Whenever you play a {Y} card, put a Coil counter on the Atavic Volatility.
Remove 5 Coil counters: Each player puts into stalemate a manifestation they control in the Confrontation Zone.
As long as there are 10 or more Coil counters on the Atavic Volatility, at the beginning of the turn you can choose a target manifestation on the field. That manifestation loses its effects until the end of the turn.

## Arbitrages confirmés

immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| coil-counter-on-own-yellow-card | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |
| disable-target-at-turn-start-with-ten-coils | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |
| spend-coils-to-stalemate-own-manifestations | pass | pass | pass | pass | pass | pass | not-applicable | not-applicable | pass | not-applicable |

## Parcours UI effectivement exécutés

| Capacité | Résultat | Résolution |
|---|---|---|
| spend-coils-to-stalemate-own-manifestations | pass | completed-no-pending-choice |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

ongoing:lose_effects, result:add_counter_source, result:each_player_stalemate_own_confrontation, trigger:beginning_of_turn, trigger:card_played

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
