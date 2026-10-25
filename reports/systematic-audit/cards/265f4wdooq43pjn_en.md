# Atavic Introspection

Identifiant : `265f4wdooq43pjn_en`

## Texte de référence

This card is {B} and can be played before the Revelation.
Whenever you play a {B} card, put a Control counter on the Atavic Introspection.
Remove 5 Control counters: A target manifestation on the field returns to its owner's hand, it cannot be played until the end of the turn.
As long as there are 10 or more Control counters on the Atavic Introspection, at the end of the turn you can choose 2 cards in the Limbo and put one on the top and one on the bottom of your deck.

## Arbitrages confirmés

immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| control-counter-on-own-blue-card | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |
| spend-controls-to-bounce-manifestation | pass | pass | pass | pass | pass | pass | pass | pass | pass | not-applicable |
| split-two-limbo-cards-at-end-of-turn-with-ten-controls | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |

## Parcours UI effectivement exécutés

| Capacité | Résultat | Résolution |
|---|---|---|
| spend-controls-to-bounce-manifestation | pass | completed-no-pending-choice |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.
- `test_websocket_integration` : 20 tests réussis.

## Mécaniques

result:add_counter_source, result:move_target, result:split_targeted_limbo_cards, target:zone_card, trigger:card_played, trigger:end_of_turn

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`
- `tests/test_websocket_integration.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
