# Bêta 150.1.3 — Cible d'import Solo verrouillée

Version des ressources : `20261103-rules-beta-150-1-3`, affichée
`beta 150.1.3`.

## Correction

- L'éditeur de deck mémorise explicitement le siège P1 ou P2 qui l'a ouvert.
- Les mises à jour d'activité et les états renvoyés par le serveur ne peuvent
  plus remplacer cette cible pendant que l'éditeur reste ouvert.
- Chaque commande `import_deck` Solo transporte directement l'`actingPlayerId`
  mémorisé.
- Le verrou est libéré uniquement après fermeture ou validation de l'éditeur.

La régression reproduit l'aller-retour d'état qui faisait auparavant importer
le premier deck P2 sur P1, et vérifie que P2 reste ciblé dès la première
tentative.

## Validation

- **4 363/4 363 tests Python** réussis.
- Frontend général, continuité des choix, **609 scénarios** de parité, Solo
  desktop/mobile, cycle de connexion et **25 contrôles PWA** réussis.
- Registre strict inchangé : **309/450 cartes (68,7 %)**, aucune preuve exclue.
