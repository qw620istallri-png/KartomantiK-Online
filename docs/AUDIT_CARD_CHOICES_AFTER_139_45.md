# Audit des choix de cartes et de leur interface après 139.45

## Périmètre

Suite de l'audit client / serveur : sélections privées et publiques après
résolution, répartition de puissance, tri de cartes, réponses en attente,
reprise après erreur et durée des modificateurs appliqués par ces parcours.
Les corrections précédentes restent présentes dans le même travail local.

## Défauts reproduits et corrigés

### P1 — Trois malus disparaissaient au tour suivant

Les pertes de puissance de Kanon, the Deathdealer, Dulfer, the Touchy et
Shattering the Self utilisaient une expiration de fin de tour. Aucun des trois
textes ne prévoit cette durée. Selon la règle des modificateurs déjà confirmée,
ils persistent tant que la cible reste sur le champ ou en Impasse.

Les trois chemins utilisent désormais `while_target_on_field`. Les tests
passent par la pioche remplacée et les deux choix successifs de Kanon, le choix
de Dulfer et le résultat de Shattering. Ils vérifient le maintien au tour suivant,
la persistance après le départ de Kanon, puis la suppression au départ de la cible.

Contrôle positif : le bonus de Quorum, explicitement limité à la fin du tour,
expire toujours. Les durées imprimées de Poopom, Obelisk of Friendship et Bibi
ont également été comparées à leurs chemins de résolution ; elles sont conservées.
L'exclusion de puissance de Paciphint concerne bien la résolution de la Confrontation.

### P2 — Les mises à jour du plateau effaçaient les décisions en cours

`renderAll` reconstruisait le contenu du choix à chaque état reçu, même lorsque
seuls l'activité ou la position d'une carte avaient changé. Les sélections de
Kanon, les cartes choisies aux Limbes et les déplacements dans les destinations
d'Expansive Ponderer étaient perdus. Les réponses saisies et les ordres locaux
suivaient le même mécanisme.

L'interface conserve maintenant le contenu tant que ses données d'entrée
restent identiques. Un changement de choix, de joueur, de langue, de main ou
d'identité des cartes concernées reconstruit le contenu. La visibilité est
rétablie après une attente d'animation sans perdre le contenu déjà construit.

Les sélections de main sont aussi liées à leur joueur et à la séquence réelle
des cartes. Un ancien index n'est pas envoyé pour une autre carte après un
changement de main.

### P2 — Deux réponses concurrentes pouvaient partir pour le même choix

Plusieurs boutons désactivaient uniquement la réponse cliquée ; une nouvelle
mise à jour les réactivait. Un autre bouton pouvait donc envoyer une réponse
différente avant celle du serveur. Le serveur refusait la réponse périmée,
mais le joueur recevait une erreur après un choix pourtant valide.

Les réponses de l'écran de choix passent par un contrôle commun : identité du
choix, joueur concerné et absence de réponse déjà en attente. Les contrôles
restent verrouillés pendant cette attente, y compris après actualisation.
Un ancien bouton détaché de l'écran ne peut plus répondre au nouveau choix.

Une erreur réactive la décision. Les tris de Deck et les déplacements de
Confrontation conservent leur reprise spécifique et leur distribution courante.
Une déconnexion efface le verrou et les données locales ; l'état reçu à la
reconnexion reconstruit le choix encore attendu par le serveur.

### P2 — Retirer une perte inexistante modifiait une autre carte

Dans la répartition de Kanon, cliquer sur le badge vide d'une carte appelait
`splice(-1, 1)` et retirait la dernière perte attribuée à une autre carte.
L'annulation ne modifie maintenant que les pertes réellement attribuées à la
carte choisie. Le parcours normal d'attribution et d'envoi reste fonctionnel.

## Validation

- `tests/test_choice_modifier_lifetime.py` : trois reproductions de malus qui
  expiraient à tort, plus Quorum comme contrôle de l'expiration volontaire.
- `tests/test_choice_continuity.cjs` : reproductions avant correction sur PC
  1440 × 1000 et mobile 844 × 390, puis sélection conservée, envoi correct,
  réponse unique, reprise après erreur, reconnexion, main réordonnée et ancien
  bouton ignoré. Le déplacement vers la main de Ponderer utilise un vrai geste
  de pointeur, conservé après une mise à jour du plateau.
- Régressions : interface générale, cartes signalées en 139.2, 529 scénarios
  de concordance, Essences blanches et cycle de connexion.
- Tri de Ponderer sur trois tailles / thèmes : aucune zone hors écran ni
  débordement ; contraste des destinations supérieur à 3:1.
- Détecteur Impeccable sur les deux fichiers d'interface modifiés : aucun
  signalement mécanique. Inspection des captures PC et mobile effectuée.
- Suite complète finale : 977 tests Python réussis ; les suites navigateur
  mentionnées ci-dessus passent également.

Points conservés : apparence du plateau, séparation des informations privées,
possibilité de corriger un choix refusé, et contrôle final du serveur.

Cette passe cible les parcours décrits ; elle ne certifie pas toutes les
combinaisons de cartes ni une conformité globale d'accessibilité. Les gestes
de tri au clavier et l'ensemble des langues restent des périmètres distincts.
Les changements restent locaux ; aucune nouvelle publication.
