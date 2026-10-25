# Rinq, Shameless Slacker

Identifiant : `b5ge92hr33pdwc7_en`

## Texte de référence

As long as Rinq is on the field, you can pay {H}{H}: A target persistent Will on the field you control becomes a manifestation with power {H} equal to its tribute cost until the Resolution and enters in Support under your control.
If the Will loses the confrontation, destroy it.

## Arbitrages confirmés

cleanse-animation, immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| rinq-persistent-will-becomes-support | pass | pass | pass | pass | pass | pass | pass | pass | pass | pass |

## Parcours UI effectivement exécutés

| Capacité | Résultat | Résolution |
|---|---|---|
| rinq-persistent-will-becomes-support | pass | completed-no-pending-choice |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

cost:tribute, phase-window, result:will_becomes_support_manifestation, target:card

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
