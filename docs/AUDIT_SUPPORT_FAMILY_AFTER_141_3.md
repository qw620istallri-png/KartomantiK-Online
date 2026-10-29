# Lot de six cartes : Support, jetons et persistance

Ce lot reste local, après la publication de la 141.3. Il ajoute des preuves de clauses sélectionnées pour six cartes, sans certifier toutes leurs interactions.

| Carte | Comportements vérifiés |
| --- | --- |
| Unite Impulses | Deux essences phlegmatiques ; seules les Manifestations présentes dans son Interzone à la résolution gagnent Support ; expiration en fin de tour ; aucun déplacement automatique. |
| Rally | Deux essences phlegmatiques et essences supplémentaires {H} ; nombre exact de jetons de puissance 1 {H} ; paiement par plusieurs tributs et utilisation de leur excédent ; aucune création avant résolution. |
| Mirror the Impulse | Trois essences vitreuses ; copie en Support d'une Manifestation actuellement contrôlée sur le champ ; puissance et tempérament de la cible contrôlée ; propriété du jeton ; invalidation d'une cible devenue adverse. |
| Reforging Fate | Trois essences mélancoliques ; les deux Limbos ; arrivée en Support sous son contrôle ; remplacement par BOB ; mémoire d'exil à la victoire ; disparition puis retour de la cible. |
| Persist | Deux essences vitreuses ; cible en Zone de Confrontation ; le vainqueur reste Première Manifestation, le perdant ne reste pas ; expiration et Cleanse. |
| Incinerate | Quatre essences colériques ; historique d'entrée en Support ce tour ; Protection, Immunité et Impasse ; destruction/remplacement ; disparition des jetons sans carte fantôme au Limbo. |

Le texte du catalogue et ses empreintes sont épinglés dans `audit/support-family.json`. Les coûts, comptes, destinations et durées attendus sont des oracles littéraux dans les tests.

## Corrections

Les jetons et copies n'avertissaient pas uniformément les observateurs d'entrée de Manifestation, tels que Blossom. Le chemin commun collecte maintenant ces déclenchements avec les effets d'entrée propres aux copies. Les créations multiples sont regroupées avant le choix d'ordre simultané. Le choix du nombre de jetons de Stampeding Brood transmet également ces déclenchements à la pile.

L'historique d'entrée en Support est enregistré seulement pour une arrivée effective en Zone de Confrontation. Les jetons créés dans l'Interzone par Stampeding Brood conservent la capacité Support indiquée par leur texte sans être considérés comme déjà entrés en Support.

Reforging Fate conservait une destination d'exil sur l'objet de terrain, sans la mémoire d'effet correspondante. L'effet crée maintenant cette mémoire : elle survit à Cleanse et aux passages par la Main ou le Limbo, se rattache à la nouvelle instance de terrain, puis s'efface au Deck ou à l'Exil. Un départ remplacé par BOB reste signalé une seule fois aux observateurs de sortie.

Incinerate pouvait détruire une carte dans l'Impasse et ignorer l'Immunité. La destruction globale exclut maintenant ces cas. La Protection ne bloque pas cet effet global sans cible.

## Preuves et limites

- **83 cas passent** : 73 méthodes unitaires et dix parcours à deux connexions WebSocket réelles.
- Les déclarations payées utilisent les capacités du catalogue ; coûts et absence de résultat prématuré sont vérifiés avant la résolution.
- Les effets déclenchés par Blossom restent sur la pile : les compteurs changent seulement après leur résolution. Le cas Rally avec deux jetons teste le choix d'ordre via les sockets.
- Huit routes supplémentaires de génération sont exercées par un test à sous-cas : Buuz, Atavic Welcome, Jija, Mamelath, Horned Augustus, Recall the Consumed, Lilitha et Stampeding Brood. Leurs entrées, contrôleurs, comptes de jetons et comptes d'observateurs sont vérifiés. Ce sont des interactions ciblées, pas huit certifications supplémentaires de cartes ni leurs parcours de paiement complets.
- **90 tests voisins passent**, concernant Support, Cleanse, copies, événements observés et remplacements.

Le premier relevé `before.json` comporte notamment une attente erronée du banc : Reforging Fate déclenchait déjà Blossom, mais le test lisait son compteur avant de résoudre l'effet sur la pile. Le premier scénario Cleanse supposait aussi le maintien du contrôle d'une carte adverse après nettoyage ; il utilise maintenant une carte de son propre Limbo pour isoler la mémoire. Ces attentes corrigées ne sont pas comptées comme défauts du jeu. Les erreurs de méthode du tout premier essai étaient aussi dans le banc. Les relevés séparés des huit générateurs et du choix de nombre conservent les échecs reproduits avant leurs corrections.

Les cibles et états initiaux sont des fixtures contrôlées. Les copies de cartes déjà modifiées, animées ou elles-mêmes copiées ne sont pas certifiées par ce lot. L'avance automatique des phases est désactivée dans les dix parcours réseau afin d'isoler la pile. Aucun nouveau contrôle de navigateur, d'illustration distante ou d'appareil physique n'est ajouté.

Validation finale : **3325/3325 tests Python passent**, aucun échec ni test ignoré ; **608 scénarios de parité** client/serveur passent. Le registre strict atteint **148/450 cartes (32,9 %)**, soit six nouvelles cartes avec clauses sélectionnées prouvées et 302 hors registre. Les preuves ciblées, la régression complète et le registre ont le même digest courant. **Aucun push.**
