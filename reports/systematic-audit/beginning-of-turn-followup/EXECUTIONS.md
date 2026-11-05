# Passe des débuts de tour

- **4 376/4 376 tests Python** réussis.
- Zéro échec, test ignoré, identifiant dupliqué ou preuve exclue.
- **4/4 contrats ciblés** réussis pour huit cartes
  `trigger:beginning_of_turn`.
- Zone exacte, visibilité, Réceptacle adverse, seuil de compteurs et unicité
  par tour vérifiés.
- La première transition propre à chacune des huit cartes est exécutée :
  paiement, choix, essence, compteurs ou effet continu selon le texte imprimé.
- Le contrat de **Red Plague** exige désormais explicitement le Réceptacle
  d'un adversaire, conformément à sa carte.
- Registre strict : **339/450 cartes (75,3 %)**.
- Lacunes restantes : **111 cartes, 154 paragraphes et 459 oracles**.

La suite complète est enregistrée dans `unit-tests.json` et la preuve de clauses
dans `clauses.json`. Les branches situées après la première transition restent
à relier à leurs familles dédiées.
