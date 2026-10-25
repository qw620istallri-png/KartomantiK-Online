# Atavic Fury

Identifiant : `m2l3v60n0iakrm2_en`

## Texte de référence

This card is {R} and can be played before the Revelation.
Whenever you play a {R} card, put a Violence counter on Atavic Fury.
Remove 5 Violence counters: A target manifestation on the field gets -2 power.
As long as there are 10 or more Violence counters on Atavic Fury, whenever you win a confrontation, you gain 10 points.

## Arbitrages confirmés

immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| violence-counter-on-own-red-card | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |
| spend-violence-to-shrink-manifestation | pass | pass | pass | pass | pass | pass | pass | pass | pass | not-applicable |
| gain-points-on-win-with-ten-violence | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |

## Parcours UI effectivement exécutés

| Capacité | Résultat | Résolution |
|---|---|---|
| spend-violence-to-shrink-manifestation | pass | completed-no-pending-choice |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.
- `test_websocket_integration` : 20 tests réussis.

## Mécaniques

ongoing:power_modifier, result:add_counter_source, result:score_owner, trigger:card_played, trigger:player_wins_confrontation

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`
- `tests/test_websocket_integration.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
