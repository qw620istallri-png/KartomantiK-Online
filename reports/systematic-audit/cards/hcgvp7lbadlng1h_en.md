# Gummo

Identifiant : `hcgvp7lbadlng1h_en`

## Texte de référence

As long as Gummo is in the Interzone, at the end of the turn you may choose a manifestation in your Empathic Vessel. If you do, Gummo copies its base power and gains its effects in addition to its own until this effect is reused.
Upon the End of Recovery, you may pay {H}{H}{H}: Gummo enters the Confrontation Zone as First Manifestation from the Interzone.

## Arbitrages confirmés

immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| gummo-copies-vessel-manifestation | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |
| gummo-becomes-first-manifestation | pass | pass | pass | pass | pass | pass | not-applicable | not-applicable | pass | pass |

## Parcours UI effectivement exécutés

| Capacité | Résultat | Résolution |
|---|---|---|
| gummo-becomes-first-manifestation | pass | completed-no-pending-choice |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

cost:tribute, phase-window, result:gummo_copy_vessel, result:interzone_becomes_first_manifestation, trigger:end_of_turn

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
