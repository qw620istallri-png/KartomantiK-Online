# Denblew, the Puritan

Identifiant : `inner-deserts-026`

## Texte de référence

Support.
Cannot be played as First Manifestation.
As long as Denblew is on the field, if an opponent draws one or more cards during the turn outside of the Recovery Phase, Denblew gets +1 power until the end of the turn.

## Arbitrages confirmés

immediate, denblew-draw-events

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| denblew-grows-when-opponent-draws | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

first-restriction, ongoing:power_modifier, support-from-hand, support-from-interzone, trigger:cards_drawn

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
