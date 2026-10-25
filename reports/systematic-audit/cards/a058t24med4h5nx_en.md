# Atavic Oppression

Identifiant : `a058t24med4h5nx_en`

## Texte de référence

This card is {P} and can be played before the Revelation.
Whenever you play a {P} card, put a Fatigue counter on Atavic Oppression.
Remove 5 Fatigue counters: Each opponent discards a card from their hand and you draw a card.
As long as there are 10 or more Fatigue counters on Atavic Oppression, at the end of the turn you can discard up to two cards from your hand.

## Arbitrages confirmés

immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| fatigue-counter-on-own-purple-card | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |
| spend-fatigues-to-make-opponent-discard | pass | pass | pass | pass | pass | pass | not-applicable | not-applicable | pass | not-applicable |
| fatigue-ten-discard-up-to-two-at-end-of-turn | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |

## Parcours UI effectivement exécutés

| Capacité | Résultat | Résolution |
|---|---|---|
| spend-fatigues-to-make-opponent-discard | pass | completed-no-pending-choice |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

result:add_counter_source, result:discard_hand_each_opponent, result:optional_discard_up_to, trigger:card_played, trigger:end_of_turn

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
