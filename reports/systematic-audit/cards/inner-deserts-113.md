# Lilitha, the Dismemberer

Identifiant : `inner-deserts-113`

## Texte de référence

Support from hand.
Cannot be played as First Manifestation.
When Lilitha enters the Confrontation Zone, you may Destroy a target manifestation in the Confrontation Zone. If you do, that manifestation’s controller puts a number of Tokens with 1 🔘 power equal to its base power in Support under their control.
When Lilitha wins a confrontation, Exile it.

## Arbitrages confirmés

immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| lilitha-dismembers-confrontation-manifestation | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |
| lilitha-exiles-after-win | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

first-restriction, result:destroy_target_tokens_for_controller, result:move_source_to_owner_exile, support-from-hand, target:card, trigger:enters_field_zone, trigger:wins_confrontation

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
