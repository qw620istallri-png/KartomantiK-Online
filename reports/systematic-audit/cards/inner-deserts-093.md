# Bizarre Mechanism

Identifiant : `inner-deserts-093`

## Texte de référence

When the Bizarre Mechanism enters the field, put an Enigma counter on it.
You may only activate the effect corresponding to the number of Enigma counters on the Bizarre Mechanism.
1 - Put an Enigma counter on this card: Shuffle your deck.
2 - Put an Enigma counter on this card: Look at the top card of your deck, you may swap it with a card in your hand or put it on the bottom of your deck.
3 - Put a card from your hand on the bottom of your deck: Remove 2 Enigma counters from this card.

## Arbitrages confirmés

immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| mechanism-starts-with-an-enigma | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |
| mechanism-one-shuffle | pass | pass | pass | pass | pass | pass | not-applicable | not-applicable | pass | not-applicable |
| mechanism-two-peek-and-swap | pass | pass | pass | pass | pass | pass | not-applicable | not-applicable | pass | not-applicable |
| mechanism-three-bottom-a-card | pass | pass | pass | pass | pass | pass | not-applicable | not-applicable | pass | not-applicable |

## Parcours UI effectivement exécutés

| Capacité | Résultat | Résolution |
|---|---|---|
| mechanism-one-shuffle | pass | completed-no-pending-choice |
| mechanism-two-peek-and-swap | pass | completed-no-pending-choice |
| mechanism-three-bottom-a-card | pass | completed-no-pending-choice |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

result:add_counter_source, result:bottom_hand_card_remove_counters, result:peek_top_swap, result:shuffle_owner_deck, trigger:enters_field

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
