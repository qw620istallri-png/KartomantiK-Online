# Convert the Pain

Identifiant : `inner-deserts-021`

## Texte de référence

Destroy up to 2 target Manifestations in Support. Each player draws 2 cards for each Manifestation they control destroyed this way.

## Arbitrages confirmés

immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| convert-the-pain | pass | pass | pass | pass | pass | pass | not-applicable | pass | pass | pass |

## Parcours UI effectivement exécutés

| Capacité | Résultat | Résolution |
|---|---|---|
| convert-the-pain | pass | completed-no-pending-choice |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

result:destroy_support_targets_draw, target:card

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
