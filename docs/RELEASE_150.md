# Bêta 150 — Entraînement Solo et couverture des règles

Version des ressources : `20261103-rules-beta-150`, affichée `beta 150`.

## Mode Solo

- Une connexion contrôle P1 en bas et P2 en haut sans retourner la table.
- Les deux Mains et toutes les zones privées restent visibles et interactives.
- Le serveur vérifie le siège agissant pour chaque action, choix et passage de
  priorité ; une partie normale ne peut pas usurper l'adversaire.
- L'encart P2 regroupe la pioche d'une carte, le complément de Main et l'édition
  du second deck.
- La reconnexion restaure les deux sièges uniquement dans le navigateur
  créateur.

## Règles et couverture

- En mode manuel, les points de Confrontation suivent désormais le côté
  physique de la table afin de permettre les changements de propriétaire.
- Treize clauses d'entrée sur le terrain et onze clauses de Tempérament
  alternatif pendant le Tribut disposent de preuves reproductibles dédiées.
- Le registre strict atteint **309/450 cartes (68,7 %)** ; ce nombre certifie
  au moins une clause sélectionnée par carte, pas l'intégralité du catalogue.

## Validation

- **4 362/4 362 tests Python** sans échec, test ignoré ou identifiant
  dupliqué.
- Régressions frontend, choix desktop/mobile, parité client/serveur, version
  139.2 et parcours Solo desktop/mobile.
- Versions de l'application, du service worker et des 24 ressources JS/CSS
  synchronisées.
