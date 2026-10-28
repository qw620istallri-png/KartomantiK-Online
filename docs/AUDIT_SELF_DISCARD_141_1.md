# Tombloom et Nghoul-ong : effet propre après défausse

L'arbitrage du créateur confirme que ces deux cartes déclenchent leur effet
quand leur défausse est suspendue par BOB. Leur effet peut exiler leur propre
carte depuis la Suspension ; ce déplacement n'entre ni ne sort d'un Limbo ou
d'un Deck. L'arbitrage est conservé dans `audit/rule-decisions.json`, sous
`self-discard-exile-from-suspension`.

La reproduction initiale conserve 28 tests : 13 réussites et 15 échecs. Les
effets propres n'étaient recherchés qu'à l'arrivée au Limbo. Une source revenue
dans la même zone ou une autre copie portant le même identifiant imprimé
pouvait aussi être exilée à la place de l'objet d'origine. Tombloom annonçait
« exilé » lorsque sa sortie du Limbo était en réalité suspendue.

Un événement individuel de défausse est désormais enregistré pour les cartes
possédant cette capacité. Il conserve l'objet déposé au Limbo, en Exil ou en
Suspension. L'ancien événement d'entrée au Limbo n'ajoute pas un deuxième
déclenchement. Des identifiants privés d'occurrence au Limbo et en Exil
complètent l'identifiant de Suspension déjà disponible. Les extractions et les
réordonnancements dans la même zone respectent ces identités.

Tombloom applique son −2 temporaire à la cible valide, même si sa source a
disparu. Une source déjà exilée est annoncée comme telle. Une source absente
ou réentrée n'autorise pas l'exil d'une autre copie. Nghoul-ong doit effectivement
exiler sa propre occurrence avant d'accorder la permission gratuite ; une source
déjà en Exil ne produit pas d'offre optionnelle inutile. Les actions anciennes
déjà en vol sans référence d'occurrence conservent leur repli historique au Limbo.

Les **33 scénarios unitaires** vérifient les défausses de Main et de Deck sous
BOB, l'Exil par un état résolu de Nullify Reason, deux copies suspendues,
départ/réentrée, autre copie restée au Limbo, réordonnancement, cible invalidée,
aller-retour JSON et refus optionnel. Pour Nghoul-ong, le coût maximal de 3 est
testé à égalité et au-delà, ainsi que l'exclusion d'une Volonté Persistante.
Un vrai Ponder est joué sans tribut grâce à la permission et est exilé après
sa résolution.

Les **quatre parcours WebSocket** commencent par une vraie déclaration de Pray,
sa défausse et ses pioches remplacées par BOB. Ils poursuivent le choix propre
de la carte, une reconnexion, la sélection de cible et les passages de priorité.
Une intervention contrôlée retirant la source avant résolution vérifie son
indépendance et l'absence de permission gratuite sans exil payé. Le parcours
Nghoul-ong réussi joue ensuite Ponder par le protocole et vérifie sa destination.
Le pilote automatique des phases est isolé.

`python tools/card_self_discard_audit.py` exécute les 37 méthodes et écrit les
[preuves par clause](../reports/systematic-audit/self-discard-followup/clauses.json).
La préparation du jeu gratuit restitue la priorité par un vrai passage avant
de déclarer Ponder ; un refus initial dû à la priorité du banc n'est pas compté
comme défaut du jeu. Les deux tests JSON et les trois bornes de coût ont été
ajoutés après la reproduction initiale.

Les producteurs, états de remplacement et changements d'occurrence sont des
préparations explicites ; ils ne certifient pas toutes les séquences adverses
permettant de les atteindre. Les références d'occurrence concernent la source
de ces effets, pas une certification générale de toutes les cibles avec doublons.
Aucun redémarrage du processus, appareil physique, Safari ou nouveau parcours
navigateur propre à ces cartes n'est certifié.
