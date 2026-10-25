# Ju Lien, the Provocateur

Identifiant : `qapv47r7rz6gqah_en`

## Texte de référence

When Ju Lien enters the Confrontation Zone, you can put a Will from your hand on the field. That Will becomes a manifestation with {H} power equal to its tribute cost until the Resolution and enters in Support under your control.
If the Will wins the confrontation, it can be played as if it were in your hand without paying its tribute cost, if it loses or enters stalemate instead exile it.

## Arbitrages confirmés

cleanse-animation, immediate

## Capacités et matrice

| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |
|---|---|---|---|---|---|---|---|---|---|---|
| ju-lien-puts-hand-will-in-support | carrier-only | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario | needs-family-scenario |

## Exécutions des modules référencés

Ce nombre concerne le module entier, pas une certification de cette carte.

- `test_card_catalog` : 40 tests réussis.
- `test_game_state` : 482 tests réussis.

## Mécaniques

result:choose_hand_will_as_support_manifestation, trigger:enters_field_zone

## Références de tests (à distinguer des exécutions)

- `tests/test_game_state.py`
- `tests/test_card_catalog.py`

## Limites

- Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.
- Une référence de fichier n'est pas une preuve d'exécution ni du texte entier.
- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.
