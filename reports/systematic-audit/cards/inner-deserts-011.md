# Chobariki, of the Shiny Muscles

Identifiant : `inner-deserts-011`

## Texte de référence

Support from hand.
Cannot be played as First Manifestation.
You may put Chobariki in Support under any player's control.
As long as Chobariki is not under its owner's control:
  • When Chobariki loses a confrontation, its owner gains 10 Points;
  • When Chobariki wins a confrontation, it returns to the top of its owner's deck.
As long as Chobariki is in the Interzone, you may pay 🌿: It gains Support until the end of the turn.

## Arbitrages confirmés

immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| enter-under-chosen-control | pass | pass | pass | pass | pass | pass | not-applicable | not-applicable | pass | not-applicable |
| pay-phlegmatic-essence-for-support | pass | pass | pass | pass | pass | pass | not-applicable | not-applicable | pass | pass |
| owner-scores-after-loss | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |
| return-after-win | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |

## Parcours UI effectivement exécutés

| Capacité | Résultat | Résolution |
|---|---|---|
| enter-under-chosen-control | pass | completed-no-pending-choice |
| pay-phlegmatic-essence-for-support | pass | completed-no-pending-choice |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

first-restriction, result:change_source_control, result:grant_source_support_until_end_turn, result:move_source_to_owner_deck_top, result:score_source_owner, support-from-hand, target:player, trigger:loses_confrontation, trigger:wins_confrontation

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
