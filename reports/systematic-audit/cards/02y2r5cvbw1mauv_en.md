# Jija, Matron Bomb

Identifiant : `02y2r5cvbw1mauv_en`

## Texte de référence

When Jija enters the Confrontation Zone, put into Support under your control a token with 1 power {H} for each manifestation in the Interzone of a target player.
As long as Jija is in the Confrontation Zone, you can sacrifice a token created by her and lose 5 points: A target manifestation on the field gets -2 power.
If Jija is put on the bottom of the deck, shuffle it.

## Arbitrages confirmés

immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| create-hollow-tokens-for-target-interzone | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |
| sacrifice-created-token-for-power-loss | pass | pass | pass | pass | pass | pass | pass | pass | pass | not-applicable |

## Parcours UI effectivement exécutés

| Capacité | Résultat | Résolution |
|---|---|---|
| sacrifice-created-token-for-power-loss | pass | completed-no-pending-choice |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

ongoing:power_modifier, result:create_tokens_for_target_interzone_count, target:player, trigger:enters_field_zone

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
