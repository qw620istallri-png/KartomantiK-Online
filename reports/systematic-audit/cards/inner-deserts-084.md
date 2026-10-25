# Chabak, the Ungrateful

Identifiant : `inner-deserts-084`

## Texte de référence

As long as Chabak is in your hand, you may put 2 Manifestations from your hand into the Stalemate Zone: Play Chabak in Support.
When Chabak wins a Confrontation, each Manifestation in the Confrontation Zone under the opponents' control returns to the bottom of its owner's deck. The owner determines their order. Then Exile Chabak.

## Arbitrages confirmés

immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| chabak-plays-in-support-for-two-manifestations | pass | pass | pass | pass | pass | pass | not-applicable | not-applicable | pass | not-applicable |
| chabak-returns-opposing-manifestations-and-exiles-itself | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |

## Parcours UI effectivement exécutés

| Capacité | Résultat | Résolution |
|---|---|---|
| chabak-plays-in-support-for-two-manifestations | pass | completed-no-pending-choice |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

phase-window, result:chabak_support, result:chabak_wins, trigger:wins_confrontation

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
