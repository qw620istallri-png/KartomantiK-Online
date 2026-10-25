# Powerful Pidue

Identifiant : `inner-deserts-129`

## Texte de référence

As long as Powerful Pidue is on the field, when an opponent plays a Manifestation in Support or a Will from their hand during the Confrontation Phase:
If 🔥, a target Manifestation on the field gets -1 power until the end of the turn.
If ⚡, a target Manifestation on the field loses its current effects until the end of the turn.
If 🌿, put a Token with 1 🌿 power in Support under your control.
If 💧, draw 1 card.
If 🔮, a target player Discards 1 card from their hand.

## Arbitrages confirmés

immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| pidue-choleric-weakens | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |
| pidue-capricious-silences | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |
| pidue-phlegmatic-token | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |
| pidue-vitreous-draws | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |
| pidue-melancholic-discards | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

ongoing:lose_effects, ongoing:power_modifier, result:create_support_token, result:discard_hand_target, result:draw_owner, target:player, trigger:card_played

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
