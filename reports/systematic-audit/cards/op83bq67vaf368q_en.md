# Censor

Identifiant : `op83bq67vaf368q_en`

## Texte de référence

As an additional cost to play this Will, reveal and exile a manifestation from your hand.
Destroy a target manifestation in the Confrontation Zone with base power equal to or lower than that of the revealed manifestation.

## Arbitrages confirmés

immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| censor-exiles-hand-manifestation-to-destroy | pass | pass | pass | pass | pass | pass | pass | pass | pass | not-applicable |

## Parcours UI effectivement exécutés

| Capacité | Résultat | Résolution |
|---|---|---|
| censor-exiles-hand-manifestation-to-destroy | pass | completed-no-pending-choice |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.
- `test_reported_card_bugs` : 50 tests réussis.

## Mécaniques

result:hand_manifestation_choice, target:card

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`
- `tests/test_reported_card_bugs.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
