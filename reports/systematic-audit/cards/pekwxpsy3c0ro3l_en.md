# Urolong, Rueful Necromancer

Identifiant : `pekwxpsy3c0ro3l_en`

## Texte de référence

As long as it is in the Interzone, you may exhaust Urolong and pay {H}{H}: Put a target manifestation from your Limbo into Support under your control. As long as that card is on the field, it loses its effects.
If that manifestation wins the confrontation, exile it.

## Arbitrages confirmés

slumberer-entry, immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| urolong-raises-limbo-manifestation | pass | pass | pass | pass | pass | pass | pass | not-applicable | pass | pass |

## Parcours UI effectivement exécutés

| Capacité | Résultat | Résolution |
|---|---|---|
| urolong-raises-limbo-manifestation | pass | completed-no-pending-choice |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

cost:exhaustSource, cost:tribute, result:play_limbo_target_as_support, target:zone_card

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
