# Buddhan the Transcended

Identifiant : `kmvhsfddh84cpq6_en`

## Texte de référence

When Buddhan the Transcended enters the field, put 3 Quiet counters on it and, as long as it is on the field, if due to cards or effects a manifestation loses power, a player discards cards or loses points, remove a Quiet counter from Buddhan the Transcended. When there are no Quiet counters on Buddhan the Transcended, it becomes of {H} temperament and gains: At the beginning of the turn, each player exiles a random manifestation from their Empathic Vessel.

## Arbitrages confirmés

modifier-expiration, immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| buddhan-quiet-on-enter | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |
| buddhan-quiet-power-lost | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |
| buddhan-quiet-cards-discarded | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |
| buddhan-quiet-points-lost | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |
| buddhan-awakened-exiles-vessels | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

result:add_counter_source, result:move_random_zone_card, trigger:beginning_of_turn, trigger:cards_discarded, trigger:enters_field, trigger:points_lost, trigger:power_lost

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
