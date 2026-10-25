# Buddhan the Dark

Identifiant : `g02zvmqx3loxlcv_en`

## Texte de référence

When Buddhan the Dark enters the Confrontation Zone, roll a D6. Discard from the top of the deck an amount of cards equal to the result of the roll. Buddhan the Dark gets +1 power for each card discarded this way.
If Buddhan the Dark wins the confrontation, each opponent discards a card from the top of their deck for each card you discarded because of this effect.

## Arbitrages confirmés

modifier-expiration, immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| buddhan-dark-rolls-and-discards | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |
| buddhan-dark-opponents-discard-on-win | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

result:opponents_discard_deck_by_source_roll, result:roll_discard_deck_gain_power, trigger:enters_field_zone, trigger:wins_confrontation

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
