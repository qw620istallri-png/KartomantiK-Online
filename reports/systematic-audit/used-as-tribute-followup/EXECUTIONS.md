# Passe du Tribut utilisé

- **4 389/4 389 tests Python** réussis.
- Zéro échec, test ignoré, identifiant dupliqué ou preuve exclue.
- **4/4 contrats ciblés** réussis pour six cartes
  `trigger:used_as_tribute`.
- Paiement réel d'un Will, déplacement au Cimetière et déclenchement unique
  vérifiés pour chaque carte.
- Une simple défausse ne compte pas comme Tribut et payer une activation de
  Will ne crée pas les mémoires réservées au jeu d'un Will.
- La première transition propre à chaque carte est exécutée : création de la
  mémoire attachée correcte, mélange du deck propriétaire ou lancer de dé et
  gain d'Essence transcendante conservée.
- Aucun défaut de code ou de donnée n'a été découvert dans ce lot.
- Registre strict : **358/450 cartes (79,6 %)**.
- Lacunes restantes : **92 cartes, 128 paragraphes et 396 oracles**.

La suite complète est enregistrée dans `unit-tests.json` et la preuve de clauses
dans `clauses.json`. La résolution ultérieure des mémoires reste reliée à ses
familles dédiées.
