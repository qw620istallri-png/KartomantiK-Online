# Zborh, the Eternal

Identifiant : `inner-deserts-015`

## Texte de référence

Adamant.
As long as Zborh is in the Interzone, when its controller loses a confrontation, upon Resolution Zborh returns to its owner's hand.

## Arbitrages confirmés

immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| zborh-returns-after-controller-loses | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_game_state` : 482 tests réussis.

## Mécaniques

adamant, result:move_source_to_owner_hand, trigger:player_loses_confrontation

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
