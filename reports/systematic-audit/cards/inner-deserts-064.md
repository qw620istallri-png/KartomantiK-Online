# Kanon, the Deathdealer

Identifiant : `inner-deserts-064`

## Texte de référence

Adamant.
As long as Kanon is on the field, whenever an opponent would draw cards outside of the Recovery Phase, they choose half of them rounded up instead. That player discards the chosen cards, then draws the rest.
For each Will discarded this way, a target Manifestation on the field controlled by an opponent gets -1 power.

## Arbitrages confirmés

permanent-modifiers, immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| replace-opponent-nonrecovery-draw | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

adamant, passive:replace_opponent_nonrecovery_draw

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
