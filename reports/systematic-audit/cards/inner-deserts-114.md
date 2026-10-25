# Sandokaron, Banners Bearer

Identifiant : `inner-deserts-114`

## Texte de référence

Sandokaron enters the field with 1 Banner Counter.
As long as Sandokaron is on the field, when you win a confrontation put 1 Banner Counter on it. If instead you lose a confrontation, remove 1 Banner Counter.
As long as Sandokaron is on the field, you may remove 1 Banner Counter and choose one:
  •  A target manifestation on the field gets +3 power;
  •  Gain 2 🔥 essences.
If at the end of the turn there are no Banner Counters on Sandokaron, Exile it.

## Arbitrages confirmés

immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| sandokaron-banner-on-enter | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |
| sandokaron-banner-on-win | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |
| sandokaron-banner-lost-on-loss | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |
| sandokaron-banner-power | pass | pass | pass | pass | pass | pass | pass | pass | pass | not-applicable |
| sandokaron-banner-essence | pass | dedicated-path | dedicated-path | dedicated-path | dedicated-path | dedicated-path | dedicated-path | dedicated-path | dedicated-path | dedicated-path |
| sandokaron-exile-without-banner | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |

## Parcours UI effectivement exécutés

| Capacité | Résultat | Résolution |
|---|---|---|
| sandokaron-banner-power | pass | completed-no-pending-choice |
| sandokaron-banner-essence | pass | completed-no-pending-choice |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

ongoing:power_modifier, result:add_counter_source, result:create_essence, result:move_source_to_owner_exile, trigger:end_of_turn, trigger:enters_field, trigger:player_loses_confrontation, trigger:player_wins_confrontation

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
