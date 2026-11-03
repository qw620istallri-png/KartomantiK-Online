# Bêta 150.1.1 — Import des deux decks Solo

Version des ressources : `20261103-rules-beta-150-1-1`, affichée
`beta 150.1.1`.

## Préparation Solo

- Chaque encart P1/P2 possède son propre bouton **Importer un deck**.
- Chaque bouton reprend la couleur du siège qu'il contrôle.
- Le bouton ouvre l'éditeur dans le contexte exact de son joueur ; le libellé
  de l'éditeur confirme également P1 ou P2.
- Une fois un deck choisi, le bouton devient **Modifier le deck**.
- Le bouton générique ambigu sous les deux joueurs est masqué en Solo.

## Correction serveur

- La validation standard des decks accepte maintenant les sessions `solo` en
  plus des sessions `casual`.
- Le second deck peut être importé et validé avec `actingPlayerId=P2`.
- La validation du deuxième deck distribue ensuite les deux Mains d'ouverture.

## Validation

- **4 363/4 363 tests Python** réussis, sans échec, test ignoré ou identifiant
  dupliqué.
- Frontend général, continuité des choix, **609 scénarios** de parité,
  régressions 139.2, Solo desktop/mobile, clavier/chat et installation PWA
  réussis.
- Registre strict inchangé : **309/450 cartes (68,7 %)**, aucune preuve exclue.
