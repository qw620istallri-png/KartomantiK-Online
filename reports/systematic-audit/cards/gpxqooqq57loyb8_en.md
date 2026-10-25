# Reviving Cage

Identifiant : `gpxqooqq57loyb8_en`

## Texte de référence

As long as the Reviving Cage is in the Interzone, you can exile it: Put a target manifestation from your Limbo into the Interzone.

## Arbitrages confirmés

immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| reviving-cage | pass | pass | pass | pass | pass | pass | pass | not-applicable | pass | not-applicable |

## Parcours UI effectivement exécutés

| Capacité | Résultat | Résolution |
|---|---|---|
| reviving-cage | pass | completed-no-pending-choice |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

cost:sacrificeSource, result:move_zone_target_to_field_zone, target:zone_card

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
