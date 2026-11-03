# Bêta 150.1 — Table permanente et import Solo explicite

Version des ressources : `20261103-rules-beta-150-1`, affichée `beta 150.1`.

## Interface

- La nouvelle table devient l'unique interface de jeu.
- Les interrupteurs de la Home et du menu de partie, leur préférence locale et
  les chemins de restauration de l'ancienne table sont supprimés.
- Le sélecteur de thème reste disponible dans le menu de partie.
- Les commandes de profondeur propres à l'ancien plateau ne sont plus proposées.

## Mode Solo

- L'éditeur de deck affiche clairement le siège concerné, avec sa couleur :
  `Deck du joueur P1` ou `Deck du joueur P2`.
- Si le siège porte un nom personnalisé différent de P1/P2, ce nom est ajouté
  au repère.

## Robustesse

- L'agrandissement d'une carte de Main est recalé après rendu pour rester
  entièrement dans la fenêtre, y compris avec les transformations de rareté.
- Les régressions frontend sont alignées sur la table permanente ; aucune
  compatibilité avec l'ancien basculement n'est réintroduite.

## Validation

- **4 362/4 362 tests Python** réussis, sans échec, test ignoré ou identifiant
  dupliqué.
- **78/78 gestes réels** de déplacement réussis sur PC, mobile et vue mixte.
- **16/16 configurations** de Pile réussies dans Chrome et WebKit.
- Frontend général, continuité des choix, **609 scénarios** de parité,
  régressions 139.2, Solo desktop/mobile, accessibilité clavier et installation
  PWA réussis.
- Registre strict inchangé : **309/450 cartes (68,7 %)**, aucune preuve exclue.
