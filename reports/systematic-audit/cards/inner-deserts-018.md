# Paciphint, the Pious

Identifiant : `inner-deserts-018`

## Texte de référence

Paciphint enters the field with 2 Flower Counters on it.
As long as Paciphint is on the field, during Reaction you may remove 1 Flower Counter: Put a manifestation on the field you control other than Paciphint on the bottom of its owner's deck. If you do, the power of a target manifestation in the Confrontation Zone is not considered for the resolution of the confrontation.
As long as Paciphint is in the Interzone, whenever you lose a confrontation, put 1 Flower Counter on it.

## Arbitrages confirmés

immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| paciphint-enters-with-flowers | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |
| paciphint-blooms-when-its-owner-loses | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |
| paciphint-sacrifices-an-ally-to-ignore-a-power | pass | pass | pass | pass | pass | pass | pass | pass | pass | not-applicable |

## Parcours UI effectivement exécutés

| Capacité | Résultat | Résolution |
|---|---|---|
| paciphint-sacrifices-an-ally-to-ignore-a-power | pass | completed-no-pending-choice |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

phase-window, result:add_counter_source, result:paciphint_swap, trigger:enters_field, trigger:player_loses_confrontation

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
