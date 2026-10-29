# Destructions ciblées et suites conditionnelles

Le lot couvre des clauses sélectionnées de huit cartes : Disfigure, Knobbly
Colossus, Borombo, Deviate, Repress the Self, Convert the Pain, Multicastigate
et l'effet d'entrée de Lilitha. Les attentes relues depuis le catalogue sont
conservées dans `audit/targeted-destruction.json`, avec les textes et empreintes.
Les cibles synthétiques valent explicitement 20 points et ont 4 de puissance ;
les valeurs attendues ne sont pas calculées depuis le résultat du moteur.

Trois défauts sont reproduits puis corrigés :

- Convert the Pain faisait piocher pour une destruction remplacée par un exil.
  Seules les destructions effectives comptent désormais pour ses pioches, y
  compris quand une autre cible reste valide ou appartient à un autre joueur.
- Lilitha créait ses jetons lorsque la cible était exilée au lieu d'être détruite.
  Sa condition « If you do » exige maintenant une destruction effective. La
  destruction d'un jeton reste possible et le nombre créé utilise la puissance
  de base, sans y ajouter un bonus de puissance.
- Repress the Self ne donnait pas les points après suspension par BOB. Le
  créateur confirme que son gain indépendant reste applicable après suspension
  ou exil. La décision `repress-independent-points` est conservée dans
  `audit/rule-decisions.json`. Elle ne remplace pas les conditions de phase ou de
  ciblage imprimées dans le catalogue par une formulation différente.

Le correctif distingue une arrivée réelle au Limbo d'un déplacement ayant
réussi vers l'Exil. Il conserve la destruction des jetons qui disparaissent en
quittant le champ. Les autres instructions indépendantes ne sont pas assimilées
aux instructions conditionnées par « détruite de cette manière ».

## Preuves exécutées

Les **126 méthodes unitaires** et **9 parcours WebSocket** réussissent, sans test
ignoré. Chaque carte possède ses propres identifiants de test. Selon le texte,
les cas vérifient : déclaration et paiement réels des Volontés, résolution
différée, Protection/Immunité, cible partie ou passée en Impasse, changement de
type ou de contrôle, propriétaire différent du contrôleur, Adamant, départ de
la source déclenchée, mauvais événement et refus d'un effet optionnel.

Les cas particuliers comprennent le seuil de Disfigure à 20/21 points et ses
cibles dans les deux Vaisseaux, les Volontés Éphémères et Persistantes visées
par Knobbly, les conditions de phase et de résultat de Deviate/Repress, zéro à
deux cibles pour Convert, les pioches exactes par contrôleur, les jetons et les
2 ou 5 essences payées pour une ou deux cibles de Multicastigate. Une cible
invalide n'empêche pas la destruction de l'autre cible indépendante.

Les parcours réseau jouent les cinq Volontés par le protocole réel. Convert
possède aussi un parcours de résolution partielle après reconnexion et un
parcours d'exil remplacé. Repress possède les parcours de suspension et d'exil.
Un client reçoit les mises à jour incrémentales, l'autre les états complets.
Le pilote automatique de phases est isolé.

Les preuves sont dans `reports/systematic-audit/targeted-destruction-followup/` :

- `before.json` : 101 réussites et un échec Convert sur 102 méthodes ;
- `sibling-before.json` : 123 réussites et un échec Lilitha sur 124 méthodes,
  après correction de Convert ;
- `repress-before.json` : 125 réussites et un échec Repress sur 126 méthodes,
  après l'arbitrage et les deux premières corrections ;
- `clauses.json` : 135 méthodes réussies, liées à 12 paragraphes sélectionnés.

Les erreurs de préparation initiales du banc — décompte d'une carte renvoyée en
Main, nom de couleur, propriété singulière de tempérament et autre capacité de
Lilitha sur un autre événement — ont été corrigées avant les reproductions
conservées ci-dessus. Une exécution intermédiaire a également refusé de produire
une preuve après modification de format du registre de règles pendant son
exécution ; les tests ont été réexécutés une fois les sources figées.

## Limites

La régression complète exécute **3 083 méthodes Python distinctes**, toutes
réussies, sans test ignoré. Son empreinte correspond à celle du lot. Le compteur
strict actualisé atteint **129/450 cartes (28,7 %)** : sept nouvelles cartes,
Multicastigate étant déjà dans le registre. Il s'agit d'au moins une clause
sélectionnée par carte ; 321 cartes restent hors de ce registre et aucune
certification exhaustive de toutes les branches n'est annoncée.

Les cibles, résultats de confrontation et états résolus de BOB/Nullify sont des
préparations contrôlées. Les déclenchements utilisent la file de production,
sans prétendre qu'une partie entière a produit chaque événement. Les autres
capacités de Lilitha restent hors de ce lot. Drildrill n'est pas ajouté au compteur
par simple ressemblance de son texte.

Cette preuve ne certifie pas toutes les branches de ces cartes, les navigateurs,
les appareils physiques ou le pilote automatique. Aucun changement de version,
commit ou push n'est effectué pour ce lot.
