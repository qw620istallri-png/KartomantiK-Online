# Publication bêta 150.1

Empreinte source : voir `unit-tests.json`.

## Résultats

- **4 362/4 362 tests Python** réussis.
- Zéro échec, test ignoré, identifiant dupliqué ou preuve exclue.
- Frontend général, continuité des choix desktop/mobile et **609 scénarios** de
  parité client/serveur réussis.
- **78/78 gestes réels** réussis sur les configurations PC, mobile et mixtes.
- **16/16 configurations** de Pile réussies dans Chrome et WebKit.
- Régressions 139.2, Solo desktop/mobile, clavier/chat, sélecteurs privés,
  Scry mobile, Impasse, Vaisseau et Essences blanches réussies.
- Registre strict : **309/450 cartes (68,7 %)**.

## Ressources

Le client, le service worker et les 24 URL JavaScript/CSS utilisent
`20261103-rules-beta-150-1`, affichée `beta 150.1`.

## Portée

La table actuelle est désormais permanente : aucun bouton, stockage local,
chemin de restauration ou variante de test ne permet de revenir à l'ancienne.
L'import Solo indique le siège ciblé et l'agrandissement des cartes de Main est
recalé dans la fenêtre après rendu.
