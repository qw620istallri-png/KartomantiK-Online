# Empathic Mask

Identifiant : `1ixfmjkfewc0o42_en`

## Texte de référence

Pay {H}: A target manifestation on the field becomes of a base temperament of your choice until the end of the turn.

## Arbitrages confirmés

immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| mask-becomes-choleric | pass | pass | pass | pass | pass | pass | pass | pass | pass | pass |
| mask-becomes-vitreous | pass | pass | pass | pass | pass | pass | pass | pass | pass | pass |
| mask-becomes-phlegmatic | pass | pass | pass | pass | pass | pass | pass | pass | pass | pass |
| mask-becomes-capricious | pass | pass | pass | pass | pass | pass | pass | pass | pass | pass |
| mask-becomes-melancholic | pass | pass | pass | pass | pass | pass | pass | pass | pass | pass |

## Parcours UI effectivement exécutés

| Capacité | Résultat | Résolution |
|---|---|---|
| mask-becomes-choleric | pass | completed-no-pending-choice |
| mask-becomes-vitreous | pass | completed-no-pending-choice |
| mask-becomes-phlegmatic | pass | completed-no-pending-choice |
| mask-becomes-capricious | pass | completed-no-pending-choice |
| mask-becomes-melancholic | pass | completed-no-pending-choice |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

cost:tribute, ongoing:temperament_override

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
