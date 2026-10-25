# Juggernut, the Overwhelming

Identifiant : `inner-deserts-100`

## Texte de référence

Juggernut can only be played as if it were a Persistent Will.
As long as Juggernut is on the field, at the end of each turn, it gets +3 power.
Upon the end of Recovery, you may pay 🔘🔘: Juggernut enters the Confrontation Zone as First Manifestation.
When Juggernut wins a Confrontation, Exile it.

## Arbitrages confirmés

juggernut, immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| juggernut-grows-at-end-of-turn | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |
| juggernut-charges-into-confrontation | pass | pass | pass | pass | pass | pass | not-applicable | not-applicable | pass | pass |
| juggernut-exiled-after-winning | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |

## Parcours UI effectivement exécutés

| Capacité | Résultat | Résolution |
|---|---|---|
| juggernut-charges-into-confrontation | pass | completed-no-pending-choice |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

cost:tribute, first-restriction, phase-window, result:add_counter_source, result:field_becomes_first_manifestation, result:move_source_to_owner_exile, trigger:end_of_turn, trigger:wins_confrontation

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
