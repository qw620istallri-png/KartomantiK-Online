# Exécutions — observateurs de défausse

Empreinte finale commune : `c3901379bbb5006f0a16a6ae9598aa15d5618d5180a6f0a4997b78871f894d81`. Lot local après 141, non publié.

- Huit clauses sélectionnées avec attentes indépendantes.
- 168 scénarios de famille et dix parcours WebSocket : 178 méthodes réussies.
- Avant correction : 118 réussites et 50 échecs sur 168 méthodes ; les 50 mêmes
  tests sont retrouvés et réussis dans la suite complète finale.
- Suite complète : 2 911 méthodes Python distinctes réussies, sans échec ni test ignoré.
- Trois suites client réussies : parité des règles (608 scénarios), frontend
  et transport incrémental. Aucun nouveau parcours UI de carte.
- Registre strict : 120 → 121/450 (26,9 %). Seul Buddhan s'ajoute ; les autres
  cartes étaient déjà comptées. Au moins une clause sélectionnée par carte,
  sans certification exhaustive des branches.

Le correctif dans `rules_zone_move_replacement` enregistre la défausse après
un mouvement réussi vers Suspension ou Exil si l'instruction d'origine était
Main/Deck vers Limbo. Les entrées au Limbo ne sont pas inventées. Les chemins
ordinaires et de Support Tenebro ne sont pas doublés. Pioches, mélanges suspendus,
tributs et mouvements refusés restent distincts des défausses.

Kanon compte toutes les Volontés défaussées, même avec destination remplacée,
pour sa répartition de malus. Sa liste publique de cartes reste limitée aux
déplacements ordinaires ou en Support pour préserver les identités privées.
Le test historique de suspension de Kanon garde son identifiant, avec des
assertions et un commentaire corrigés par l'arbitrage explicite du créateur.
La nouvelle preuve signale quelle ancienne interprétation elle remplace ; les
anciens rapports et leurs empreintes ne sont pas réécrits.

La première suite globale de ce lot comporte 2 910 réussites et un seul échec
sur l'ancienne assertion négative de Traumatize. Le fichier
`full-before-legacy-ruling-update.json` le conserve. L'attente est mise à jour
selon le même arbitrage, avec une vérification de l'absence d'entrée au Limbo.
Les 20 tests du module réussissent ensuite, avant la suite finale consignée ici.

`python tools/card_discard_observer_audit.py` exécute les contrats manuels de
`audit/discard-observers.json`. Les producteurs sont les mouvements réels et
le résultat de défausse multiple, pas des événements cards_discarded injectés.
Les états de remplacement sont préparés explicitement. Trois cartes défaussées
ensemble ne déclenchent qu'une fois les observateurs « une ou plusieurs » ;
Otranth reste une fois par arrivée réelle de Manifestation au Limbo.

Les dix parcours réseau utilisent des actions d'entrée de Pluff contrôlées,
son effet de défausse, des choix de cibles et des passages de priorité. Kanon
emploie une déclaration payée de Ponder, deux ordres de remplacement successifs,
une reconnexion et deux malus. Les clients incrémental et ancien reçoivent les
états. Le pilote des phases est isolé et la phase reste stable.

Le banc reconnaît une action déjà en attente de son choix de cible et distingue
correctement les producteurs de Main/Deck de Makaboon. Ces ajustements précèdent
la reproduction conservée et ne sont pas comptés comme défauts du jeu.

La suite complète est `run_card_audit.units()` avec `audit.OUT` pointant vers
ce dossier. Les tests réseau et Chrome utilisent ici une exécution hors sandbox
Windows. `ui-tests.json` conserve commandes, durées et journaux des trois suites.

`coverage-before.json` conserve les octets du registre précédent ; son empreinte
correspond à la preuve historique conditional-discard-followup. Les empreintes
des deux fichiers de production avant correction correspondent aussi aux sources
consignées par ce lot précédent. `evidence.json` relie les sources après correction,
les contrats, arbitrages, résultats et le registre actualisé.

Les profils d'exil posent directement les marques Quasimillenary, y compris
au Deck. Ils contrôlent le chemin de remplacement sans prouver que ces états
particuliers sont atteignables en partie automatique. Le parcours réseau de
Kanon utilise aussi cet état contrôlé. Les branches ordinaires et de BOB restent
distinctes de cette limite.

Les effets propres aux cartes défaussées (Tombloom, Nghoul-ong hors Limbo), les
instructions multiples avant une collecte, autres capacités, parties complètes
et toutes les interactions restent hors de ce lot. Aucun changement client,
VFX, version, commit ou push, ni nouveau test Safari, appareil ou illustration.
