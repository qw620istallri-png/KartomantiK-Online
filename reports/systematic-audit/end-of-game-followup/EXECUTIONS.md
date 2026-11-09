# Passe des effets de fin de partie

- **4 471/4 471 tests Python** réussis en 714,396 s.
- Zéro échec, test ignoré, identifiant dupliqué ou preuve exclue.
- **7/7 contrats ciblés** réussis pour deux cartes et deux paragraphes
  imprimés.
- Phimosino donne exactement 50 Points de fin de partie au propriétaire dont
  le Deck le contient. Il ne donne rien depuis la Main, les Limbes, l'Exil ou
  le Réceptacle, et son bonus s'ajoute normalement aux autres composantes du
  score final.
- Piercing Lover pénalise uniquement le joueur dont le Réceptacle Empathique
  adverse le contient. Ce joueur perd exactement 5 Points par Manifestation
  de puissance de base inférieure ou égale à 2 dans ce Réceptacle, quelle que
  soit leur propriété ; les Volontés et les puissances supérieures sont
  exclues.
- Unreachable Pillar neutralise correctement la pénalité tant qu'il retire
  les effets du Réceptacle concerné, puis celle-ci revient lorsque le Pillar
  perd ses effets.
- Aucun nouveau défaut de code ou de donnée n'a été découvert dans ce lot.
- Registre strict : **401/450 cartes (89,1 %)**.
- Lacunes restantes : **49 cartes, 72 paragraphes et 230 oracles**.

La suite complète est enregistrée dans `unit-tests.json` et la preuve des deux
paragraphes dans `clauses.json`.
