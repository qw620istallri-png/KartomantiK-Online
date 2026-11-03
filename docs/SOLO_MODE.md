# Mode Solo bêta

Le mode Solo est une session d'entraînement à deux sièges contrôlés par une
seule connexion.

## Principes

- P1 reste en bas et P2 en haut ; la table ne pivote jamais.
- Les deux Mains et toutes les zones privées sont visibles.
- La source d'une action détermine le siège agissant. Les commandes sans source
  transmettent explicitement `actingPlayerId`.
- Le serveur n'accepte `actingPlayerId` que pour les deux sièges de la session
  Solo. Une partie normale ne peut pas l'utiliser pour agir à la place de
  l'adversaire.
- En règles assistées, la priorité ou le choix obligatoire met en avant la Main
  correspondante. Avec le suivi manuel des phases, le siège qui n'a pas passé
  est mis en avant.

## Connexion et visibilité

Une session `mode="solo"` crée deux joueurs internes stables et enregistre leur
identifiant dans `solo_player_ids`. La connexion reçoit ces identifiants dans
`controlledPlayerIds`, mais conserve P1 comme identité primaire d'orientation.

La sérialisation Solo donne accès aux Mains, Decks, Exils, sideboards et cartes
face cachée des deux sièges. Le code interne de la session sert uniquement à la
reconnexion du même navigateur ; il n'est pas affiché comme code à partager.

## Interface

- La Home expose **Entraînement solo (bêta)** dans le menu **Modes bêta**.
- La Main P1 réutilise le bac inférieur.
- La Main P2 est une Main interactive supérieure, avec cartes à l'endroit,
  pioche, remplissage de Main et accès à son deck.
- La Main active est légèrement agrandie ; l'autre reste visible mais atténuée.
- Sur mobile paysage, la Main inactive se compacte afin de préserver le plateau.

## Validation

Les tests dédiés couvrent la création, la visibilité des deux zones privées,
l'autorisation d'agir pour chaque siège, le refus d'usurpation dans une partie
normale, la reconnexion, la priorité assistée, les deux Mains fixes et une action
assistée depuis la Main P2.
