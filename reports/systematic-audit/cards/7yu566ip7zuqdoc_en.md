# Malaleuco, the Will-shaper

Identifiant : `7yu566ip7zuqdoc_en`

## Texte de référence

As long as Malaleuco is in the Interzone, you can exhaust it to copy a Will on the stack that you control. You can choose a new target for the copy.
If Malaleuco is in hand and there is space in your Interzone, you can pay {B}{B}{B}: Put it in your Interzone.

## Arbitrages confirmés

immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| malaleuco-copy-will | pass | pass | pass | pass | pass | pass | pass | not-applicable | pass | not-applicable |
| malaleuco-to-interzone | pass | pass | pass | pass | pass | pass | not-applicable | not-applicable | pass | pass |

## Parcours UI effectivement exécutés

| Capacité | Résultat | Résolution |
|---|---|---|
| malaleuco-copy-will | pass | completed-no-pending-choice |
| malaleuco-to-interzone | pass | completed-no-pending-choice |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

cost:exhaustSource, cost:tribute, result:copy_stack_action, result:move_hand_source_to_interzone, target:stack_action

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
