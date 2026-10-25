# Jodorosk, the Psychomage

Identifiant : `inner-deserts-126`

## Texte de référence

When Jodorosk enters the Confrontation Zone, a target opponent puts the top card of their deck face down in front of them. You declare its type, Temperament, and power/cost value, then the opponent uncovers the card and puts it back on top of the deck. Based on the number of correctly guessed characteristics, apply the corresponding effect:
1 - You gain 10 Points. Look at the top card of your deck, you may put it on the bottom of the deck.
2 - You gain 20 Points. Draw 2 cards.
3 - You gain 30 Points. Uncover the top card of your deck. If it is a Manifestation, Chain it. If it is a Will, put it onto the field. It can be played as if it were in your hand without paying its Tribute cost.

## Arbitrages confirmés

immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| guess-opponent-top-card-characteristics | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

result:guess_top_card, target:player, trigger:enters_field_zone

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
