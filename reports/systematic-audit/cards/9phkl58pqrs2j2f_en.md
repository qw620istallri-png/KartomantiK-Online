# Greed Trap

Identifiant : `9phkl58pqrs2j2f_en`

## Texte de référence

If a manifestation on the field controlled by an opponent reaches exactly 0 power, it is not destroyed but enters your Empathic Vessel.
Whenever an opponent plays a Will, you can choose a target manifestation in the Confrontation Zone controlled by that opponent and roll a D6.
1-2: Nothing happens.
3-4: The manifestation gets -1 power.
5-6: The manifestation gets -2 power.

## Arbitrages confirmés

immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| capture-opponent-manifestation-at-exact-zero | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |
| roll-against-opponent-will | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

passive:capture_opponent_exact_zero, result:roll_d6_target_table, trigger:will_played

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
