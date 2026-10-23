# Audit des événements et déclenchements après 139.42

Passe du 23 octobre 2026. Corrections intégrées à la version 139.42 à la demande du joueur, en complément de la première publication de cette version.

## Règles retenues

- Une variation de puissance bloquée par un plafond ou un plancher n'est pas un gain ou une perte réelle. Une variation partielle produit un seul événement par Manifestation concernée.
- L'expiration normale d'un bonus n'est pas une réduction due à une carte ou un effet (arbitrage du joueur). Le coût d'activation **Reduce** est également exclu, conformément à sa définition dans le livret, page 39.
- Une destruction remplacée par suspension ou exil ne déclenche pas « une Manifestation est détruite ». La sortie de zone a néanmoins lieu et peut déclencher Katun (arbitrage du joueur).
- Katun réagit aux effets des deux joueurs selon son texte corrigé. Les mouvements naturels de fin de Confrontation ne sont pas des sorties causées par un effet de carte.

## Corrections

- Les événements de puissance comparent maintenant les caractéristiques effectives avant et après la modification. Berta, les minimums et les maximums ne provoquent plus de faux déclenchements de Guart, Imgurd ou Buddhan.
- Les écritures directes de puissance et les ajouts d'effets contournant la fabrique commune passent par la même observation : Humiliate, résultats de dés, effets de Chain, choix de puissance, distribution, compteurs de puissance et autres résultats dédiés. Les compteurs de ressources seuls ne produisent aucun événement de puissance.
- Copies, doublements, puissance fixée, Cleanse et déplacement explicite d'un effet continu observent leur changement réel. Réactiver une copie identique ne produit rien ; changer sa valeur compare à la copie précédente, sans annoncer un gain artificiel depuis la puissance imprimée.
- Katun voit désormais les sorties du champ ou des Limbes remplacées par une suspension, ainsi que la disparition d'une copie par effet. La même carte n'est pas annoncée deux fois. Un réordonnancement à l'intérieur des mêmes Limbes ne compte pas comme sortie.
- Les arrivées réelles dans les Limbes sont enregistrées au point commun d'insertion, après détermination de la destination. Les sacrifices et autres arrivées précédemment omis sont observés une fois ; une arrivée remplacée par exil ou suspension ne crée aucune entrée fictive.
- Détruire une Volonté ne produit plus `manifestation_destroyed`. Envoyer une Volonté dans un Réceptacle ne produit plus `manifestation_enters_opponent_vessel`.
- Le regroupement « une ou plusieurs cartes défaussées » reste distinct des entrées individuelles de chaque Manifestation dans les Limbes. Une seconde collecte des événements ne rejoue pas les déclenchements déjà consommés.

## Vérification

- `tests/test_observed_events_audit.py` : 27 tests ciblés, incluant les exceptions d'expiration et de Reduce, les effets bloqués, les remplacements, les sacrifices, les types de cartes et les événements groupés.
- `tests/test_observed_events_integration.py` : 2 tests avec le vrai serveur WebSocket. Une perte réelle déclenche Imgurd une seule fois, y compris après reconnexion ; Berta empêchant la perte ne crée aucun effet ni choix. Les joueurs gardent une réponse légale pour rendre l'état intermédiaire observable avant les passages automatiques de la Pile.
- Suite Python complète : **874 tests réussis**, incluant les 29 régressions de cette passe et les contrôles de catalogue/scénarios.
- Régressions générales de l'interface dans Chrome : **réussies**.

L'audit porte sur les événements produits par ces opérations et les cas voisins reproduits ; il ne constitue pas une preuve de toutes les combinaisons possibles du catalogue.
