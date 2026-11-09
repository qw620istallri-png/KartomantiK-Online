# Passe des déclenchements d'entrée en Soutien

- **4 479/4 479 tests Python** réussis.
- Zéro échec, test ignoré, identifiant dupliqué ou preuve exclue.
- **8/8 contrats ciblés** réussis pour deux cartes et deux paragraphes
  sélectionnés.
- Tant qu'une Gomeran active est dans la Zone de Confrontation de son
  contrôleur, l'entrée en Soutien d'une Manifestation non-token sous ce même
  contrôle crée exactement une copie-token de cette carte en Soutien. Une
  entrée adverse ou token ne déclenche rien, et la copie créée ne relance pas
  Gomeran.
- Unruly Flail n'est jouable depuis la Main en Soutien que si une Volonté
  adverse présente n'importe où dans la Pile vise actuellement une
  Manifestation de la Zone de Confrontation. Comme toute Manifestation, Flail
  entre sans Tribut ; son entrée propre depuis la Main neutralise exactement
  la Volonté adverse éligible choisie.
- Aucun nouveau défaut de code ou de donnée n'a été découvert dans ce lot.
- Le second paragraphe de Gomeran, consacré au mélange après placement sous le
  Deck, reste hors de cette preuve mécanique ciblée.
- Registre strict : **403/450 cartes (89,6 %)**.
- Lacunes restantes : **47 cartes, 69 paragraphes et 221 oracles**.

La suite complète est enregistrée dans `unit-tests.json` et la preuve des deux
paragraphes sélectionnés dans `clauses.json`.
