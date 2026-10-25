# Nghoul-ong, the Tormented

Identifiant : `inner-deserts-055`

## Texte de référence

If Nghoul-ong is discarded, you may exile it. If you do, you may play a target Ephemeral Will from your Limbo with a cost equal to or less than Nghoul-ong's base power without paying its Tribute cost until the end of the turn. If that Will would leave the Stack, exile it.

## Arbitrages confirmés

immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| nghoulong-exiles-itself-for-a-free-limbo-ephemeral-will | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

result:exile_source_grant_limbo_will_play, target:zone_card, trigger:discarded

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
