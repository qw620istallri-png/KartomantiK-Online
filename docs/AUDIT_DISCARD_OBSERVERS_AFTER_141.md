# Observateurs de défausse et destinations remplacées

Le créateur confirme le 28 octobre 2026 qu'une défausse de Main ou de Deck reste
une défausse lorsque BOB suspend la carte ou qu'un remplacement l'exile. Les
observateurs réagissent à l'action, pas au nombre de cartes défaussées ensemble.
Une pioche ou un mélange suspendu n'est pas une défausse. Une entrée au Limbo
doit, quant à elle, avoir réellement eu lieu.

L'arbitrage `replaced-discard-observers` est conservé dans
`audit/rule-decisions.json`. Les contrats manuels de `audit/discard-observers.json`
figent les textes et les résultats attendus indépendamment des capacités livrées.

## Défauts reproduits et corrections

La [reproduction avant correction](../reports/systematic-audit/discard-observer-followup/before.json)
conserve **168 méthodes : 118 réussites et 50 échecs**. Les mouvements remplacés
vers Suspension ou Exil ne produisaient pas les événements de défausse requis.
Le malus de Kanon ignorait aussi les Volontés dont la défausse était remplacée.

Le traitement commun des remplacements enregistre désormais une défausse après
un mouvement réussi si l'instruction d'origine était Main/Deck vers Limbo.
Il distingue le Deck pour Makaboon. Les mouvements ordinaires et le remplacement
de Tenebro en Support conservent leur chemin existant, sans événement ajouté
deux fois. Aucun événement de fausse arrivée au Limbo n'est créé.

Kanon compte toutes les Volontés effectivement défaussées pour répartir ses
malus. Sa liste publique historique `discardedCardIds` reste limitée aux cartes
déplacées normalement au Limbo ou en Support : les identités des cartes
suspendues ou exilées privées ne sont pas ajoutées au journal adverse.

L'ancien test négatif de Kanon a été révisé conformément à cet arbitrage. Son
identifiant historique est conservé pour maintenir les liens des preuves ; un
commentaire et la preuve actuelle signalent explicitement que son ancienne
interprétation « pas de défausse ni de malus sous BOB » est remplacée. Les
anciens rapports conservent leurs résultats et empreintes historiques.

La première suite globale après correction réussit 2 910 tests sur 2 911.
Son seul échec est une autre assertion héritée : Traumatize considérait encore
qu'une défausse suspendue n'était pas un événement de défausse. Cette assertion
est mise à jour selon le même arbitrage ; les 20 tests du module repassent.
Le résultat initial est conservé dans `full-before-legacy-ruling-update.json`,
séparément de la validation globale finale.

## Clauses sélectionnées

| Carte | Résultat vérifié |
|---|---|
| Forfog | L'adversaire défaussant perd 5 points, une fois par action |
| Pale Entity | Le contrôleur gagne 5 points à la défausse d'un joueur |
| Ehgog | Une cible adverse reçoit −1 jusqu'à la fin du tour |
| Conflux of Catastrophe | Une cible adverse reçoit −1 tant qu'elle reste sur le champ |
| Buddhan | Une action de défausse retire un marqueur Quiet |
| Makaboon | La défausse du Deck demande une défausse supplémentaire de Main |
| Otranth | Chaque arrivée réelle d'une Manifestation au Limbo retire un Shackle ; aucun sur suspension/exil/Support |
| Kanon | Chaque Volonté défaussée par son remplacement compte pour un malus de −1 |

Les **168 scénarios de famille** utilisent les mouvements de production et le
résultat de défausse multiple du Deck. Ils couvrent les deux origines, les
destinations ordinaires, Suspension et Exil, les deux choix d'ordre BOB/exil,
les remplacements optionnels de Tenebro, les lots de trois cartes, le contrôleur
actuel et les sources couvertes, désactivées ou en Impasse. Les scores,
puissances, durées et marqueurs attendus sont vérifiés selon
la clause. Les faux événements issus d'une pioche, d'un mélange, d'un tribut
ou d'un mouvement refusé sont exclus. Une seconde collecte n'ajoute pas le même
déclenchement. La défausse de Main de Makaboon ne boucle pas son effet de Deck.

Les **dix parcours WebSocket** vérifient chaque clause avec un client incrémental
et un client ancien. La plupart des effets producteurs sont des entrées de Pluff
préparées explicitement, suivies de son véritable effet de défausse de Deck.
Ils ne certifient pas une déclaration ou une entrée complète de Pluff. Kanon
utilise une vraie déclaration payée de Ponder, puis deux ordres de remplacement,
une reconnexion et la répartition de deux malus. Les choix de cibles d'Ehgog et
Conflux passent par le protocole. Otranth a deux parcours : Limbo réel et BOB.
La phase reste stable et son pilote automatique est isolé.

Le banc a été ajusté avant la reproduction conservée pour reconnaître une
action attendant déjà son choix de cible, au lieu de considérer son absence de
la liste retournée comme un déclenchement manquant. Les cas de Main de Makaboon
utilisent bien la Main comme producteur négatif. Ces ajustements ne constituent
pas des défauts supplémentaires du jeu.

## Preuves et limites

Le lot comporte **178 méthodes** au total. La commande
`python tools/card_discard_observer_audit.py` écrit les
[preuves par clause](../reports/systematic-audit/discard-observer-followup/clauses.json).
Le [registre d'exécution](../reports/systematic-audit/discard-observer-followup/EXECUTIONS.md)
et `evidence.json` relient reproduction, tests, arbitrage, empreintes et compteur.

La validation globale finale réussit **2 911 méthodes Python distinctes**, sans
échec ni test ignoré, et les trois suites client, dont 608 scénarios de parité.
Le registre strict passe de **120 à 121/450 (26,9 %)**. Buddhan est la seule
nouvelle carte unique ; les autres gagnent des branches vérifiées. Au moins une
clause sélectionnée est prouvée par carte, sans certification exhaustive.

Les autres capacités de ces cartes ne sont pas certifiées. Les effets propres
aux cartes défaussées, notamment Tombloom et Nghoul-ong hors du Limbo, restent
un audit séparé. Les lots de trois cartes représentent une seule action ; des
instructions de défausse distinctes avant une même collecte ne sont pas couvertes.
Les parties complètes, tous les croisements de cartes, un redémarrage du serveur,
Safari, les appareils physiques et de nouveaux parcours UI de carte restent
hors de ce lot. Aucun changement client, VFX, version, commit ou push.

Les profils d'exil posent directement la mémoire de Quasimillenary, y compris
sur des cartes du Deck. Ce sont des contrôles du chemin des remplacements ; ils
ne démontrent pas que ces états particuliers sont atteignables en partie
automatique. Le parcours réseau de Kanon utilise également cet état contrôlé.
Les branches ordinaires et de BOB restent distinctes de cette limite ; aucune
certification d'une combinaison jouée Quasimillenary/Kanon n'est revendiquée.
