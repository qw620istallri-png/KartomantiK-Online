# Passe des déclenchements de Manifestation utilisée comme Tribut

- **4 493/4 493 tests Python** réussis en 722,049 secondes.
- Zéro échec, test ignoré, identifiant dupliqué ou preuve exclue.
- **7/7 contrats ciblés** réussis pour deux cartes et deux paragraphes
  sélectionnés.
- Melancholic Mirror ne propose son déclenchement optionnel que lorsqu'il est
  actif, prêt et que son contrôleur utilise une Manifestation comme Tribut.
  Refuser ne change rien ; accepter épuise le Mirror et crée exactement une
  copie-token de la Manifestation en Soutien sous le contrôle de ce joueur.
- Sacred Mountain observe les Tributs de tous les joueurs, exile la
  Manifestation depuis le Limbo de son propriétaire immuable puis donne 5
  Points à chaque joueur autre que celui qui a payé le Tribut.
- Deux défauts de production ont été corrigés : un Mirror déjà épuisé
  proposait encore un choix impossible, et Sacred Mountain perdait le
  propriétaire immuable lorsqu'un autre joueur contrôlait la Manifestation
  payée.
- Registre strict : **407/450 cartes (90,4 %)**.
- Lacunes restantes : **43 cartes, 65 paragraphes et 209 oracles**.

La suite complète est enregistrée dans `unit-tests.json` et la preuve des deux
paragraphes sélectionnés dans `clauses.json`.
