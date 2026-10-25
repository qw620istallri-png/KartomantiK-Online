# The Slumberer

Identifiant : `nlbgn1ranlrd09r_en`

## Texte de référence

Cannot be used as tribute. Can only be played as if it were a persistent Will.
When The Slumberer enters the field, put 3 Sleep counters on it. If you lose a confrontation while The Slumberer has Sleep counters, the winner puts it in their Empathic Vessel, otherwise remove a Sleep counter. At the beginning of the turn, if there are no Sleep counters on The Slumberer, it enters the Confrontation Zone as First Manifestation and gains Persist.

## Arbitrages confirmés

slumberer-entry, immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| slumberer-falls-asleep | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |
| slumberer-taken-by-the-winner | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |
| slumberer-sleeps-deeper | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |
| slumberer-sleeps-deeper-on-stalemate | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |
| slumberer-wakes-up | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

first-restriction, result:add_counter_source, result:slumberer_wakes, result:source_to_winner_vessel, trigger:beginning_of_turn, trigger:confrontation_stalemate, trigger:enters_field, trigger:player_loses_confrontation, trigger:player_wins_confrontation

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
