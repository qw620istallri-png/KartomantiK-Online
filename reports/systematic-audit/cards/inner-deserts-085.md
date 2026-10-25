# Fee-fee, the Afflicted

Identifiant : `inner-deserts-085`

## Texte de référence

As long as Fee-fee is in the Stalemate Zone:
  • Its controller cannot put it into the Interzone or to the bottom of the deck by winning a Confrontation.
  • At the beginning of the turn, put 1 Spite counter on Fee-fee. Then pay 🔘 for each Spite counter, otherwise put Fee-fee into the Empathic Vessel of an opponent of your choice.
  • The power of each Manifestation with power equal to or less than the number of Spite counters on Fee-fee is not considered for the resolution of the Confrontation.

## Arbitrages confirmés

immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| fee-fee-spite-upkeep | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |
| fee-fee-cannot-win-out-of-stalemate | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |
| fee-fee-spite-ignores-low-power | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

passive:stalemate_ignores_low_power, passive:stalemate_win_blocked, result:spite_upkeep, trigger:beginning_of_turn

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
