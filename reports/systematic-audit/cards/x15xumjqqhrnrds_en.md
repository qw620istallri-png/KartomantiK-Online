# Glabron, the Oppressing

Identifiant : `x15xumjqqhrnrds_en`

## Texte de référence

As long as Glabron is in hand or in the Interzone, you can put into stalemate a manifestation in your Interzone: Glabron gains Support until the end of the turn.

## Arbitrages confirmés

immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| glabron-stalemates-own-interzone-card-for-support | pass | pass | pass | pass | pass | pass | pass | pass | pass | not-applicable |

## Parcours UI effectivement exécutés

| Capacité | Résultat | Résolution |
|---|---|---|
| glabron-stalemates-own-interzone-card-for-support | pass | completed-no-pending-choice |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.
- `test_reported_card_bugs` : 50 tests réussis.

## Mécaniques

result:stalemate_target_grant_source_support, target:card

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`
- `tests/test_reported_card_bugs.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
