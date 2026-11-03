# Publication bêta 150.1.1

Empreinte source : voir `unit-tests.json`.

## Résultats

- **4 363/4 363 tests Python** réussis.
- Zéro échec, test ignoré, identifiant dupliqué ou preuve exclue.
- Frontend général, continuité des choix desktop/mobile et **609 scénarios** de
  parité client/serveur réussis.
- Régressions 139.2, Solo desktop/mobile, clavier/chat et installation PWA
  réussies.
- Registre strict : **309/450 cartes (68,7 %)**.

## Ressources

Le client, le service worker et les 24 URL JavaScript/CSS utilisent
`20261103-rules-beta-150-1-1`, affichée `beta 150.1.1`.

## Portée

Chaque siège Solo dispose de son bouton coloré d'import de deck. Le serveur
valide désormais les deux decks standard en mode Solo et distribue les deux
Mains d'ouverture après validation du second.
