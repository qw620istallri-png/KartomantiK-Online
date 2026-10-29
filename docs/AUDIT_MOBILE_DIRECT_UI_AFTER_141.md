# Dépôt direct et navigateur de pile en deux colonnes

La demande de révision retire le panneau de destinations Interzone/Volontés.
Le glissement vise maintenant les zones réelles du plateau, avec une surbrillance
directe et une tolérance de huit pixels près de leur bord. Les anciens éléments,
styles, libellés et point d'entrée de ce panneau ont été retirés.

En mode manuel tactile, un dépôt rapide sur une carte déjà présente dans
l'Interzone ou les Volontés choisit un emplacement libre de cette zone, sans
superposition automatique. Rester environ une demi-seconde sur la carte visée
arme une superposition volontaire : un contour et un libellé l'indiquent.
Bouger de plus de huit pixels ou changer de carte réinitialise cette intention.
Les superpositions à la souris et le parcours des règles automatisées conservent
leur comportement. La Zone de Confrontation garde son comportement de dépôt.
La fin du geste, son annulation et les réinitialisations nettoient le retour
visuel et les minuteries.

## Deck / Mazzo

Le navigateur de pile utilise désormais deux colonnes : les commandes à gauche,
les cartes à droite. Confirmer et Fermer restent accessibles en bas de la colonne
de gauche ; le titre, filtre, aide et réglage de taille ont leur propre défilement
si nécessaire. Les cartes défilent indépendamment sur toute la hauteur à droite.

Sur tactile, les cartes de la pile servent au défilement. Elles ne commencent
plus un glissement de carte pendant un balayage. Un appui long utilise le
gestionnaire existant pour ouvrir leurs options ; un déplacement de plus de
dix pixels annule cet appui long. Un tap simple ouvre l'inspection, placée
au-dessus de la recherche, avec sa croix accessible. Les options ne s'exécutent
pas au relâchement de l'appui long. Le clic et le glissement souris existants
restent disponibles. Cliquer dans un espace vide de la liste ne ferme plus la
recherche ; son fond extérieur et Fermer la ferment.

Le filtre, les sélections en attente et leur confirmation sont conservés. Les
libellés et l'aide sont traduits en français, anglais et italien.

## Preuves

`node tests/test_mobile_manual_ui.cjs` exécute **168 contrôles réussis**, sur
844 × 390 et 640 × 288 avec tactile émulé puis 1440 × 1000 avec souris,
dans les trois langues et depuis les deux places :

- 48 dépôts rapides depuis la Main et le plateau dans Interzone/Volontés ;
- 24 superpositions après maintien depuis le plateau et 12 annulations ;
- 18 parcours de recherche avec filtrage, sélection, conservation d'une
  sélection masquée, confirmation et réouverture ; les douze variantes tactiles
  font réellement défiler la liste puis ouvrent les options par appui long ;
- 12 inspections par tap puis fermeture par la croix visible ;
- 18 vérifications du résolveur selon le type d'entrée, 18 vérifications des
  modes règles/observateur et 18 vérifications d'absence d'erreurs JavaScript.

Les **96 contrôles de débordement** passent également sur la disposition en
deux colonnes. Les suites frontend et nettoyage des glissements réussissent.
Les 264 identifiants de contrôles d'interface sont distincts. Les preuves,
empreintes, sorties et captures se trouvent dans
`reports/systematic-audit/mobile-direct-ui-followup/`.

La passe intermédiaire conserve 168 contrôles avec 24 échecs : le test utilisait
l'ancien bouton d'inspection masqué au lieu de la croix visible, puis laissait
l'inspection ouverte pour les douze cas suivants. Le banc isole maintenant ces
préparations et ferme par la vraie commande tactile. L'inspection est aussi
placée au-dessus de la fenêtre de recherche en production. Le banc de survol
souris est réinitialisé explicitement après les gestes tactiles : aucun faux
survol n'est attendu sur tactile.

## Limites

Les gestes natifs utilisent Chrome en émulation, avec images locales et messages
interceptés. Les vérifications du résolveur sur le DOM ne prétendent pas être des
gestes natifs supplémentaires. Les règles serveur, appareils physiques, clavier
logiciel réel, Safari et Samsung Internet ne sont pas nouvellement certifiés.
Les rapports précédents des panneaux de dépôt restent des preuves historiques
de l'itération remplacée. Aucun changement de version, commit ou push.
