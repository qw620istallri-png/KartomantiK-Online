# Moteur de règles assistées KKO

Ce document est le point d'entrée technique pour reprendre l'automatisation de
Kartomantik Online avec une autre IA ou un autre développeur.

Le mode assistance reste une bêta optionnelle. Le serveur automatise uniquement
ce qu'il peut démontrer depuis l'état partagé et les capacités déclarées. Tout
texte non encodé reste appliqué manuellement par les joueurs.

## Sources de vérité

Par ordre de priorité :

1. le livret Rules 2.x ;
2. les pages d'additions et d'errata ;
3. le texte anglais actuel des cartes ;
4. `public/card-abilities.json` pour l'encodage déclaratif ;
5. les tests, qui doivent refléter les sources précédentes et non les remplacer.

Les références locales se trouvent dans `_A_NE_PAS_UPLOADER/`. Ce dossier ne
doit pas être publié.

Décisions déjà confirmées :

- les sessions peuvent être perdues lors d'un redémarrage ;
- le mode assistance reste dans le menu discret en haut à droite ;
- l'objectif est de construire des mécaniques réutilisables avec quelques
  cartes pilotes, pas d'annoncer rapidement toutes les cartes comme automatisées.

## Carte de l'architecture

| Fichier | Responsabilité |
|---|---|
| `server/main.py` | HTTP statique, WebSocket, autorisations, dispatch des messages, chargement du catalogue et compilation des métadonnées statiques |
| `server/session.py` | État de partie et moteur de règles autoritaire |
| `public/cards-data.json` | 300 cartes du jeu de base |
| `public/extensions/inner-desert/cards.json` | 150 cartes Inner Deserts |
| `public/card-abilities.json` | Capacités automatisées déclaratives |
| `public/automation-coverage-overrides.json` | Statuts confirmés et références de tests maintenus manuellement |
| `public/automation-coverage.json` | Registre généré pour les 450 cartes |
| `public/app.js` | Rendu, interaction, prévisualisation des coûts/cibles et dialogues de choix |
| `public/i18n.js` | Libellés d'interface et de journal |
| `tests/test_game_state.py` | Tests unitaires du moteur |
| `tests/test_card_catalog.py` | Tests du catalogue et de la compilation des capacités |
| `tests/test_websocket_integration.py` | Tests traversant le vrai protocole WebSocket |
| `tools/automation_coverage.py` | Génération et validation du registre de couverture |
| `tests/test_frontend.cjs` | Tests de rendu navigateur, lorsqu'un environnement Playwright est disponible |

`Session` est la source de vérité. Le client ne décide jamais qu'une action est
légale : il ne fait qu'en proposer une représentation plus pratique.

## Phases avancées

L'ordre officiel est défini par `ADVANCED_PHASES` :

```text
recovery_start
recovery_draw
recovery_end
confrontation_choose
confrontation_before_revelation
confrontation_reveal
confrontation_immediate
confrontation_entry
confrontation_reaction
resolution_compare
resolution_effects
resolution_move
end_actions
end_triggers
end_expire
```

Points importants de l'errata :

- `recovery_end` se produit après la pioche et avant le choix des Premières
  Manifestations ;
- `confrontation_before_revelation` se produit après le choix face cachée des
  Premières Manifestations et avant leur révélation ;
- les cartes restent face cachée pendant cette fenêtre ;
- les Volontés Éphémères et capacités activées sont autorisées pendant
  `end_actions`, mais pas pendant `end_triggers`.

## Cycle d'une action

Une action encodée suit ce chemin :

1. le client construit un brouillon depuis les capacités déclarées ;
2. `declare_rules_action` revalide la phase, la priorité, la source et les
   cibles ;
3. le serveur calcule puis paie le Tribut et les coûts supplémentaires ;
4. le contrôleur accepte ou refuse les déclenchements optionnels (`may`/`can`) ;
5. seules les actions acceptées et les déclenchements obligatoires simultanés
   sont placés sur la Pile ;
6. chaque ajout ou passe transfère la priorité ;
7. deux passes consécutives résolvent uniquement le sommet ;
8. la source jouée change de zone ;
9. les cibles sont entièrement revalidées ;
10. le résultat, les effets continus et les conséquences automatiques sont
   appliqués ;
11. les nouveaux déclenchements sont collectés avant toute nouvelle réponse ;
12. la priorité revient à l'adversaire du contrôleur du nouveau sommet, ou aux
    règles normales si la Pile est vide.

Les coûts restent payés si l'action est ensuite neutralisée ou si sa cible
devient invalide.

## Paiement du Tribut

Le serveur :

- dépense d'abord les Essences compatibles ;
- vérifie Tempéraments et puissance de base ;
- accepte toute sélection dans laquelle aucune Manifestation n'est superflue ;
- génère l'Essence excédentaire ;
- fait expirer les Essences générées à la fin du tour.

Exemple : pour un coût de 3, choisir des Manifestations de puissances 2 et 1
reste légal même si une Manifestation de puissance 3 est également en main.

Les destinations alternatives sont portées par
`card_rules[card_id]["tributeDestination"]` :

- `graveyard` : Limbo normal ;
- `deck_bottom` : Glob-glob ;
- `stalemate` : Sly Frog.

`action["cost"]["tributeMovements"]` décrit les mouvements réellement payés.

## Cibles

Une cible est validée à la déclaration et à la résolution.

Contrats actuellement disponibles :

```text
kind
min / max
cardType / cardTypes
zones
controller: self | opponent
fieldZone
supportOnly
maxPoints
maxPower
excludeEventSource
sourceOnly
```

`sourceOnly` sert notamment à Gornagor : l'effet ne peut cibler que sa propre
source.

Une cible devenue invalide produit `invalid_targets` et l'effet ne se produit
pas.

## Propriété et contrôle

`ownerId` ne change jamais. `controllerId` est facultatif et n'est stocké que
lorsqu'il diffère du propriétaire.

- la puissance de Confrontation, la priorité, les cibles `self/opponent` et les
  capacités de champ utilisent le contrôleur ;
- les Decks, Mains, Limbes et Exils utilisent toujours le propriétaire ;
- lorsqu'une carte contrôlée par un autre joueur quitte le champ ou la
  Stalemate Zone, elle revient dans une zone de son propriétaire ;
- la Résolution capture les Manifestations selon leur propriétaire, comme
  indiqué par le livret, même si leur contrôle avait changé.

La famille est couverte par :

- Hot Potato : transfert initial, coût dynamique selon les marqueurs Burn,
  transfert activé, perte de points du contrôleur actuel et destruction ;
- Thought Saboteur : contrôle lié à la présence de la source ;
- Invert Emotions : échange asymétrique entre deux Interzones ;
- Dominate the Aspects : échange en Confrontation puis retour différé sous les
  Decks des propriétaires à la Résolution.

Les capacités à cibles asymétriques utilisent `targetGroups`. Les déclenchements
qui exigent une cible inconnue au moment du mouvement utilisent le choix
bloquant `trigger_targets`.

## Déclenchements simultanés

Les actions simultanées sont construites hors de la Pile.

1. le joueur avec la priorité place les actions qu'il contrôle ;
2. l'adversaire place ensuite les siennes ;
3. si un joueur en contrôle plusieurs, `simultaneous_stack_order` lui demande
   leur ordre ;
4. le lot complet est ajouté atomiquement ;
5. aucune réponse n'est possible avant cette opération.

Une action payée et les déclenchements des Manifestations utilisées comme
Tribut sont dans le même lot. Reliable Ammonite est le pilote de cette règle.

## Effets Immédiats

Une capacité déclarée avec `"immediate": true` est placée au-dessus des autres
actions simultanées et résolue sans passe de priorité. La résolution utilise le
même pipeline que le sommet normal de la Pile : source, cibles, résultat,
conséquences automatiques et nouveaux déclenchements.

- Pontificate Heresy mélange les Mains puis fait piocher quatre cartes ;
- Extinguish Nostalgia exile les Limbes présents avant que la carte elle-même
  rejoigne les Limbes ;
- Kiss of the Myrmillo! demande son paiement interne sans créer de fenêtre de
  réponse, peut terminer immédiatement la Confrontation puis, si son contrôleur
  perd ainsi, réutilise le choix de cible bloquant pour appliquer la perte de
  puissance calculée depuis les puissances de base mémorisées avant la
  comparaison.

## Effets continus, modificateurs et mémoire

Ne pas fusionner ces trois concepts.

### Effets continus

Stockés dans `rules_engine["ongoingEffects"]`.

Durées disponibles :

- `until_end_of_turn` ;
- `while_source_and_target_on_field`.

Exemples : bonus de puissance, puissance ignorée, copie de puissance et
Tempérament, gain temporaire de Persist.

### Modificateurs et marqueurs physiques

Les marqueurs physiques sont dans `item["counters"]`. Les coûts peuvent retirer
des marqueurs avec `removeAllCountersFromSource`. La valeur retirée peut
alimenter un effet via `valuePerRemovedCounter`.

Intoxicating Blossom est le pilote de ce modèle.

### Mémoire

Stockée dans `rules_engine["effectMemories"]`.

Une mémoire est identifiée par la carte et son propriétaire. Elle survit aux
passages par :

- le champ ;
- la Stalemate Zone ;
- la Main ;
- les Limbes ;
- un Réceptacle Empathique.

Elle est supprimée lorsque la carte entre dans :

- un Deck ;
- l'Exil.

Les mémoires de fin de tour créent de vraies actions déclenchées pendant
`end_triggers`. Lady of the Humps, Coral Skull et Refrain Repeater sont les
pilotes actuels.

## Decks, révélations et réordonnancement

Le moteur suit désormais le tour d'entrée de chaque carte dans une zone afin
de valider les effets limités aux cartes arrivées « ce tour-ci ».

- Skysailing Triad résout la carte du dessus selon son type ;
- Lady of the Humps Enchaîne depuis le Deck, mélange et mémorise l'Exil du
  gagnant ;
- Dissect présente au contrôleur les trois cartes du dessus de chaque Deck et
  valide côté serveur leur répartition et leur ordre ;
- Caress the Dawn ne propose que les cartes arrivées dans les Limbes pendant
  le tour courant et impose la moitié arrondie au-dessus ;
- Jodorosk garde la carte adverse secrète jusqu'à la déclaration, révèle les
  caractéristiques réelles, puis applique le gain de points et la suite
  correspondant au nombre de réponses exactes.

Les choix privés de Deck ne sont jamais sérialisés aux joueurs adverses.

## Jetons et copies

Les copies de carte et les jetons génériques partagent désormais une création
serveur avec provenance de source, contrôleur, zone de champ et suppression
automatique lorsqu'ils quittent le champ.

- Jija crée des jetons Creux 1 sans effet selon l'Interzone ciblée et peut
  sacrifier un jeton qu'elle a créé ;
- Bratto capture une Manifestation d'Impasse non possédée puis crée sa copie en
  Soutien ;
- Melancholic Mirror observe les Manifestations utilisées comme Tribut et
  propose un choix optionnel d'épuisement ;
- Recall the Consumed exile les Manifestations des Limbes et crée les copies
  Creuses sans effet correspondantes ;
- Tuxnu observe l'entrée d'une Volonté Persistante non-Jeton et crée les copies
  pour les autres joueurs.

## Main et Récupération

Les limites de Main sont calculées par le serveur pour le tour courant. Les
cartes excédentaires créent un choix privé obligatoire dont la destination est
déclarée par l'effet.

- Possessed Pyramid planifie une réduction d'une carte pour le tour suivant ;
- Red Plague demande la perte de points ou applique la limite de cinq ;
- Palm Coercer fixe la limite à six et place l'excédent sous le Deck dans
  l'ordre choisi ;
- Solitary Combhand augmente la pioche de Récupération selon les emplacements
  vides de l'Interzone ;
- Kanon remplace une pioche hors Récupération par une inspection privée, la
  défausse de la moitié arrondie au-dessus et la distribution des pertes de
  puissance produites par les Volontés défaussées.

## Coûts et ressources

Le paiement prend maintenant en compte les réductions de Tribut, les coûts
supplémentaires exclusivement payés en Essences et les sources alternatives de
Tribut.

- Arcane Teapot réduit d'un le Tribut des Volontés de son contrôleur ;
- Alchemical Press entre avec cinq marqueurs Formule, autorise les
  Manifestations des Limbes comme Tribut vers l'Exil et propose le cycle
  défausse/pioche après une Volonté ;
- Inflate the Ego réduit son coût depuis la puissance de base de la Première et
  fixe cette Manifestation à 10 avec un maximum de 10 ;
- Multicastigate déduit le coût supplémentaire de trois Essences de la présence
  d'une deuxième cible ;
- Subjugate calcule le nombre minimal d'Essences depuis la valeur en Points de
  la cible ;
- Essence Cauldron empêche l'expiration des Essences excédentaires de son
  contrôleur.

## Actions depuis l'Interzone et Support

Les capacités activées peuvent maintenant déclarer `sourceZones`, un
`sourceFieldZone`, un coût exclusivement payé en Essences et plusieurs effets
continus. Le paiement de Tribut accepte également une Manifestation autorisée
depuis l'Interzone avec une puissance de Tribut imprimée différente.

- World Spore paie depuis l'Interzone avec une puissance de Tribut de deux ;
- Diabolical Giant active son gain de Support depuis la Main ou l'Interzone ;
- Gusted Nebula ordonne les retours des Soutiens et renforce les Premières ;
- Chobariki choisit son contrôleur, paie son Essence et applique ses résultats
  de victoire ou de défaite ;
- Brioski compile la forme `Support; Float` ;
- Bakato obtient sa permission de jeu depuis les Limbes et son Exil de victoire ;
- Leadenshroud mémorise les destructions et défausses du tour avant de
  réanimer sa cible en Soutien ;
- Cirrocumulus résout immédiatement un élément contrôlé de la Pile ;
- Stormmace crée simultanément son bonus et sa Protection ;
- Lugione impose le seuil de puissance quatre avant destruction ;
- Haltan choisit le changement de Points ou empêche globalement tout changement
  de Points jusqu'à la fin du tour.

## Lots manuels simples

Le parseur reconnaît maintenant les puissances de Tribut Inner Deserts écrites
avec les symboles illustrés. Orzo, Faroc-Ko, Philfer, Quasimolg et Proboscidon
réutilisent ainsi le paiement depuis l'Interzone de World Spore.

Les primitives existantes couvrent également :

- les observateurs simples de Callus, Will-punishing Cannon, Crickelob et
  Essence Forager ;
- les déplacements Limbes/Main/Interzone de Recover from the Abyss, Revive et
  Reveal the Hidden ;
- la copie en Soutien de Mirror the Impulse et le Support temporaire de Unite
  Impulses ;
- les puissances dynamiques de Heartening Monument, Tipson, Planar Beak et
  Repelling Urn.

Cleanse supprime les effets et caractéristiques ajoutés à sa cible, y compris
les effets continus, pertes d'effets, changements de Tempérament, permissions
temporaires, Protection, copie de caractéristiques et contrôle ajouté. La
carte conserve sa zone, son rôle normal dans cette zone, son orientation, son
texte et ses statistiques imprimés ainsi que tous ses compteurs.

Rally déclare désormais un nombre optionnel d'Essences supplémentaires après
le paiement de son Tribut minimal. Le serveur prélève exactement ce montant et
crée autant de Tokens Creux de puissance 1 en Soutien.

Les cartes classées `manual` proposent une action explicite **Jouer
manuellement** depuis la Main. Elle place la carte sur le plateau sans appliquer
les fenêtres ni les coûts assistés et sans créer d'action dans la Pile. Les
choix obligatoires et permissions de session restent prioritaires.

Les modificateurs continus imprimés sont exposés dans l'état public avec la
puissance effective et affichés comme un modificateur sur la carte. Skapus
montre ainsi son +2 lorsqu'il est le seul Soutien contrôlé. Flower Tender
utilise l'événement attaché à sa propre entrée dans la Zone de Confrontation,
et non un observateur de toutes les entrées en Soutien.

## Aléatoire

Les jets sont produits et appliqués par le serveur, avec le résultat conservé
dans le résultat structuré de l'action.

- Greed Trap complète son remplacement à zéro avec son déclenchement sur les
  Volontés adverses ;
- Plinius applique le modificateur pair/impair ;
- Mutate Uncontrollably couvre destruction, changement de Tempérament et bonus
  de puissance ;
- Bibi mémorise son jet, demande sa cible uniquement sur un résultat impair et
  réutilise ce jet lorsqu'elle gagne avant de s'Exiler ;
- Pillarpede lance cinq dés, ajoute les bonus pairs et demande la défausse
  privée correspondant aux résultats impairs.

Karma Bro et Kaos Bro restent explicitement `manual` car leur texte dépend d'un
lancer physique et des cartes réellement touchées.

## Phases et victoire

La Révélation produit désormais un événement serveur distinct capable de
résoudre des Effets Immédiats avant les déclenchements d'entrée habituels.

- The Stomper mémorise un gagnant forcé lorsque sa Première possède la plus
  haute puissance de base et mélange automatiquement lorsqu'il atteint le
  dessous du Deck ;
- Sermon demande au joueur concerné de perdre 10 points ou de passer la
  Confrontation ;
- Unpredictable Loudmouth force l'Impasse s'il est la dernière Manifestation
  entrée dans la Zone de Confrontation ;
- Half Han ne peut pas payer de Tribut, exclut son propriétaire de la victoire
  normale lorsqu'il est dans les Limbes et active la victoire à -130 ou moins ;
- Jeovak s'Exile, demande la répartition Interzone/dessous de Deck de toutes
  les Manifestations, termine la Confrontation, saute la Résolution et accorde
  50 points à l'adversaire.

## Généralisation Inner Deserts

`Float` n'est plus limité au mot-clé imprimé : le calcul consulte les effets
continus de gain et de perte ainsi que les marqueurs déclaratifs. Gladionimbus,
Float et Sever the Ascent utilisent ce même chemin ; Hyperuranic Tower accorde
Float depuis les marqueurs Abstraction, donne le bonus de puissance associé,
entre avec ses trois marqueurs et peut en déplacer un entre deux cibles
revalidées.

`Adamant` est compilé pour toutes les cartes du catalogue portant le mot-clé et
reste une interdiction absolue face aux mouvements encodés d'un adversaire.

La Suspension accepte désormais des politiques de retour et de jeu autres que
BOB. Gobres utilise la fenêtre avant Révélation, fait choisir secrètement une
Volonté adverse, la retire de toutes les zones normales, permet à son contrôleur
de la jouer avec tout Tempérament de Tribut, puis la renvoie en Main à la fin du
tour ou lorsque Gobres quitte le champ.

Les effets de Chain, recherche ou tutorisation depuis une pile cachée exposent
au joueur concerné une fenêtre privée contenant uniquement les cartes
éligibles. L'adversaire voit qu'un choix est en attente, mais jamais le contenu
filtré de la pile. Lady of the Humps utilise ce flux pour son Chain depuis le
Deck ; le choix ne dépend plus d'un glisser-déposer depuis une pile invisible.

## Conséquences automatiques

Après une résolution, `resolve_rules_state_actions` détruit immédiatement une
Manifestation dont la puissance vient d'atteindre 0 ou moins. Les effets de
remplacement sont consultés avant cette destruction :

1. Berta peut empêcher la puissance de descendre sous sa valeur de base ;
2. Greed Trap déplace une Manifestation adverse à exactement 0 dans le
   Réceptacle Empathique de son contrôleur ;
3. Life Sustainer maintient une Manifestation à exactement 0 sur le champ et
   lui fait perdre ses effets ;
4. sans remplacement, la Manifestation est détruite.

Une carte ayant perdu ses effets ne peut plus produire de passif, déclencher ou
activer ses capacités, ni utiliser ses mots-clés. Si Life Sustainer quitte le
champ alors qu'une Manifestation maintenue est toujours à 0, les conséquences
automatiques sont recalculées et cette Manifestation est détruite.

Autres conséquences déjà gérées :

- expiration des effets temporaires ;
- expiration des Essences générées ;
- perte des mémoires au Deck ou à l'Exil ;
- nettoyage des relations lorsqu'une source ou cible quitte le champ ;
- preuve publique d'une Main lorsqu'une action obligatoire la concernant est
  impossible.

## Persist

Persist peut être :

- imprimé sur la carte (`card_rules.persist`) ;
- accordé temporairement par un effet `grant_persist`.

À la Résolution :

- une Manifestation gagnante avec Persist reste dans la Zone de Confrontation ;
- elle devient la Première Manifestation du tour suivant ;
- elle ne redéclenche pas ses effets d'entrée ;
- si plusieurs gagnantes ont Persist, leur contrôleur en choisit une et les
  autres retournent sous leurs Decks.

## Mots-clés Inner Deserts

- `adamant` : un effet adverse encodé ne peut pas déplacer cette carte hors de
  sa zone ;
- `float` : la Manifestation peut partager un emplacement d'Interzone ;
- `suspendedCards` : stockage distinct de l'Exil et de toutes les zones
  normales ;
- `minimumPower` / `maximumPower` et effets `power_minimum` /
  `power_maximum` : limites appliquées après les modificateurs.

## Choix bloquants

`rules_engine["pendingChoice"]` bloque toute autre mutation de jeu.

Choix principaux :

- paiement conditionnel ;
- cibles d'une copie ;
- ordre d'actions simultanées ;
- défausse privée ;
- Chain ;
- destination de Résolution ;
- remplacement d'Interzone ;
- choix d'une Première avec Persist ;
- retour ou paiement d'une mémoire.

Le serveur doit rester bloqué jusqu'à résolution complète du choix.

## Pilotes d'issue de Confrontation

Les évènements `wins_confrontation` et `loses_confrontation` sont émis pour
chaque Manifestation participante, selon son contrôleur, avant le déplacement
final. Ils réutilisent les cibles de déclenchement (`trigger_targets`) et le
choix optionnel (`optional_stack_action`) existants.

- Solenero (perd, renvoie une carte de son Limbo en main), Sallow Thief
  (gagne, reprend une carte qu'il possède depuis le Réceptacle d'un adversaire),
  Knobbly Colossus (gagne, détruit une Volonté ou Manifestation adverse),
  Borombo (perd, détruit une Manifestation adverse de la Confrontation) et
  Tardigramo (gagne, l'adversaire exile une Manifestation aléatoire de son
  Réceptacle) ne demandent que des entrées JSON ;
- le contrat de cible `container: "opponent"` restreint une carte d'une zone
  publique au conteneur d'un adversaire (serveur et client) ;
- `score_owner` accepte `perCount: "own_interzone_manifestations"` : Floating
  Dancer gagne 5 points par Manifestation contrôlée dans son Interzone ;
- Mind Parasite (Chain depuis le Limbo) et Reforging Fate (Soutien depuis un
  Limbo) réutilisent `chain_from_zone` et `play_limbo_target_as_support` avec
  l'exil du gagnant.

## Jouer en phase de fin et statiques de puissance

- `endPhaseInterzonePlay` (compilé depuis « In the End Phase, X can be played
  into the Interzone. ») autorise Flem, Viter, Mal, Capry et Chol à passer de la
  Main à l'Interzone pendant `end_actions`, Pile vide, avec priorité et une
  place libre. Le message `place_card` ordinaire est utilisé : le serveur reste
  l'arbitre et refuse le même geste dans toute autre phase.
- `canPayTributeFromInterzone` reconnaît désormais « X can be used as tribute
  from the Interzone. » ; sans puissance de Tribut alternative, c'est la
  puissance imprimée qui compte. `canPayTribute` reconnaît aussi « Cannot be
  used as tribute. ».
- Nouvelles règles de `continuousPowerRules` : `self_per_controller_limbo_card`
  (avec `floor`, Kelona), `self_per_opponent_confrontation_manifestation`
  (Lucerco), `self_per_owned_vessel_manifestation` (Vengeful Vilupera),
  `first_manifestation_per_interzone_manifestation` (Prospero) et
  `only_friendly_confrontation_manifestation` (Bell).

- Les 16 Manifestations sans texte imprimé n'ont aucune mécanique à encoder :
  elles sont `automated` parce que le moteur de base (jeu, puissance, Tribut)
  les couvre déjà ; `test_vanilla_manifestations_have_no_printed_effect_to_automate`
  échoue si l'une d'elles gagne un texte.
- `score_owner` accepte aussi, pour une Volonté jouée, `perCount:
  "target_player_confrontation_non_token_manifestations"` (Plea for Generosity).

## Tests

Commandes minimales :

```powershell
py -m unittest discover -s tests -p "test_*.py" -q
node --check public\app.js
node --check public\i18n.js
```

Les tests WebSocket démarrent leur propre serveur sur un port éphémère et ne
touchent pas au serveur local déjà ouvert.

Registre de couverture :

```powershell
py tools\automation_coverage.py --write
py tools\automation_coverage.py --check
```

Les statuts sont :

- `manual` : le moteur ne fournit aucune automatisation fiable et
  significative du texte imprimé ; une reconnaissance de sous-chaîne qui
  accorde une permission trop large ne compte pas comme couverture ;
- `generic` : statut provisoire généré à partir de métadonnées statiques, avant
  audit du texte complet ; il ne prouve jamais que la carte est couverte ;
- `partial` : au moins une mécanique imprimée est réellement automatisée, mais
  une ou plusieurs autres restent manuelles ; l'override doit nommer les
  mécaniques manquantes dans `notes` ;
- `automated` : chaque capacité imprimée a été comparée au comportement
  serveur/client, est entièrement automatisée et possède des références de
  tests dans `testRefs`.

Un mot-clé compilé (`Support`, restriction de Première Manifestation,
`Adamant`, `Float`, etc.) ne suffit donc pas à promouvoir une carte si le reste
de son texte n'est pas implémenté. L'audit des 72 anciennes cartes `generic`
les classe explicitement et laisse désormais le compteur `generic` à zéro.

`tests/test_frontend.cjs` exige `playwright` et `pngjs`. Ne pas ajouter ces
dépendances au projet sans déclarer explicitement un environnement JavaScript.

## Règles de modification

- corriger le moteur avant d'ajouter des exceptions de carte ;
- préférer une primitive réutilisable à une branche nommée d'après une carte ;
- ne pas déduire une mécanique complexe avec une recherche approximative dans
  le texte ;
- garder les interdictions absolues prioritaires sur les permissions ;
- ne jamais faire confiance au client pour les informations privées ou la
  légalité ;
- ajouter au minimum un test catalogue et un test moteur pour toute nouvelle
  capacité ;
- ajouter un test WebSocket lorsqu'un nouveau message, choix ou changement de
  phase est introduit ;
- conserver `reset_board` hors de tous les verrouillages de partie : ce message
  doit annuler choix obligatoires, Mulligan, Pile et état de fin avant de
  reconstruire le plateau ;
- augmenter la version statique dans `public/index.html`, `public/app.js` et
  `README.md` après une modification d'asset client.

## État actuel et prochaine extension

Le socle couvre phases, priorité, Pile, Tributs, cibles, déclenchements
simultanés, Persist, mémoire, remplacements de destination et coûts en
marqueurs. Les huit grandes familles disposent désormais d'au moins un pilote :

1. modificateur global : Corrode ;
2. Tempéraments alternatifs de Tribut : Shimmering Seaguide, Blunt Leaf et
   Rocky Heartcrystal ;
3. marqueurs : Intoxicating Blossom ;
4. observateurs permanents : Intoxicating Blossom et Wheel of Retribution ;
5. mémoire : Lady of the Humps, Coral Skull et Refrain Repeater ;
6. Pile : Neutralize, Deny, Ignore et Imitate ;
7. phase supplémentaire : Rematch ;
8. carte-système : BOB.

Le pilote BOB couvre sa croissance, Persist, les seuils de Suspension
Deck/Limbo, l'immunité des Mains, la libération des cartes suspendues et son
seuil d'Exil. Les remplacements de Suspension ne s'appliquent qu'aux mouvements
que le moteur sait identifier comme provenant d'une carte ou d'un effet ; les
mouvements manuels restent sous arbitrage des joueurs.

Les prochaines familles utiles sont :

- remplacements de destruction à 0 puissance ;
- contrôle temporaire et retour au propriétaire ;
- changements d'effets et de caractéristiques ;
- Immediate Effects ;
- davantage de fenêtres spéciales d'Inner Deserts.

Familles supplémentaires couvertes :

- perte et remplacement des effets : Annihilating Nectar, Embottle, Obscure,
  Starkaz et Vexing Thorn ; Mirrorbeast copie la puissance, les mots-clés,
  passifs, déclenchements et capacités activées de sa cible jusqu'à la
  Résolution, y compris les déclenchements d'entrée acquis ;
- Protection et Immunité : Mobile Sanctuary, Rajas, Purifying Ritual et
  Protect ; Psychowall autorise son activation de destruction par chacun des
  deux joueurs et Wall Off protège aussi une carte sur la Pile, puis transfère
  cette protection au permanent lorsqu'il entre sur le champ.

La passe de clôture des 39 anciennes cartes `partial` ajoute également :

- les fenêtres d'activation déclaratives avec `phaseIds` ;
- les activations `anyPlayer` dont le contrôleur diffère de celui de la source ;
- les contrats de cible exigeant un marqueur et les résultats `move_counter` ;
- la cible union `card_or_stack_action` et la protection des objets de Pile ;
- la revalidation correcte d'une Première Manifestation adverse ;
- le changement de cible de Flaying Jaw et les restrictions de Support de
  Nullifying Hat.

Les modes multijoueurs, 2v2 et Bazaar Draft restent explicitement hors
périmètre tant que le mode deux joueurs n'est pas stabilisé.

- Condition `firstWillOfTurn` sur `will_played` : le serveur compte les Wills jouées par joueur et par tour (`rules_engine.willsPlayed`) ; Hermetic Threshold pioche sur la première Will de chaque joueur.
- Évènements observés (`points_lost`, `cards_discarded`, `manifestation_destroyed`, `manifestation_enters_opponent_vessel`) : le moteur les note dans `rules_engine.observedEvents` (via `adjust_rules_score`, `move_zone_card`, `_rules_remove_field_item*`) puis `queue_rules_observed_event_triggers` les transforme en déclencheurs à la fin de la résolution d'une action ou d'un choix. `eventController` filtre le joueur concerné. Pilotes : Pale Entity, Conflux of Catastrophe, Compensating Orchard.
- Résultat `destroy_matching_on_field` (`match` : `entered_support_this_turn` via `rules_engine.supportEntries`, ou `won_confrontation_this_turn` via `confrontationResult.participantItemIds` du gagnant) : détruit en masse. Adamant ne protège que du déplacement : un effet `move_target` avec `reason: "destroy"` n'est pas bloqué. Pilotes : Incinerate, Punish the Winners.
- Volontés persistantes Atavic : drapeau `playBeforeRevelation` (regex dans `build_card_rules`) = jouable en `confrontation_before_revelation` ; coût d'activation `removeCountersFromSource {name, amount}` (validé à la déclaration, payé dans `pay_rules_activation_cost`) ; filtres de déclencheur `firstWillOfTurn`, `cardTemperament`, `sourceCounterMin`, `controllerConfrontationManifestations` ; événements `card_played`, `player_wins_confrontation` / `player_loses_confrontation`.
- Résultat `chain_from_zone` étendu (Chain depuis la main) : `players` (`each_opponent` / `all`, un choix privé à la fois via `begin_rules_chain_sequence`, suite dans `pendingChainSequences`), `scoreCost` (Help!), `preMove: first_manifestation_to_deck_bottom` (Mollino), `afterChain` (`discard_deck_per_base_power`, `power_counter_target_per_base_power`) et `chainAbilities` (effets qui ne s'appliquent qu'à la manifestation enchaînée : `wins_confrontation` / `loses_confrontation`, résolus par `queue_rules_chain_outcome_triggers`). Un joueur sans manifestation jouable montre sa main (`handProofs`). Résultats associés : `move_source_to_owner_hand`, `score_each_opponent` ; `perCount` : `source_base_power`, `source_card_points`. Règle de puissance `self_per_opponent_confrontation_total` (+1 par manifestation adverse, plafond `cap`, Kazadur).
- Cartes « entré dans une zone ce tour » : `zoneEntryTurns` (cartes en Limbo/Vessel/etc., règle de cible `enteredThisTurn` + `container`/`owner`) et `interzoneTurn` posé par `mark_rules_interzone_entry` sur les manifestations de l'Interzone (règle `enteredInterzoneThisTurn`). Résultats : `move_zone_target_to_own_vessel` (Claim the Forsaken), `move_zone_target_to_field_zone` avec `fieldZone: stalemate` (Salvage, Mock Fate), `move_target_to_own_vessel` (Manipulate Intellect, Adamant respecté), `return_target_player_support` (Abandon, interdit de rejouer jusqu'à la fin du tour), `return_target_player_interzone_to_deck_top` (Rogue Tadpole, ordre = ordre du plateau). Drapeau `reactionEmptyStackOnly` (Mock Fate).
- Lot « cartes manuelles » : `create_essence` accepte `retained` (essence conservée, `expiresTurn: 0`) et `perCount` ; `reorder_top_decks` accepte `afterDraw` ; règle de cible `confrontationOutcome: won|lost` (via `confrontationResult`) ; drapeau `playPhases` (calculé par `play_phases_for_card` : « only during the Reaction / Resolution / before the Revelation », vérifié par `rules_action_timing_error` et `rulesEphemeralPhasesClient`) ; résultats `double_target_base_power`, `destroy_random_interzone_target_player`, `destroy_target_gain_points`, `exile_target_on_win` (mémoire `win_destination_exile`), `shuffle_hand_into_deck_and_draw`, `exile_limbo_targets_add_power`, `deck_discard_then_weaken`, `play_limbo_target_as_support` + `losesEffects`.

### Lot des cartes manuelles « faciles »

Pigon, Sticky Fasces-fly, Pass Judgment, Dissolve and Coagulate, Convert the Pain, Eviscerate Morality, Induce Desertion, Rah-kio, Volcano, Consult, Reviving Cage, Armored Husk, Humiliate et Veer the Will sont automatisées avec des résultats dédiés (`add_power_counter_target`, `weaken_target_per_hand_card`, `dissolve_vessel_targets`, `destroy_support_targets_draw`, `power_counter_from_other_target`, `destroy_all_tokens`, `exile_all_wills_and_interzones`, `consult_support`, `humiliate_target`), l'option `afterDiscard` de `reorder_top_decks`, `sacrificeDestination: "exile"` sur les capacités activées et `destination: "hand"` pour `neutralize_stack_action`.
