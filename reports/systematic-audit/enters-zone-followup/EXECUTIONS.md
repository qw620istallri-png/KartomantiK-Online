# Passe des déclenchements d'entrée en Réceptacle

- **4 486/4 486 tests Python** réussis en 720,979 secondes.
- Zéro échec, test ignoré, identifiant dupliqué ou preuve exclue.
- **7/7 contrats ciblés** réussis pour deux cartes et deux paragraphes
  sélectionnés.
- Inspired Nimbus ne se déclenche qu'en entrant dans le Réceptacle Empathique
  adverse. Son propriétaire immuable reçoit alors, pour le tour courant, une
  permission consommable une seule fois de jouer gratuitement une Volonté
  depuis sa Main. Le joueur du Réceptacle ne reçoit rien et la permission ne
  survit pas au changement de tour.
- Worm Bomb ne se déclenche lui aussi que dans le Réceptacle adverse. Il y
  détruit aléatoirement jusqu'à trois autres Manifestations, sans se compter
  lui-même ni compter les Volontés. S'il y en a moins de trois, elles sont
  toutes détruites et rejoignent le Limbo de leurs propriétaires immuables.
- Unreachable Pillar neutralise correctement les deux effets tant qu'il retire
  les effets du Réceptacle.
- Aucun nouveau défaut de code ou de donnée n'a été découvert dans ce lot.
- Registre strict : **405/450 cartes (90,0 %)**.
- Lacunes restantes : **45 cartes, 67 paragraphes et 215 oracles**.

La suite complète est enregistrée dans `unit-tests.json` et la preuve des deux
paragraphes sélectionnés dans `clauses.json`.
