# Thoughtcutter

Identifiant : `inner-deserts-086`

## Texte de référence

As long as the top card on the Stack is a Will, you may play the Thoughtcutter in Support from hand.
When played this way, the Stack is interrupted and, until it fully resolves, players cannot add cards or effects on the Stack except through cards or effects already present on the Stack or Triggered effects.
When it enters the Confrontation Zone, the Thoughtcutter gets +1 power until the end of the turn for each card currently on the Stack controlled by the opponents.

## Arbitrages confirmés

immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| thoughtcutter-gains-power-per-opposing-stack-card | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

conditional-support, result:thoughtcutter_surge, trigger:enters_field_zone

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
