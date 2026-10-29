# Mode manuel tactile : destinations et recherche du Deck

Rapport historique de l'itération avec panneau de destinations, remplacée à la
demande du créateur. Le comportement courant est décrit dans
[l'audit du dépôt direct](AUDIT_MOBILE_DIRECT_UI_AFTER_141.md). Le script de test
actuel écrit ses nouvelles preuves dans `mobile-direct-ui-followup/`.

Une carte relâchée sur une autre carte est normalement superposée à celle-ci.
Sur les colonnes étroites Interzone/Volontés, ce geste rendait difficile une
simple mise en place séparée. Le mode manuel tactile affiche désormais, pendant
le glissement, trois grandes cibles : Interzone, Zone de Confrontation, Volontés.
Relâcher la carte sur une de ces cibles choisit un emplacement libre de la zone
du joueur. Une carte du plateau est explicitement détachée de sa superposition
ou de la Pile manuelle ; une carte d'une zone personnelle est placée face visible.

Le dépôt sur les cartes elles-mêmes conserve les superpositions volontaires.
Le parcours souris existant est conservé. Les cibles tactiles ne sont pas
proposées en règles automatisées ou en observation. Leur calcul de placement
exige un joueur assis et ne modifie aucune règle serveur.

Le nettoyage du glissement intervient après la détection du dépôt, dans un
`finally`, pour que les cibles restent présentes pendant le choix de destination.
Une annulation nettoie les cibles, surbrillances et fantôme sans envoyer d'action.

## Deck / Mazzo

Sur écran tactile, un bouton de recherche de 44 pixels apparaît directement sous
le Deck du joueur. Il appelle le même parcours `searchPile` que l'entrée de menu
existante et ne crée pas d'accès au Deck adverse ou aux modes d'observation.

Le navigateur de pile propose un filtre par nom affiché de carte, insensible à
la casse et aux accents. Il ne modifie ni l'ordre ni le contenu de la pile. Une
carte déjà sélectionnée reste en attente de confirmation même si le filtre la
masque. L'état vide indique de retirer le filtre. La recherche est effacée à
l'ouverture d'une nouvelle pile ou après fermeture/réouverture. Les commandes
de confirmation restent accessibles. Le filtre et les nouveaux libellés sont
traduits en français, anglais et italien ; les libellés sont actualisés lors
du rendu du navigateur de pile.

La barre de recherche partage la ligne des commandes sur les petits paysages.
Le réglage de taille des cartes reste présent sous une forme compacte et
conserve son étiquette accessible.

## Vérifications

`tests/test_mobile_manual_ui.cjs` exécute **156 contrôles réussis** sur
844 × 390 et 640 × 288 avec tactile émulé, puis 1440 × 1000 avec souris,
dans trois langues et depuis les deux places de joueur :

- 72 dépôts tactiles réussis depuis la Main et le plateau vers les trois zones,
  avec des cartes déjà présentes dans Interzone et Volontés ;
- 12 annulations tactiles, sans message envoyé et sans fantôme résiduel ;
- 18 parcours de recherche, filtrage, choix dans le vrai menu, conservation de
  sélection masquée, confirmation et réouverture sans ancienne recherche ;
- 18 contrôles du résolveur de superposition sur une vraie carte du DOM,
  distincts des gestes tactiles natifs ;
- 18 contrôles d'exclusion en règles automatisées/observation et 18 contrôles
  d'absence d'erreurs JavaScript.

Les messages de placement/déplacement sont vérifiés, ainsi que la zone déduite
des coordonnées envoyées et l'absence de `stackOnId` sur un dépôt explicite.
Les superpositions volontaires vérifient inversement leur ancre.

Les **96 contrôles de débordement** du lot précédent sont réexécutés sur cette
interface dans un répertoire distinct. Les suites `test_frontend.cjs` et
`test_drag_cleanup.cjs` réussissent également. L'inspection visuelle a conduit
à renforcer la spécificité CSS du raccourci pour garantir ses 44 pixels malgré
les styles compacts existants ; une assertion vérifie cette hauteur.

Les preuves et captures sont dans
`reports/systematic-audit/mobile-manual-ui-followup/`. La première passe conserve
138 contrôles réussis ; la confirmation ajoute les 18 vérifications explicites
de superposition et les contrôles de réouverture/dimension dans les parcours
existants. Les empreintes des sources sont conservées dans les rapports finaux.

## Limites

Il s'agit de Chrome avec tactile émulé et images locales. Les gestes tactiles
sont envoyés par le navigateur ; le contrôle de superposition volontaire
appelle directement le résolveur sur la géométrie réelle du DOM. Les messages
sont interceptés pour vérifier leur contenu, sans nouvelle certification du
protocole serveur ou d'une partie entière.

Aucun appareil physique, clavier logiciel réel, Safari ou Samsung Internet réel
n'est certifié. Le compteur des clauses de cartes reste celui du lot précédent ;
les 3 083 tests Python antérieurs ne sont pas présentés comme réexécutés sur
cette interface. Aucun changement de version, commit ou push.
