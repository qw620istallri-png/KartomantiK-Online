# Zum, the Manifold

Identifiant : `282b0n6ldnzdp0p_en`

## Texte de référence

As long as Zum is on the field, you can activate each of these effects once per turn and, if in a turn they are all activated, Zum gains Support.
{R}: A target manifestation on the field gets -1 power until the end of the turn;
{Y}️: A target manifestation on the field loses its effects until the end of the turn;
{G}: A target manifestation on the field gets +1 power until the end of the turn;
{B}: A target player draws 1 card;
{P}: A target player discards 1 card from the top of the deck.

## Arbitrages confirmés

immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| zum-weaken | pass | pass | pass | pass | pass | pass | pass | pass | pass | pass |
| zum-silence | pass | pass | pass | pass | pass | pass | pass | pass | pass | pass |
| zum-strengthen | pass | pass | pass | pass | pass | pass | pass | pass | pass | pass |
| zum-draw | pass | pass | pass | pass | pass | pass | pass | not-applicable | pass | pass |
| zum-mill | pass | pass | pass | pass | pass | pass | pass | not-applicable | pass | pass |

## Parcours UI effectivement exécutés

| Capacité | Résultat | Résolution |
|---|---|---|
| zum-weaken | pass | completed-no-pending-choice |
| zum-silence | pass | completed-no-pending-choice |
| zum-strengthen | pass | completed-no-pending-choice |
| zum-draw | pass | completed-no-pending-choice |
| zum-mill | pass | completed-no-pending-choice |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

ongoing:lose_effects, ongoing:power_modifier, result:discard_deck_owner, result:draw_owner, target:player

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
