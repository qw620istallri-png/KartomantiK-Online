# Soul-borer

Identifiant : `wfxxi0znaojxiti_en`

## Texte de référence

As long as the Soul-Borer is in an opponent's Empathic Vessel, at the beginning of each turn that player loses 5 points.

## Arbitrages confirmés

immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| vessel-owner-loses-five-each-turn | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

result:score_source_container, trigger:beginning_of_turn

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
