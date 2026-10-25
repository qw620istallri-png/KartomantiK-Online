# Referen-Doom, the Dreamer

Identifiant : `inner-deserts-038`

## Texte de référence

When Referen-Doom enters the field, you may Exile any number of target Wills from your Limbo. Referen-Doom gets +1 power for each Will Exiled this way until the end of the turn.
When Referen-Doom loses a Confrontation, you gain a number of 🌈 essences equal to its power.

## Arbitrages confirmés

immediate, source-power-after-departure

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| referen-doom-exiles-limbo-wills | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |
| referen-doom-gains-rainbow-essence-on-loss | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

result:create_essence, result:exile_limbo_wills_add_power_each, target:zone_card, trigger:enters_field, trigger:loses_confrontation

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
