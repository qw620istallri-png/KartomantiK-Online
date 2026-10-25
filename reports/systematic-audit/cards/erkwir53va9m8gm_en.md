# Atavic Welcome

Identifiant : `erkwir53va9m8gm_en`

## Texte de référence

This card is {G} and can be played before the Revelation.
Whenever you play a {G} card, put a Union counter on Atavic Welcome.
Remove 5 Union counters: Put 2 tokens with 1 power {G} into Support.
As long as there are 10 or more Union counters on Atavic Welcome, whenever a manifestation enters Support under your control you gain 5 points.

## Arbitrages confirmés

immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| union-counter-on-own-green-card | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |
| spend-unions-for-support-tokens | pass | pass | pass | pass | pass | pass | not-applicable | not-applicable | pass | not-applicable |
| gain-points-when-support-enters-with-ten-unions | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |

## Parcours UI effectivement exécutés

| Capacité | Résultat | Résolution |
|---|---|---|
| spend-unions-for-support-tokens | pass | completed-no-pending-choice |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.
- `test_websocket_integration` : 20 tests réussis.

## Mécaniques

result:add_counter_source, result:create_support_tokens, result:score_owner, trigger:card_played, trigger:enters_support

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`
- `tests/test_websocket_integration.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
