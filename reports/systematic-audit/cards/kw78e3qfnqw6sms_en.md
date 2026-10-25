# Katun, the Inconsistent

Identifiant : `kw78e3qfnqw6sms_en`

## Texte de référence

As long as Katun is in the Interzone, whenever a manifestation leaves the field, a Limbo, an Empathic Vessel or the Stalemate Zone due to cards or effects, you gain 5 points.
If Katun has left an Empathic Vessel during the course of the game, instead whenever you trigger its effects you gain 10 points.

## Arbitrages confirmés

replacement-not-destruction, katun-either-controller, immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| katun-gains-five | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |
| katun-gains-ten-after-vessel | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

result:score_owner, trigger:manifestation_left_by_effect

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
