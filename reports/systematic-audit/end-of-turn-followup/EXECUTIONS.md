# Passe de fin de tour

- **4 418/4 418 tests Python** réussis.
- Zéro échec, test ignoré, identifiant dupliqué ou preuve exclue.
- **6/6 contrats ciblés** réussis pour trois cartes et cinq paragraphes
  imprimés.
- Ergorath autorise son contrôleur à jouer une Will depuis son Limbo pour une
  Essence creuse, puis remplace par l'Exil toute destination vers un Limbo,
  une Main ou un Deck, pour les Wills éphémères comme persistantes.
- Sa capacité de fin de tour ne part que depuis l'Interzone active : elle fait
  perdre dix points au contrôleur courant, puis mélange Ergorath dans le Deck
  de son propriétaire.
- Grimoire propose uniquement en fin de tour et depuis le Champ de placer les
  Wills de la Main ; elles restent jouables comme en Main et sont exilées si
  Grimoire quitte le Champ.
- Tax of the Malignant applique le même contrat à la Résolution et à la fin du
  tour : chaque joueur perd toute Essence excédentaire, ou cinq points s'il
  n'en possède aucune.
- Les sources absentes, cachées, désactivées, mal placées ou concernées par
  une fin de tour sautée ne déclenchent pas leur capacité.
- Aucun nouveau défaut de code ou de donnée n'a été découvert dans ce lot.
- Registre strict : **384/450 cartes (85,3 %)**.
- Lacunes restantes : **66 cartes, 96 paragraphes et 287 oracles**.

La suite complète est enregistrée dans `unit-tests.json` et la preuve des cinq
paragraphes dans `clauses.json`. Cette passe ne recertifie pas les autres
capacités de fin de tour déjà attribuées à des familles antérieures ni les
branches génériques de paiement, de déplacement ou de résolution.
