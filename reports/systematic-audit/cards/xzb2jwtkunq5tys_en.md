# Guart, the Slinger

Identifiant : `xzb2jwtkunq5tys_en`

## Texte de référence

As long as Guart is on the field:
• Whenever the power of a manifestation on the field controlled by an opponent increases, a target manifestation on the field you control gets +1 power until the end of the turn.
• Whenever a manifestation on the field you control loses power due to a card or effect, a target manifestation on the field controlled by an opponent gets -1 power until the end of the turn.

## Arbitrages confirmés

modifier-expiration, immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| guart-answers-opponent-power-gain | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |
| guart-answers-own-power-loss | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

ongoing:power_modifier, trigger:power_gained, trigger:power_lost

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
