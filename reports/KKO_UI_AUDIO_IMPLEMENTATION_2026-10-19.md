# KKO — essences, ciblage et feedback sonore

Date : 19 octobre 2026

## Fonctionnement livré

- Le menu inférieur ne crée plus d’essence colorée. Son bouton `⊕` sert uniquement aux compteurs neutres nommés.
- Le petit `+` d’essence est placé à gauche et hors du cadre du total de CZ. Il est cliquable au clavier, au clic et au survol, en UI normale comme en UI bêta.
- Un clic sur un tempérament crée une essence de valeur 1 via le serveur. Un clic sur le pool agrégé retire une unité ; la dernière unité supprime le jeton serveur.
- En UI bêta, les essences de tempérament sont masquées sur le terrain et restent visibles dans le pool agrégé. Les compteurs neutres restent visibles.
- Les diagonales ont été retirées du fond de la Zone de Confrontation et restent limitées aux Interzones.
- Lors d’un choix de joueur, seul le côté survolé reçoit le glow. Le glow est nettoyé dès que le choix est résolu ou fermé.

## Banque sonore temporaire

Source : banque Hearthstone locale fournie dans `Sounds (Sorted)`. Ces sons servent de références temporaires en attendant les remplacements originaux.

Le dossier `public/audio/ui/` contient uniquement les 42 fichiers OGG utilisés par le gestionnaire. Les anciens WAV ElevenLabs et le son de survol ont été supprimés.

| Situation | Feedback |
|---|---|
| UI | clic, confirmation, erreur ou action impossible ; aucun son au survol |
| Cartes | pioche, jeu, pose, invocation, destruction et quatre variantes de révélation/retournement |
| Effets | déclenchement, résolution générique, défausse, effet négatif et bonus sur la cible |
| Ressources | gain et dépense d’essence |
| Rythme | retour de priorité au joueur local, nouveau tour et début de partie |
| Confrontation | capture, victoire, défaite et égalité |
| Partie | victoire, défaite et égalité de fin de partie |

Les événements de règles reposent sur `recentLog` et son numéro de séquence : aucun historique n’est rejoué lors de la connexion ou reconnexion. Les sons de priorité et de résultats sont calculés du point de vue du joueur local. Les variantes évitent de répéter immédiatement le même fichier.

## Contrôles automatisés

- UI normale et bêta : position externe du `+`, clic actif, ouverture du sélecteur, création et retrait serveur d’essence.
- UI bêta : essence colorée absente du terrain, compteur neutre présent, diagonales limitées aux Interzones.
- Ciblage joueur : aucun glow avant survol, glow sur un seul côté, nettoyage après résolution.
- Audio : absence de son de hover ; pioche, jeu, révélation multi-variante, invocation, essence, priorité, tour, début de partie, effets, défausse, bonus/malus, capture, confrontation et fin de partie.
- WebSocket : cycle création → décrément → suppression d’une essence sur un vrai serveur de test à deux joueurs.
- Persistance : son activé/coupé et mémorisé dans `localStorage`.


## Correctifs systémiques ajoutés après validation sandbox

- **Tribut hors main** : tous les candidats de tribut provenant d’une zone publique sont maintenant présentés près de la main avec leur zone d’origine. Cela couvre l’Interzone de Solar Apparition, le Limbo et les futures cartes utilisant le même mécanisme.
- **Cibles optionnelles** : un effet `0–N` ne se soumet plus automatiquement lorsqu’il existe des cibles légales. Le joueur peut confirmer zéro carte ou en sélectionner plusieurs. Dissolve and Coagulate fonctionne donc avec 0, 1 ou 2 Manifestations du Réceptacle.
- **Limite de main** : une pioche normale ou générée par un effet ne déclenche plus immédiatement le choix d’excédent. Le contrôle a lieu à la sortie de `end_expire`, après les effets de fin de tour, et les cartes excédentaires vont sous le Deck. Les limites explicitement imposées immédiatement par une carte conservent leur comportement propre.
- **Carte jouée comme un autre type** : « The Slumberer » hérite maintenant de toutes les règles d’une Volonté persistante : aucune Première Manifestation, fenêtre `end_actions`, aucun tribut, arrivée dans la zone des Volontés et compteurs Sleep inchangés.
- **Trap** : le client utilise la fenêtre spéciale de Trap avant les règles génériques des Volontés éphémères. La carte ne reçoit donc plus de surbrillance bleue hors de son moment légal.

## Interface et sons finalisés

- La nouvelle interface est activée par défaut pour un nouveau navigateur. La valeur locale `0` conserve l’ancienne interface via le toggle.
- Le sélecteur rapide d’Essence est réservé au mode manuel. En nouvelle UI il reste ouvert pour plusieurs clics, se ferme au départ du pointeur et passe au-dessus du plateau grâce à sa couche dédiée. En règles assistées, création et dépense manuelles sont masquées et bloquées côté client.
- Les Essences restent masquées sur le terrain dans la nouvelle UI, quel que soit le mode de règles.
- Mapping doux : `UI_MouseClick_01`, `UI_BnetToast`, variantes Trigger/Play/Draw/DismissPoof, `draw_card_into_play`, mouvement vers le Deck et Mana Crystal. Les volumes sont réglés par cue, sans compression. Le retournement utilise quatre paliers selon la puissance imprimée/effective.
- Aucun son de hover. Les anciens fichiers remplacés (`Small_Click`, `ALERT_YourTurn_0v2`, `MinionToDeck_transition`) ont été retirés du dossier livré.

## Validation finale

- `node tests/test_frontend.cjs` : **OK**.
- `python -m unittest tests.test_game_state` : **480 tests OK**.
- `python -m unittest tests.test_card_catalog` : inclus dans la validation ciblée, **40 tests OK**.
- `python -m unittest tests.test_auto_pass tests.test_websocket_integration` : **41 tests OK**.
- `python -m unittest tests.test_sandbox_scenarios` : **8 tests OK**.
- Vérification syntaxique Node de `app.js`, `ui-beta.js`, `audio-manager.js` et du test frontend : **OK**.

Aucun commit ni push n’a été effectué.
### Correctif de clic des essences dans la nouvelle UI

- Le bandeau des totaux et des essences est maintenant porté par une couche interactive dédiée au-dessus du plateau. Le décor du terrain reste derrière les cartes.
- Le test navigateur vérifie désormais le vrai hit-testing avec `elementFromPoint` pour le bouton `+`, une couleur d'essence et la dépense d'une essence. Il couvre ainsi les calques invisibles qui interceptent la souris.
- La version statique passe à `beta 138.10` pour invalider l'ancien CSS mis en cache.
