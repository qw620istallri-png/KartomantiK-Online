# Passe de réordonnancement du dessus des Decks

- **4 401/4 401 tests Python** réussis.
- Zéro échec, test ignoré, identifiant dupliqué ou preuve exclue.
- **4/4 contrats ciblés** réussis pour cinq cartes et cinq paragraphes
  imprimés `result:reorder_top_decks`.
- Shababba ne se déclenche qu'à la fin du tour depuis l'Interzone et applique
  réellement l'ordre choisi aux quatre cartes inspectées.
- Dissect inspecte les trois premières cartes de chaque Deck et refuse sans
  mutation une réponse qui n'ordonne pas exactement tous les groupes.
- Tut dépense réellement une Essence Creuse et impose deux cartes au-dessus et
  une au fond lorsque trois cartes sont disponibles.
- Glimpse the Omens pioche la nouvelle première carte après le réordonnancement.
- Eviscerate Morality défausse les deux nouvelles premières cartes après le
  réordonnancement.
- Aucun défaut de code ou de donnée n'a été découvert dans ce lot.
- Registre strict : **375/450 cartes (83,3 %)**.
- Lacunes restantes : **75 cartes, 109 paragraphes et 339 oracles**.

La suite complète est enregistrée dans `unit-tests.json` et la preuve des cinq
paragraphes dans `clauses.json`. Cette passe ne recertifie pas les familles
génériques de confidentialité, reconnexion ou remplacement de pioche et de
défausse déjà couvertes ailleurs.
