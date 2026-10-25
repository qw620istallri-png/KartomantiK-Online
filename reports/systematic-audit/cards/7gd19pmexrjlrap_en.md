# Annihilating Nectar

Identifiant : `7gd19pmexrjlrap_en`

## Texte de référence

When Annihilating Nectar enters the field, choose a target manifestation on the field.
That manifestation loses all its effects.
In the End Phase, you may exhaust this card and pay {Y}: Change the target of the effect of this card.

## Arbitrages confirmés

cleanse-links, immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| nectar-disable-target | pass | pass | pass | pass | pass | pass | pass | pass | pass | pass |
| nectar-retarget-disable | pass | pass | pass | pass | pass | pass | pass | pass | pass | pass |

## Parcours UI effectivement exécutés

| Capacité | Résultat | Résolution |
|---|---|---|
| nectar-disable-target | pass | completed-no-pending-choice |
| nectar-retarget-disable | pass | completed-no-pending-choice |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

cost:exhaustSource, cost:tribute, ongoing:lose_effects, phase-window, result:retarget_source_effect

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
