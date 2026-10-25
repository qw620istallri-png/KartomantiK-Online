# Temperamental Splendor

Identifiant : `inner-deserts-143`

## Texte de référence

When Temperamental Splendor enters the field, put 2 Gem Counters on it and choose a base Temperament. Those Counters can be removed and used at any time as if they were excess essence of the chosen Temperament.
If there are no more Gem Counters on Temperamental Splendor, Exile it.

## Arbitrages confirmés

immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| splendor-chooses-a-base-temperament | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |
| splendor-spends-a-gem-as-excess-essence | pass | dedicated-path | dedicated-path | dedicated-path | dedicated-path | dedicated-path | dedicated-path | dedicated-path | dedicated-path | dedicated-path |

## Parcours UI effectivement exécutés

| Capacité | Résultat | Résolution |
|---|---|---|
| splendor-spends-a-gem-as-excess-essence | pass | completed-no-pending-choice |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

result:choose_source_temperament, result:create_essence, trigger:enters_field

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
