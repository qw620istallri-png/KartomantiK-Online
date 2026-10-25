# BOB

Identifiant : `inner-deserts-134`

## Texte de référence

Persist.
As long as BOB is in the Confrontation Zone, it gets +3 power at the beginning of each turn; it additionally gains all the following effects based on its power:
2+: Cards that are about to enter or leave a deck due to cards or effects are Suspended instead.
5+: Cards that are about to enter or leave a Limbo due to cards or effects are Suspended instead.
8+: Cards in each hand are immune to cards and effects.
If BOB leaves the Confrontation Zone, each player shuffles the cards Suspended this way into their deck.
If BOB reaches 11 power or more, Exile BOB and all cards Suspended this way.

## Arbitrages confirmés

simultaneous-order, immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| gain-three-power-at-beginning-of-turn | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

persist, result:add_counter_source, suspension-thresholds, trigger:beginning_of_turn

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
