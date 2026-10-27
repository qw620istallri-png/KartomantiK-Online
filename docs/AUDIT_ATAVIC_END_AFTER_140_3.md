# Marqueurs et choix des Atavic — suite après 140.3

Cette passe locale ajoute 22 méthodes, dont deux parcours réseau, pour cinq
paragraphes sélectionnés d'Atavic Introspection et Atavic Oppression. Les
attentes sont écrites depuis les textes imprimés, indépendamment des valeurs
encodées. Les associations explicites et résultats sont dans
[clauses.json](../reports/systematic-audit/atavic-end-followup/clauses.json).

## Défaut reproduit et corrigé

Atavic Oppression faisait piocher son contrôleur avant de demander à
l'adversaire sa défausse. Si Kanon remplaçait cette pioche, le choix de
remplacement était ensuite écrasé par le choix de défausse.

Le coût de cinq Fatigue reste engagé à la déclaration. À la résolution,
l'adversaire défausse d'abord ; une continuation attachée à son choix demande
ensuite la pioche au contrôleur d'Oppression, avec les remplacements habituels.
La continuation reste valide après le départ de la source. Une réponse invalide
ou rejouée ne fait pas piocher. Une main adverse vide ou Immune n'empêche pas
la pioche restante ; aucun choix de défausse impossible n'est créé.

La preuve historique [before.json](../reports/systematic-audit/atavic-end-followup/before.json)
conserve 20 méthodes exécutées, 18 réussies et deux en échec. Les erreurs de
liaison des helpers de la toute première préparation du banc ont été corrigées
avant ce relevé ; elles ne sont pas présentées comme des défauts du jeu.

## Branches vérifiées

- Une carte bleue/violette jouée sous le contrôle approprié ajoute un marqueur
  à Introspection/Oppression. Deux événements distincts en ajoutent deux ;
  mauvaise couleur, jeu adverse, activation et simple mise sur le champ ne
  comptent pas. Une source cachée ou privée d'effets ne collecte rien ; le
  contrôleur courant est utilisé après changement de contrôle.
- Le seuil de fin de tour est vérifié à neuf, dix et quinze marqueurs, sans
  consommation du stock. Le saut de phase finale ne supprime que les effets
  du joueur concerné. Le refus de l'effet ne déplace aucune carte.
- Introspection n'offre pas une sélection de deux cartes si moins de deux
  sont disponibles. Dans le propre Limbo du contrôleur, les Manifestations,
  Volontés Persistantes et Éphémères, y compris Trap, sont admissibles.
  L'ordre dessus/dessous est choisi dans les deux sens, sans mélange et sans
  changement des cartes déjà dans le Deck. Doublons de sélection, cartes
  injectées, mauvais nombre de cartes et réponses de l'autre joueur sont
  refusés sans mutation. Le départ de la source après ciblage ne supprime pas
  le choix d'ordre à la résolution.
- Oppression permet de défausser zéro, une ou deux cartes à la fin du tour ;
  une main vide ne provoque pas d'offre inutile. L'activation refuse quatre
  Fatigue et en dépense exactement cinq à partir de cinq ou onze, avant les
  réponses. Défausse, pioche et remplacement par Kanon suivent l'ordre corrigé.

## Réseau

Les deux scénarios emploient le protocole réel, avec un client incrémental et
un ancien client : Oppression conserve la défausse après reconnexion, attend
sa confirmation, pioche une fois puis refuse le rejeu ; Introspection conserve
son choix dessus/dessous après reconnexion, refuse un mauvais ordre et place
les deux cartes exactement aux positions choisies. Les détails internes de
continuation ne sont pas envoyés dans le choix sérialisé.

Le pilote automatique est isolé pour ces deux essais. L'événement de fin de
tour d'Introspection est préparé explicitement ; les choix et passes de pile
utilisent les gestionnaires normaux. Les tests de marqueurs isolent certains
événements de jeu de leur déclaration et paiement. Ils ne certifient pas tous
les changements de couleur possibles sur la pile.

## Limites

La première passe ne tranchait pas la portée d'Introspection sur les Limbos
adverses. L'[arbitrage et sa suite dédiée](AUDIT_ATAVIC_LIMBO_AFTER_140_3.md)
autorisent désormais chaque Limbo sans mélange, avec retour au Deck du
propriétaire ; les preuves initiales ci-dessus restent historiques. La sélection de deux copies
identiques et le choix de placement après invalidation partielle des cibles
restent hors de ce lot.

Les autres paragraphes, toutes les interactions du catalogue et les appareils
physiques ne deviennent pas couverts par analogie. Les preuves des publications
140.3 et précédentes conservent leur empreinte historique. Cette nouvelle
correction reste locale, sans commit ni push supplémentaire.

Commande : `python tools/card_atavic_end_audit.py`.
Les régressions finales et leurs empreintes sont conservées dans
[le registre d'exécution](../reports/systematic-audit/atavic-end-followup/EXECUTIONS.md).

Validation finale : **1 431 tests Python réussis**, aucun échec ni test ignoré,
ainsi que quatre suites navigateur et une suite JavaScript du transport. Les
preuves ciblées et générales portent la même empreinte des sources ; les
rapports des publications précédentes restent historiques.
