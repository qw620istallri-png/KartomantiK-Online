# Passe des restrictions de Première Manifestation

- **4 430/4 430 tests Python** réussis en 709,832 s.
- Zéro échec, test ignoré, identifiant dupliqué ou preuve exclue.
- **6/6 contrats ciblés** réussis pour deux cartes et quatre paragraphes
  imprimés.
- Diabolical Giant et Brioski, the Aerial sont refusés atomiquement comme
  Première Manifestation sans rendre les autres cartes de la Main
  injouables.
- Diabolical Giant paie exactement 10 points depuis la Main ou l'Interzone,
  une seule fois, puis peut réellement entrer en Soutien jusqu'à la fin du
  tour.
- Une activation du Géant depuis une mauvaise zone ou hors Réaction est
  refusée sans paiement ni action résiduelle.
- Brioski entre réellement en Soutien depuis la Main et l'Interzone ; sa
  Flottaison lui permet de partager un emplacement d'Interzone occupé au
  nettoyage de la Confrontation.
- Le lot a révélé puis corrigé un défaut du validateur d'action : les résultats
  qui accordent temporairement le Soutien étaient bien considérés comme
  inutilisables hors Réaction par l'auto-passage, mais une déclaration directe
  pouvait encore les activer et payer leur coût.
- Registre strict : **389/450 cartes (86,4 %)**.
- Lacunes restantes : **61 cartes, 84 paragraphes et 255 oracles**.

La suite complète est enregistrée dans `unit-tests.json` et la preuve des
quatre paragraphes dans `clauses.json`.
