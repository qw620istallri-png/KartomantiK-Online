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

### Cartes partielles passées en automatique

Lament, Nameless Arcane, Ononok, Lilitha, Mamelath, Silem, Timidette, Drildrill et Phalanx Tower ont des résultats dédiés (`mill_deck_per_confrontation_manifestation`, `sacrifice_other_confrontation_for_essence`, `exile_source_then_shuffle_limbo_and_interzone`, `destroy_target_tokens_for_controller`, `first_manifestations_to_interzone_tokens`, `stalemate_to_support_disabled`, `timidette_support_to_deck_bottom`, `destroy_persistent_will_refund_essence`, `optional_discard_manifestation_weaken_target`). Timidette range les Supports dans l'ordre du plateau (l'ordre choisi par le joueur n'est pas demandé).

### Cartes partielles, lot 2

Makaboon (`deck_cards_discarded`), Denblew (`cards_drawn`, `oncePerTurn`), Atavic Oppression (`optional_discard_up_to`), Tigrolione (`lossDestination: winner_interzone`), Absent Trinket (`manifestation_targeted_by_will`, `return_source_to_hand_restricted`), Yzzit (`vesselEntryRoll`), Jesterina (`chain_discarded_manifestation_from_target_deck`), Linoleus (`points_gained`, `score_owner_silent`) et Inert Anchorstone (`supportWhenNoCounter`) sont automatisées. Les événements observés `cards_drawn` sont détectés par un mouvement deck vers main en position `bottom` hors phase de Récupération.

### Cartes manuelles, lot 2

Filth-eater, Zozok, Pan Zuto, Flower of Evil, Shattered Memory, Compensate, Ohmom, Walk the Oblivion et Quorum sont automatisées. Le choix de défausse `discard_from_hand` accepte désormais `upTo` (jusqu'à N cartes), `requireTypes`, `sourcePowerPerDiscard` et `lossPerRemaining`, avec une sélection multiple côté client. `neutralize_stack_action` accepte `refundEssence`.

### Lot 3 (entrées en Limbo, verrous de Support)

- Nouvel évènement observé `card_entered_limbo` : déclenche `enters_limbo` et, si la raison est une défausse, `discarded` sur la carte elle-même (Zombieswing, Memento, Tombloom, Tenebro).
- Tenebro : approximation, la carte passe par le Limbo puis remonte en Support (le remplacement de défausse n'est pas modélisé).
- Fintus (`destroyNextEntries`) détruit la prochaine entrée adverse sans déclencher les effets propres de la carte entrante.
- Gorb / Wretched Arena : `lock_support_entries` ne couvre que les jeux en Support déclarés.
- Healing Bond, Watchtower, Horned Augustus automatisés.

### Lot 4 (jets de dé, mémoires de fin de tour, tokens d'Interzone)

- Worm Bomb détruit jusqu'à 3 manifestations au hasard dans le Réceptacle où elle entre (toujours le maximum, le choix « jusqu'à » n'est pas laissé au joueur).
- Buddhan the Dark : jet d'un D6, défausse du dessus du deck, +1 puissance par carte (compteur permanent) ; à la victoire les adversaires défaussent autant (mémorisé dans `rollDiscarded`).
- Qu Lom : mémoire de fin de tour avec jet (pair : main, impair : exil). Loop : mémoire optionnelle, ignorée si le contrôleur n'a pas perdu la confrontation du tour.
- Explosive Rancor, Punitive Tripod (puissance fixée à 1 via `power_set_maximum`), Sacred Mountain, Drain the Substance (retire toutes les essences en excès).
- Stampeding Brood : tokens `fieldZone: interzone` (non perdus à la Résolution).
- Referen-Doom : l'exil de Volontés du Limbo et les essences arc-en-ciel gagnées en cas de défaite sont automatisés.

### Lot 5 (scores de fin de partie, perte vers l'Interzone du propriétaire)

- Évènement `end_of_game` : lu uniquement par `rules_end_game_points` (appelé par `calculate_final_scores`, champ `endGamePoints`). Résultats `final_deck_points` (Phimosino : +50 si dans le deck) et `final_vessel_penalty` (Piercing Lover : -5 par manifestation de puissance de base ≤ 2 dans le Réceptacle où il se trouve).
- Flag `lossDestination: own_interzone` (Losers' Chariot) : à la défaite la carte va dans l'Interzone de son propriétaire au lieu du Réceptacle adverse ; le vainqueur gagne 15 points et ses défaites suivantes rapportent 10 points depuis l'Interzone.
- Kox (partiel) : seuls les 50 points donnés aux adversaires à l'entrée en jeu ou au Limbo sont automatisés.

### Lot 6 (choix d'une carte en main, recherche dans le deck)

- Le choix `discard_from_hand` sert maintenant aussi de sélecteur générique : `destination` (`interzone` ou `exile` au lieu du Limbo), `drawByBasePower` (pige autant que la puissance de base de la carte choisie), `destroyTargetItemId` (détruit la cible si sa puissance de base est ≤ celle de la carte choisie) et `candidateCardIds` (recherche dans le deck : les cartes choisies vont en main puis le deck est mélangé ; la liste n'est envoyée qu'au joueur concerné).
- Résultats `hand_manifestation_choice` (Dew Invoker, Censor, Martyrize) et `search_deck_to_hand` (Hermeto, Recall).
- Approximations : Censor et Martyrize choisissent la manifestation révélée à la résolution et non comme coût additionnel ; Martyrize n'exile pas la Volonté ensuite (cartes en partiel).

### Lot 7 (« sauf si l'on paie »)

- Nouveau choix `effect_payment` (réutilise le flux de paiement du plateau, comme `effect_memory_payment`) : le payeur paie le Tribut ou laisse l'effet `onDecline` se produire. Résultats `unless_payment_deck_discard` (Lerxur : le propriétaire du Réceptacle défausse 2 cartes sauf s'il paie {H}{H}) et `unless_payment_lose_effects` (Nullify : la cible perd ses effets de façon permanente sauf si son contrôleur paie {H}{H}).
- Dulfer n'est pas fait : les cartes dans un Réceptacle ne reçoivent pas l'évènement `revelation`.

### Lot 8 (Révélation depuis le Réceptacle, Support conditionnel)

- Évènement `vessel_revelation` : envoyé par `queue_rules_revelation_triggers` aux cartes présentes dans les Réceptacles (`trigger.zone: receptacle`, `container: opponent`). Dulfer : le propriétaire du Réceptacle choisit entre perdre 10 points et -2 de puissance pour sa Première Manifestation (choix `points_or_weaken_first`).
- Passif `conditional_support` (dans `card-abilities.json`) → flag `supportCondition` lu par `rules_card_can_enter_support` : `lost_previous_confrontation` (Twin-headed Druid, via `confrontationLosses` par tour), `limbo_exit_this_turn` (Mourning Offal, via `limboExitTurn` mis à jour dans `take_zone_card`), `five_wills_in_limbo` (Artificial Thinker, +2 puissance en Confrontation via la règle continue `self_in_confrontation_with_five_limbo_wills`).
- `serialize_for` publie `canEnterSupport` sur les objets de l'Interzone : le menu client « Jouer en Support » s'appuie dessus (au lieu du seul cas Inert Anchorstone).
- Nouvel évènement observé `manifestation_entered_limbo` (Otranth retire un compteur Shackle ; Support à zéro ; dans l'Interzone au début du tour : -10 points et compteurs restaurés via `restore_source_counter`).

### Lot 9 (résultats de confrontation et Support depuis Stalemate)

- Venerable Viper cible un adversaire à sa défaite : seules les manifestations déjà présentes dans son Interzone perdent leurs effets et deviennent non remplaçables jusqu'à la fin du prochain tour.
- Referen-Doom crée à sa défaite autant d'essences arc-en-ciel que sa puissance actuelle au moment de la résolution.
- Nubilung peut être joué en Support depuis Stalemate en passant par la Pile. Son origine est conservée pendant la résolution, ce qui déclenche son +2 temporaire jusqu'à la Résolution ; une victoire en Support l'exile via la règle générique `supportWinDestination`.

### Lot 10 (limites d'usage, coût des Volontés, mise en Stalemate)

- Grudge Weaver : compteur « Grudge » à chaque confrontation perdue (déclencheur `player_loses_confrontation` depuis l'Interzone) ; retirer 2 compteurs (`removeCountersFromSource`) donne Support jusqu'à la fin du tour.
- Thornmaster : nouveau champ de capacité `useLimit` (nombre maximal d'utilisations par carte sur le champ, suivi dans `item.abilityUses`) ; perdre 5 points ajoute un compteur de puissance, 5 fois au plus.
- Cognitive Fog : passif `increase_will_tribute` ; `rules_tribute_requirements` (serveur) et `rulesActionPaymentDraft` (client) ajoutent une Essence Vide à toutes les Volontés imprimées, quel que soit leur contrôleur.
- Résultat `stalemate_confrontation` (`scope` : `all` ou `winner`, `lockZone`, `lockSupportEntries`) : Pin Down met toute la Zone de Confrontation en Stalemate et verrouille les entrées en Support ; Static Scuttler (perte) met en Stalemate les manifestations du gagnant. `lockZone` pose `zoneLockTurn` : l'objet ne retourne pas en Interzone au nettoyage, ne peut pas entrer en Support et n'est pas déplaçable par `move_target` jusqu'à la fin du tour (`rules_item_zone_locked`).
- Duel Honorably (partiel, complété au lot 11) : verrou des entrées en Support automatisé (Volonté jouable avant la Révélation) ; la neutralisation en payant {H}{H} depuis la Pile reste manuelle.

### Lot 11 (les six cartes partielles)

- Kox : texte « cannot enter the Confrontation Zone. » → drapeau `cannotEnterConfrontation` (refusé en Première Manifestation, en Support et depuis la main) ; « construction limit is increased by N points » → `constructionLimitBonus`, lu par `validate_tournament_deck(limit_bonus=…)` (serveur) et `deckImportPointLimit` (client). Passifs `construction_limit_bonus` et `cannot_enter_confrontation` dans `card-abilities.json` pour le registre.
- Censor et Martyrize : champ de capacité `additionalCost: "exile_hand_manifestation"`. `declare_rules_action(cost_card_id=…)` valide la Manifestation de la main (étape client `cost_card`, champ `costCardId`), l'exile à la déclaration (`action.cost.revealedCard`) ; la résolution (`hand_manifestation_choice`) utilise cette carte : Censor détruit la cible si sa puissance de base est ≤ celle de la carte révélée, Martyrize pioche autant puis s'exile (`resolveSourceTo: "exile"`).
- Rogue Tadpole : après le retour des Manifestations de l'Interzone sur le dessus des decks, chaque propriétaire ayant au moins deux cartes ordonne les siennes (choix `deck_reorder` enchaîné via `_queue`, `rules_next_deck_order_choice`).
- Atavic Volatility : capacité activée « retirer 5 compteurs Coil » → résultat `each_player_stalemate_own_confrontation` ; chaque joueur ayant plusieurs Manifestations en Confrontation choisit la sienne (choix `pick_own_item`, un joueur après l'autre).
- Duel Honorably : résultat `unless_opponent_payment_lock_support_entries` (choix `effect_payment` pour l'adversaire : payer {H}{H} neutralise le verrou du Support, refuser l'applique). Le paiement est demandé à la résolution, ce qui revient au même qu'un paiement pendant que la Volonté est sur la Pile puisque personne d'autre ne peut agir entre-temps.

### Langage visuel des actions automatisées

- Ciblage en cours : réticule cyan sur les seules cibles valides et trajectoire courbe animée depuis la carte source. Le clic produit un verrou bref ; il confirme l'intention, pas encore la résolution.
- Mouvement confirmé : une copie visuelle de la carte suit une courbe entre son origine et sa destination. L'impact final reste attaché à la zone réellement modifiée.
- Destruction : condamnation de la carte, rupture en fragments, puis aspiration vers le Limbo. Ce mouvement est distinct d'une défausse ou d'un simple changement de zone.
- Pile : une impulsion bleue signale l'ajout ou le déclenchement ; une impulsion verte signale la résolution. Les libellés restent lisibles à côté de la Pile.
- Effets continus : la pose d'un effet relie brièvement source et cible puis appose un sceau. Le lien persistant reste discret et ne s'anime qu'au survol ou au focus du marqueur d'effet ; sa disparition produit une dissolution courte.
- Les animations sont décoratives et pilotées par les états confirmés du serveur. Avec `prefers-reduced-motion`, les déplacements sont supprimés mais les contours, libellés et changements d'état restent visibles.

### Lot 12 (dix cartes du set Beta)

- Trim the Excess / Equalize : résultat `set_field_power` (`mode` `base` ou `lowest_base`) → un effet `power_set_maximum` jusqu'à la fin du tour sur chaque Manifestation du champ (la puissance fixée ignore les modificateurs ultérieurs).
- Soup : passif `persistent_wills_as_ephemeral` ; `rules_action_timing_error(player_id=…)` (serveur) et `rulesPersistentWillsAsEphemeralClient` (client) autorisent les Volontés persistantes en Réaction / Résolution tant que Soup est dans l'Interzone du joueur.
- Altruistic Inflorescence : effet continu `grant_support` (tant que la source et la cible sont sur le champ, lu par `rules_card_can_enter_support`) ; changement de cible en Phase de Fin via `retarget_source_effect`.
- Logos : résultat `stalemate_targets` (`includeSource`, `lockZone`) ; victoire = une Manifestation d'Interzone choisie, défaite = Logos et une Manifestation gagnante ; toutes gelées (`zoneLockTurn`) jusqu'à la fin du tour.
- Imgurd : nouvel évènement observé `power_lost`, émis quand un effet ajoute une puissance négative (`create_rules_ongoing_effects`, `add_power_counter_target`).
- Stoic Snoozer : résultat `grant_support_entry_bonus` (`supportEntryBonuses`, appliqué par `mark_rules_support_entry`) si le joueur a perdu la confrontation précédente.
- Jurat : `pay_rules_tribute` consigne les Manifestations payées en Tribut (`tributeLog`) ; une victoire crée un souvenir `return_from_limbo_end_turn` par carte, qui les rend à leur propriétaire en fin de tour.
- Glabron : résultat `stalemate_target_grant_source_support`. Le Stalemate est appliqué à la résolution et non comme coût payé avant la Pile.
- Everspring : compteurs « Tear » à chaque défaite ; retirer 3 compteurs exile jusqu'à trois Manifestations du Réceptacle adverse (nouvelle contrainte de cible `maxTotalPoints`, 60 points au total).

### Lot 13 (dix cartes du set Beta)

Registre : 359 automatisées / 0 partielle / 91 manuelles.

- Tribut hors de la main : `rules_action_payment` accepte maintenant trois sources. Forgotten Pile (`canPayTributeFromLimbo`) paie depuis le Limbo sans compteur Formula et est exilée ; Orator of the Absurd (passif `field_manifestations_as_tribute`, pour tous les joueurs) permet de payer avec ses propres Manifestations de la Zone de Confrontation et de l'Interzone (jamais les jetons ni la source elle-même) ; le client (`rulesActionPaymentDraft`) propose les mêmes candidats.
- Solar Apparition : drapeau `tributeExtraPowerLoss` (dérivé du texte). `rules_tribute_extra_power_loss` lit `cost.tributeCardIds` d'une Volonté éphémère et retire 2 de plus à chaque effet `power_modifier` négatif qu'elle crée (`create_rules_ongoing_effects`).
- Zum : capacités activées `usePerTurn` (mémorisées dans `abilityTurnUses` de la source) et `supportWhenAllUsed` ; quand les trois effets ont servi dans le même tour, la source reçoit `supportUntilTurn`.
- Twist the Soul : résultat `play_vessel_target_as_support` (cible `zone_card` du Réceptacle avec `container: "self"`). L'objet porte `supportReturn` ; en fin de confrontation, `begin_rules_confrontation_cleanup` le remet dans le Réceptacle de son contrôleur s'il gagne, sinon dans la main de son propriétaire (Égalité comprise).
- Shymon : résultat `lock_next_turn_draws` (liste `drawLocks`) ; `draw_rules_cards` ne pioche plus hors Phase de Récupération pour le joueur visé pendant le tour suivant.
- Traumatize : résultat `reveal_hand_discard_choice` (coût de 5 points à la résolution) ; choix `reveal_hand_discard` où le lanceur voit la main entière (`cardIds`, visible des deux joueurs) et choisit la carte à défausser.
- Damage et Echo of the Wilds : résultat `distribute_power` (total, signe). Les cibles sont choisies à la pose (1 à 3, chacune reçoit au moins 1) ; seul le cas « 2 cibles pour un total de 3 » demande un choix `pick_distribution_extra` (la cible qui reçoit le point en plus).
- Unruly Flail : condition `opponent_will_on_stack_targets_confrontation` (`supportFromHandCondition`, serveur et `rulesSupportFromHandAvailableClient`) et déclencheur à l'entrée en Support depuis la main qui neutralise une Volonté adverse choisie avec la nouvelle contrainte de cible `targetsConfrontationManifestation`.
- Limites connues : les nouveaux écrans (répartition, main révélée) et le tribut depuis le Limbo ou le champ ne sont testés que côté serveur et par le test frontend général, pas manuellement dans un navigateur ; Damage choisit la répartition à la résolution pour le cas à deux cibles.

## Lot 14 (Tut, Ababash, Expansive Ponderer, Zam-za, Alakazim, Palgonphio, Tricephalous Oil-Dog, Inspired Nimbus, Zizek, Obtrusive Mass)

- `reorder_top_decks` accepte `topCount`/`bottomCount`, `extraSide` (`exile`|`hand`), `extraMin`/`extraMax` et `targetPlayer`; le client envoie `extra` dans chaque groupe. Le choix `look_top_pick_hand` est dans `RULES_AFTER_CHAIN`.
- Surcharge de puissance de tribut: `tribute_power_override_for_card` (main.py) et `rules_tribute_power_override` (session.py), conditions `two_wills_played_this_turn` et `lost_or_stalemate_previous_turn`. Exposée au client via `rulesEngine.tributePowerOverrides`.
- Passif `excess_essence_as_hollow` (Alakazim). Permission générique `grant_free_will_play` (`anyWill`, `noTribute`).
- Zizek: `confrontationEntryLimboWills` et `retainsExcessEssence` (excès conservé sous la clé `(tempérament, "retained")`).
- Obtrusive Mass: `redirect_opponent_targeting_to_source` via `rules_redirect_targets`. Les déclencheurs ciblés automatiquement NE sont PAS redirigés (limite connue).
- Correctif client: `topCount`/`bottomCount` à `null` ne forcent plus tous les sélecteurs sur "bottom".
- Registre: 369 automated / 0 partial / 81 manual.

## Lot 15 (Regurgitating Catacomb, Sandokaron, Bivalv, Swindley, Timid Brain, Brabataba, Unreachable Pillar, Quper, Tax of the Malignant, Eorthoda)

- Coûts depuis la main: `sourceCost` (`discard_source`, `stalemate_source`) payé à la déclaration dans `declare_rules_action` (Bivalv, Swindley); `additionalCost: "discard_hand_will"` (Timid Brain) réutilise l'étape client `cost_card`, filtrée sur les Volontés.
- Timid Brain: l'effet n'accorde que la permission de jouer en Soutien (phase Réaction). Le joueur joue ensuite la carte lui-même.
- Brabataba: passif `vessel_manifestations_as_tribute`. Références de tribut `receptacle|<cardId>`, comptées comme {T}, exilées chez leur propriétaire.
- Unreachable Pillar: passif `vessel_protected_no_effects` (`rules_vessel_locked`). Les cartes du Vessel ne sont plus ciblables par l'adversaire et leurs déclencheurs (`beginning_of_turn`, `vessel_revelation`, `enters_zone` dans le Vessel) sont ignorés. Les effets sans cible qui touchent le Vessel d'un adversaire ne sont pas filtrés.
- Quper: passif `sacrifice_at_power` (seuil, bonus) évalué dans `resolve_rules_state_actions`; le bonus +2 est un effet continu `power_modifier` sur les Manifestations de la Zone de Confrontation du contrôleur.
- Tax of the Malignant: nouvel événement de déclencheur `resolution` (début de `resolution_effects`, `queue_rules_resolution_field_triggers`) et résultat `lose_excess_essence_or_points`. Les jetons d'essence en excès portent maintenant `isExcess`.
- Sandokaron: déclencheur `sourceCounterMax` (exil sans compteur en fin de tour). Regurgitating Catacomb: ne gère que l'exil sur victoire (pas le remplacement « quitte la Zone de Confrontation par un effet »).
- Eorthoda: résultat de déclencheur `protect_related_will` (via `relatedActionId`). L'action posée sur la Pile reçoit `cannotBeNeutralized` (bloque `neutralize_stack_action` et le mode `neutralize` de `counter_stack_action_unless_payment`, pas l'annulation `cancel`); une Volonté Persistante reçoit en plus une Protection contre les adversaires jusqu'à la fin du tour, transférée à la carte quand elle entre sur le terrain.
- Registre: 379 automated / 0 partial / 71 manual.

## Lot 16 (Powerful Pidue, Gorte, Bonzai, Numbi, Guart, Malaleuco, Gomeran, Simulacrum of Clemency, Spiked Pit, Empathic Mask)

- Mains révélées: `can_view_zone` accepte désormais la zone `hand` via `rules_hand_revealed_to`. Gorte (passif `reveal_opponent_hands`) révèle la main des adversaires de son contrôleur à tous les joueurs tant qu'il est actif; Bonzai (`vessel_reveals_owner_hand`, dans un Vessel) montre la main du propriétaire du Vessel à son propriétaire pendant `confrontation_choose` et `confrontation_before_revelation` seulement. Le client affichait déjà `hand.cards` d'un adversaire (éventail « connu »).
- Gorte: capacité `anyPlayer` + nouveau drapeau `opponentOnly` (refusé côté serveur dans `rules_action_source` et masqué côté client dans `rulesActivatedActionDraft`). Résultat `disable_source_effects` (`effectsDisabled`, définitif).
- Numbi: `chain_from_zone` (main, adversaires) avec `afterChain: boost_controller_first` (valeur 2 jusqu'à la fin du tour sur la Première Manifestation du contrôleur). Si l'adversaire ne peut pas Enchaîner, la preuve de main existante (`handProof`) sert de « il montre sa main ».
- Guart: nouvel événement observé `power_gained` (effets `power_modifier` positifs et compteurs de puissance), symétrique de `power_lost`. Les gains d'un adversaire sont filtrés par `eventController`.
- Malaleuco: résultat `move_hand_source_to_interzone` (vérifie la place dans l'Interzone à la déclaration et à la résolution). La copie de Volonté est le `copy_stack_action` existant.
- Gomeran: résultat `create_event_token_copy_in_support` (jeton copie en Soutien via `create_rules_token_copy`). Les copies sont des jetons, donc pas de boucle. Le jeton déclenche ses propres effets d'entrée et ceux des observateurs d'entrée en Soutien; le filtre `eventNonToken` empêche Gomeran de réagir aux jetons.
- Simulacrum of Clemency: résultat `clemency_choice` → choix `clemency_choice` pour le joueur adverse (`allow`/`neutralize`). Neutraliser retire la Volonté de la Pile (`counter_rules_stack_action`) et épuise Simulacrum; si la Volonté ne peut pas être neutralisée, Simulacrum gagne quand même les points. Passif `no_effects_while_exhausted` dans `rules_item_effects_active`.
- Spiked Pit: passif `interzone_entry_penalty`, appliqué par `apply_rules_interzone_entry_penalty` (depuis `mark_rules_interzone_entry` et le placement manuel). Le malus est un compteur de puissance -1 qui reste tant que la Manifestation est sur le terrain (le texte ne donne pas de durée).
- Empathic Mask: `ongoingEffect` `temperament_override` (tempérament de base choisi, jusqu'à la fin du tour), appliqué dans `rules_manifestation_characteristics`.
- Powerful Pidue: cinq déclencheurs `card_played` par tempérament (Volonté ou Manifestation de l'adversaire pendant `confrontation_before_revelation`/`confrontation_reaction`). Filtre `playedAs: support_or_hand_will`: une Manifestation compte seulement si elle entre en Soutien, une Volonté seulement si elle est jouée depuis la main.
- Version des assets: `20261010-rules-beta-110`.
- Registre: 389 automated / 0 partial / 61 manual.

## Lot 17 (Poopom, Mejik, Cradle the Putrescence, Sangen, Asciugoth, Dol, Balance of the Spirit, Denegath, Katun, Zaguor)

- Nom de carte déclaré: choix `declare_card_name` (client: champ avec liste de suggestions, envoie l'id d'une carte; le serveur compare les noms via `card_labels`). Résultats `declare_name_top_card_power` (Poopom: +4 jusqu'à la fin du tour si la carte révélée a le même nom, sinon elle est défaussée) et `declare_name_search_deck` (Mejik: première carte du même nom du deck cible défaussée puis deck mélangé; le mélange a aussi lieu si rien n'est trouvé).
- Cradle the Putrescence: `destroy_vessel_target_owner_sacrifices`. Le choix `pick_own_item` porte maintenant un `purpose` (`stalemate` ou `sacrifice`); le propriétaire de la carte détruite choisit la Manifestation qu'il sacrifie (automatique s'il n'en a qu'une).
- Sangen: passifs `win_to_opponent_interzone` (au nettoyage de la confrontation, la carte passe dans l'Interzone adverse, contrôlée par lui), `unreplaceable_in_interzone`, `interzone_allies_penalty` (-1 aux autres Manifestations de l'Interzone de son contrôleur) et `final_interzone_points` (+25 en fin de partie pour son contrôleur, dans `rules_end_game_points`). La partie « cible un adversaire » est implicite: il n'y a qu'un adversaire.
- Asciugoth: passif `entering_manifestation_becomes_hollow`, appliqué dans `queue_rules_manifestation_entry_watchers` (essence du tempérament d'origine pour son contrôleur, puis `temperamentOverride: hollow`). Les jetons créés par `create_rules_token_copy` sont aussi touchés (`apply_rules_entering_manifestation_replacements`, une seule fois par carte).
- Katun: nouvel événement observé `manifestation_left_by_effect` (retrait du terrain par effet via `_rules_remove_field_item_by_effect`, sortie de Limbo ou de Vessel via `move_zone_card_by_effect`). `take_zone_card` mémorise les cartes sorties d'un Vessel (`leftVesselCards`) et le filtre de déclencheur `sourceLeftVessel` choisit 5 ou 10 points. Les sorties « par les règles » (résolution de confrontation) ne comptent pas.
- Balance of the Spirit: passif `balance_points` géré dans `adjust_rules_score` (`rules_balance_redirect`). Le total d'un joueur est ses points d'effet plus les points des cartes de son Vessel. En cas d'égalité, rien n'est redirigé.
- Denegath: `return_first_then_chain` (Première Manifestation renvoyée en main, jouable seulement au tour suivant via `playRestrictions`, puis Chaînage depuis la main).
- Dol: `chain_from_zone` accepte `zone: receptacle`: les cartes que le joueur possède dans n'importe quel Vessel (`rules_chain_candidates`, conteneur mémorisé dans le choix). Exil si la carte gagne. Si elle quitte la Zone de Confrontation par un effet (`_rules_remove_field_item_by_effect`), elle retourne dans le Vessel d'origine (`returnToVesselId`).
- Zaguor: `exile_source_take_control_to_interzone`, déclencheur optionnel à la victoire; une seule capacité avec cible dans le Vessel adverse OU dans l'Interzone adverse (`zones: [battlefield, receptacle]`). Refusé si l'Interzone du joueur est pleine sans pile possible (Zaguor n'est alors pas exilé).
- Test frontend: l'ancien test « Volonté manuelle » ne trouvait plus de Volonté non automatisée avec une cible Manifestation; il supprime maintenant les capacités encodées de la carte choisie.
- Version des assets: `20261010-rules-beta-111`.
- Registre: 399 automated / 0 partial / 51 manual.
