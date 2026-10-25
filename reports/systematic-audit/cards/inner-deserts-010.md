# Gusted Nebula

Identifiant : `inner-deserts-010`

## Texte de référence

Support from hand; Float.
As long as Gusted Nebula is in the Interzone, you may Sacrifice it: Each player puts the manifestations in Support they control on top of their respective owner's deck in any order, then each First Manifestation gains +1 power until the end of the turn for each manifestation moved this way by its controller.

## Arbitrages confirmés

immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| sacrifice-to-return-supports | pass | pass | pass | pass | pass | pass | not-applicable | not-applicable | pass | not-applicable |

## Parcours UI effectivement exécutés

| Capacité | Résultat | Résolution |
|---|---|---|
| sacrifice-to-return-supports | pass | completed-no-pending-choice |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

cost:sacrificeSource, float, result:return_supports_and_boost_firsts, support-from-hand

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
