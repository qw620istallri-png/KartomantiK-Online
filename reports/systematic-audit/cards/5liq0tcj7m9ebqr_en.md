# Intoxicating Blossom

Identifiant : `5liq0tcj7m9ebqr_en`

## Texte de référence

Whenever a manifestation enters the field under your control, put a Petal counter on Intoxicating Blossom.
Pay {H}{H} and remove the Petal counters from Intoxicating Blossom: A target manifestation on the field gets +1 power for each Petal counter removed in this way.

## Arbitrages confirmés

immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| gain-petal-on-friendly-manifestation-entry | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |
| spend-petals-for-power | pass | pass | pass | pass | pass | pass | pass | pass | pass | pass |

## Parcours UI effectivement exécutés

| Capacité | Résultat | Résolution |
|---|---|---|
| spend-petals-for-power | pass | completed-no-pending-choice |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

cost:removeAllCountersFromSource, cost:tribute, ongoing:power_modifier, result:add_counter_source, trigger:manifestation_enters_field

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
