# Bêta 140.31 — Séquences et ciblage des Atavic

- Atavic Oppression fait défausser l'adversaire avant la pioche de son
  contrôleur. Le remplacement de pioche de Kanon reste proposé après la
  défausse ; son choix n'est plus écrasé.
- Atavic Introspection permet de choisir deux cartes dans son propre Limbo ou
  dans celui de l'adversaire, sans mélanger les deux. L'ordre dessus/dessous
  est choisi par le contrôleur de l'effet ; les cartes rejoignent le Deck de
  leur propriétaire d'origine.
- L'écran de répartition indique explicitement le Limbo source et le Deck
  concerné, dans les trois langues. La traduction française de la carte ne
  limite plus à tort la sélection à « vos Limbes ».

Les [tests de séquence](AUDIT_ATAVIC_END_AFTER_140_3.md) et
[l'arbitrage des Limbos](AUDIT_ATAVIC_LIMBO_AFTER_140_3.md) documentent les
branches, seuils, refus atomiques, propriétaires et reconnexions vérifiés.
Les sélections de copies identiques et le placement après invalidation partielle
restent hors de ces lots ; ils ne certifient pas toutes les branches du catalogue.

Les preuves avant publication conservent leurs empreintes historiques. La
validation de publication est séparée dans
`reports/systematic-audit/release-140-31/`.

Version des ressources : `20261027-rules-beta-140-31`, affichée `beta 140.31`.

Validation finale : **1 440 tests Python**, six suites navigateur et une suite
JavaScript du transport réussis, aucun échec ni test Python ignoré. Les preuves
portent une empreinte commune dans
[le registre de publication](../reports/systematic-audit/release-140-31/EXECUTIONS.md).
