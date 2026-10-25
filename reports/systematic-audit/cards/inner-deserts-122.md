# Jeovak, the Illusory

Identifiant : `inner-deserts-122`

## Texte de référence

Support.
Cannot be played as First Manifestation.
Jeovak can only be played while the Stack is empty.
When Jeovak enters the Confrontation Zone, Exile it. Each Manifestation in the Confrontation Zone is moved to its owner's Interzone, up to the maximum limit, or to the bottom of their deck in any order. The Confrontation ends and players skip the Resolution, then each opponent gains 50 Points.

## Arbitrages confirmés

immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| end-confrontation-and-relocate | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

first-restriction, result:end_confrontation_relocate_all, support-from-hand, support-from-interzone, trigger:enters_field_zone

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
