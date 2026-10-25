# Bibi, the Confused

Identifiant : `inner-deserts-127`

## Texte de référence

Support from hand.
Cannot be played as First Manifestation.
You may put Bibi in Support under any player's control.
When Bibi enters the field, its Controller rolls a D6 and based on the result applies the following effects: If it is odd, a target card on the field you control other than Bibi loses its current effects until the end of the turn. If it is even, draw a card.
When Bibi wins a Confrontation, its Controller loses Points based on the result of the roll: 1 or 2 = -5 Points ; 3 or 4 = -10 Points ; 5 or 6 = -15 Points. Then Exile Bibi.

## Arbitrages confirmés

immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| enter-under-chosen-control | pass | pass | pass | pass | pass | pass | not-applicable | not-applicable | pass | not-applicable |
| roll-on-enter-field | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |
| lose-by-roll-then-exile | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |

## Parcours UI effectivement exécutés

| Capacité | Résultat | Résolution |
|---|---|---|
| enter-under-chosen-control | pass | completed-no-pending-choice |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

first-restriction, result:change_source_control, result:roll_d6_conditional_source, result:score_controller_by_source_roll_then_exile, support-from-hand, target:player, trigger:enters_field, trigger:wins_confrontation

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
