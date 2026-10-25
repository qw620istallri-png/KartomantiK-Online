# Diabolical Giant

Identifiant : `0kcy08a6jd7ez7k_en`

## Texte de référence

Cannot be played as First Manifestation.
If the Diabolical Giant is in hand or in the Interzone, you can lose 10 points: The Diabolical Giant gains Support until the end of the turn.

## Arbitrages confirmés

immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| lose-ten-to-gain-support | pass | pass | pass | pass | pass | pass | not-applicable | not-applicable | pass | not-applicable |

## Parcours UI effectivement exécutés

| Capacité | Résultat | Résolution |
|---|---|---|
| lose-ten-to-gain-support | pass | completed-no-pending-choice |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

first-restriction, result:grant_source_support_until_end_turn

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
