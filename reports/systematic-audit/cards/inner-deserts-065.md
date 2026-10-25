# Jesterina, the Decadent

Identifiant : `inner-deserts-065`

## Texte de référence

Support from hand.
Cannot be played as First Manifestation.
When Jesterina enters the Confrontation Zone, a target opponent uncovers and discards cards from the top of their deck until they uncover a Manifestation. Chain that Manifestation under your control.
When Jesterina wins a Confrontation, exile it.

## Arbitrages confirmés

immediate, jesterina-direct-chain

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| jesterina-chains-opponent-manifestation | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |
| jesterina-exiles-after-win | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

first-restriction, result:chain_discarded_manifestation_from_target_deck, result:move_source_to_owner_exile, support-from-hand, target:player, trigger:enters_field_zone, trigger:wins_confrontation

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
