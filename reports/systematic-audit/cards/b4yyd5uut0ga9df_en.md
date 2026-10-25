# Hot Potato

Identifiant : `b4yyd5uut0ga9df_en`

## Texte de référence

When the Hot Potato enters the field, it passes under the control of a target opponent with a Burn counter on it.
The player who controls the Hot Potato can pay a number of {H} essences equal to how many Burn counters are on it: The Hot Potato passes under the control of a target opponent with one more Burn counter.
At the end of the turn, the player who controls it loses 40 points, then the Hot Potato is destroyed.

## Arbitrages confirmés

immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| enter-under-opponent-control-with-burn | pass | pass | pass | pass | pass | pass | pass | not-applicable | pass | pass |
| pass-control-with-more-burn | pass | pass | pass | pass | pass | pass | pass | not-applicable | pass | not-applicable |
| controller-loses-forty-then-destroy | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |

## Parcours UI effectivement exécutés

| Capacité | Résultat | Résolution |
|---|---|---|
| enter-under-opponent-control-with-burn | pass | completed-no-pending-choice |
| pass-control-with-more-burn | pass | completed-no-pending-choice |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

result:change_source_control, result:score_controller_then_destroy_source, target:player, trigger:end_of_turn

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
