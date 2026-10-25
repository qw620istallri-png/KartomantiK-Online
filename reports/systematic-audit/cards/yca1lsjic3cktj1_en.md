# Nullifying Radiance

Identifiant : `yca1lsjic3cktj1_en`

## Texte de référence

When Nullifying Radiance enters the field, put 3 Flame counters on it and choose a base temperament.
Pay {H}{H} and remove a Flame counter: Cancel a target effect on the stack of the chosen temperament controlled by an opponent that targets a card on the field you control.

## Arbitrages confirmés

immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| radiance-enters-with-flames | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |
| radiance-cancels-a-matching-effect | pass | pass | pass | pass | pass | pass | pass | not-applicable | pass | pass |

## Parcours UI effectivement exécutés

| Capacité | Résultat | Résolution |
|---|---|---|
| radiance-cancels-a-matching-effect | pass | completed-no-pending-choice |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

cost:tribute, result:cancel_target_stack_effect, result:choose_source_temperament, target:stack_effect, trigger:enters_field

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
