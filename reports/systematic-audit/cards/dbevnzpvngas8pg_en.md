# Jondo, the Pure Heart

Identifiant : `dbevnzpvngas8pg_en`

## Texte de référence

As long as Jondo is in the Interzone, if upon Revelation its base power is higher than the base power of the First Manifestation you control, Jondo has Support until the end of the turn.
When Jondo wins a confrontation as Support, exile it.

## Arbitrages confirmés

immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| gain-support-when-stronger-than-own-first | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_game_state` : 482 tests réussis.

## Mécaniques

result:grant_source_support_if_base_higher_than_own_first, support-win:exile, trigger:revelation

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
