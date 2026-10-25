# Gobres, the Collector

Identifiant : `inner-deserts-088`

## Texte de référence

Adamant.
As long as Gobres is in the Interzone, before the Revelation a target opponent chooses a Will from their hand and Suspends it until the end of the turn. As long as it is Suspended, the opponent cannot play it.
You may play that Will by paying its cost in tributes with any Temperament as long as it is Suspended and, if you don’t play it or if Gobres leaves the field, that Will returns to its owner's hand.

## Arbitrages confirmés

immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| suspend-opponent-will-before-revelation | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.
- `test_websocket_integration` : 20 tests réussis.

## Mécaniques

adamant, result:suspend_opponent_hand_will, target:player, trigger:before_revelation

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`
- `tests/test_websocket_integration.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
