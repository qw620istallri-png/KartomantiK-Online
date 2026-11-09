# Passe des déclenchements de défaite d'un joueur

- **4 500/4 500 tests Python** réussis en 705,729 secondes.
- Zéro échec, test ignoré, identifiant dupliqué ou preuve exclue.
- **7/7 contrats ciblés** réussis pour deux cartes et trois paragraphes
  sélectionnés.
- Grudge Weaver reçoit exactement un marqueur Grudge lorsque son contrôleur
  courant perd une confrontation, uniquement tant qu'il est actif dans
  l'Interzone. Une victoire, une égalité, une autre zone, une source inactive
  ou la défaite d'un autre joueur ne produit rien.
- Retirer exactement deux marqueurs Grudge pendant la Réaction donne Support à
  cette occurrence jusqu'à la fin du tour. L'activation est légale depuis
  toute zone active du champ et un nombre insuffisant de marqueurs est refusé
  sans mutation.
- Zborh actif dans l'Interzone suit lui aussi son contrôleur courant. Lorsque
  celui-ci perd, la même occurrence retourne à la main de son propriétaire
  immuable, y compris après un changement de contrôle.
- Aucun nouveau défaut de code ou de donnée n'a été découvert dans ce lot.
- Le paragraphe séparé `Adamant` de Zborh reste hors de cette preuve ciblée.
- Registre strict : **409/450 cartes (90,9 %)**.
- Lacunes restantes : **41 cartes, 61 paragraphes et 201 oracles**.

La suite complète est enregistrée dans `unit-tests.json` et la preuve des trois
paragraphes sélectionnés dans `clauses.json`.
