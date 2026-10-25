# Ranba, Silent Abductor

Identifiant : `fdnhc537c4xu2wo_en`

## Texte de référence

During the Reaction, as long as the last manifestation that entered in Support under the control of an opponent has a base power equal to or less than 2, you may reveal and discard Ranba from your hand. If you do and you are not the owner of that manifestation, put it into your Empathic Vessel.

## Arbitrages confirmés

immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| ranba-abduct-weak-support | pass | pass | pass | pass | pass | pass | not-applicable | not-applicable | pass | not-applicable |

## Parcours UI effectivement exécutés

| Capacité | Résultat | Résolution |
|---|---|---|
| ranba-abduct-weak-support | pass | completed-no-pending-choice |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

condition:last_opponent_support_low_power, phase-window, result:take_last_opponent_support_to_vessel

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
