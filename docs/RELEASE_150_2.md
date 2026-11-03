# Bêta 150.2 — Hover ancré et cibles joueur

Version des ressources : `20261103-rules-beta-150-2`, affichée `beta 150.2`.

## Main et glisser-déposer

- Une carte agrandie au survol ne remonte plus jusqu'à quitter la souris.
- Le déplacement vertical est plafonné à environ 40 px et le lift visuel passe
  de 10 px à 3 px.
- La carte reste alignée avec sa source pour pouvoir commencer immédiatement
  un glisser-déposer.
- Si nécessaire, le bas de l'agrandissement peut dépasser légèrement de la
  fenêtre plutôt que de déplacer fortement la carte vers le haut.

## Couverture des cartes

- Onze clauses `target:player` sont reliées à des contrats stricts :
  Haltan, Gobres, Suspend Judgment, Shymon, Rogue Tadpole, Tardigramo,
  Rude Exterminator, Ababash, Nullify Reason, Remove by Chance et
  Walk the Oblivion.
- Les tests vérifient la cible joueur unique, les restrictions adversaire, les
  mauvaises catégories de cible, les joueurs absents et l'atomicité des refus.
- Les résultats propres à ces cartes restent explicitement hors de cette preuve
  commune.
- Le registre strict atteint **320/450 cartes (71,1 %)**.

## Validation

- **4 367/4 367 tests Python** réussis, sans échec, test ignoré ou identifiant
  dupliqué.
- Frontend général, interactions de Main, continuité des choix, **609
  scénarios** de parité, Solo desktop/mobile, **78/78 gestes réels** et
  **25 contrôles PWA** réussis.
- Aucune preuve exclue.
