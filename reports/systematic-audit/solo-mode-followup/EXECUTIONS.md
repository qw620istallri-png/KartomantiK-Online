# Mode Solo bêta 141.9

## Fonctionnement livré

- Une connexion contrôle deux sièges stables, P1 en bas et P2 en haut.
- Les deux Mains et toutes les zones privées sont visibles.
- Les actions transportent un `actingPlayerId` vérifié par le serveur ; une
  partie normale ne peut pas usurper l'autre joueur.
- La Main P2 est interactive, lisible à l'endroit et dispose des contrôles de
  pioche et de deck nécessaires à l'entraînement.
- La priorité, les choix obligatoires et les passes de phase mettent en avant la
  Main concernée sans retourner la table.
- Le même navigateur peut reprendre les deux sièges après reconnexion ; un autre
  navigateur est refusé.

## Validation

- **4 358/4 358 tests Python uniques réussis** en 650,602 secondes.
- Zéro échec, test ignoré ou identifiant dupliqué.
- Frontend général, continuité des choix desktop/mobile, parité des règles
  (**609 scénarios**), régressions 139.2 et parcours Solo desktop/mobile réussis.
- Registre strict courant : **298/450 cartes (66,2 %)**, aucune preuve exclue.

## Limites du premier lot

- Pas d'intelligence artificielle.
- Pas de second navigateur joueur dans une session Solo.
- Le code interne de reconnexion n'est pas présenté comme un code de partage.
