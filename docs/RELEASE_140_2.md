# Bêta 140.2 — Priorité, Soutiens et choix de cartes

- Les longues piles continuent de se résoudre après la limite interne de
  traitement, carte par carte. La reprise conserve les choix et fenêtres de
  réponse ; un refus de commande ne lance plus le passage automatique.
- Les commandes retardées contenant une ancienne phase, un ancien tour ou un
  ancien sommet de pile sont refusées avec remise à jour du plateau.
- Les mises en Soutien par effet respectent les interdictions et déclenchent
  les événements correspondant au déplacement réellement effectué. Chiff and
  Chaff ne déclenche son retour que lors de sa propre entrée en Soutien.
- Une carte renvoyée en main avec interdiction de rejouer ne peut plus
  contourner ce verrou par une déclaration sur la pile. La disponibilité pour
  l'auto-skip suit la même règle, en conservant les autres copies jouables.
- Les enchaînements d'Urocione et Dol conservent les destinations et mémoires
  attendues. Lady of the Humps mélange aussi lorsque l'enchaînement échoue ou
  est remplacé par une suspension.
- Hermeto et Recall révèlent les cartes cherchées, visibles en main et dans le
  journal ; le reste du Deck demeure privé. Mejik engage son nom déclaré comme
  coût avant de donner la priorité adverse, et ne le redemande pas à résolution.
  Les instructions et références de cartes sont disponibles en trois langues.

Les audits détaillés et leurs preuves restent séparés par passe dans
[le suivi systématique](SYSTEMATIC_CARD_AUDIT.md). Les preuves précédant cette
publication gardent leur empreinte historique ; la validation de publication
est conservée dans `reports/systematic-audit/release-140-2/`.

Cette version ne certifie pas toutes les branches des 450 cartes. Le défaut
signalé dans la pile sur Safari Mac n'a pas été reproduit sous WebKit Windows
et reste ouvert ; aucun appareil physique n'a été testé.

Version des ressources : `20261026-rules-beta-140-2`, affichée `beta 140.2`.

Validation finale sur ces ressources : **1 388 tests Python et 14 suites UI
réussis**, aucun échec ni test Python ignoré. Les preuves et la vérification des
versions portent une empreinte commune dans
[le registre de publication](../reports/systematic-audit/release-140-2/EXECUTIONS.md).
