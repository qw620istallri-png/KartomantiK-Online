# Explosive Rancor

Identifiant : `inner-deserts-141`

## Texte de référence

Pay 🔘🔘🔘🔘: Exile all Manifestations in the Confrontation Zone and in the Stalemate Zone. Exile Explosive Rancor.

## Arbitrages confirmés

immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| explosive-rancor-exiles-confrontation-and-stalemate | pass | pass | pass | pass | pass | pass | not-applicable | not-applicable | pass | pass |

## Parcours UI effectivement exécutés

| Capacité | Résultat | Résolution |
|---|---|---|
| explosive-rancor-exiles-confrontation-and-stalemate | pass | completed-no-pending-choice |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

cost:tribute, result:exile_confrontation_stalemate_and_source

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
