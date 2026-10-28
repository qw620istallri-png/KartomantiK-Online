# Exécutions — défausse remplacée puis pioche

Empreinte finale commune : `6abc7651c301da5bfa0c973597a7c948bb9025e64749b293c0982fad7ff0633f`. Lot local après 141, non publié.

- Deux clauses déjà enregistrées : Pray the Ether et Alchemical Press.
- 70 scénarios de famille et six parcours WebSocket : 76 méthodes réussies.
- Suite complète finale : 2 733 méthodes Python distinctes réussies,
  aucun échec ni test ignoré.
- Trois suites client réussies : parité des règles (608 scénarios), frontend
  et transport incrémental. Aucun nouveau parcours UI propre à ces cartes.
- Registre strict inchangé : 120/450 (26,7 %). Zéro nouvelle carte unique ;
  de nouvelles branches de deux cartes sont désormais reliées aux tests réussis.
- Aucune nouvelle correction du moteur ou du catalogue nécessaire. Les sources
  d'exécution et les métadonnées de cartes sont inchangées pendant ce lot.

L'arbitrage du créateur confirme qu'une défausse de Main redirigée en Suspension
ou Exil satisfait sa condition. La pioche est ensuite demandée avec ses blocages
et remplacements propres. Le catalogue EN/FR/IT contient déjà l'ordre de l'errata
Bêta de Press : défausse, puis pioche. Les deux décisions sont conservées dans
`audit/rule-decisions.json`. Les attentes indépendantes sont dans
`audit/conditional-discard-draw.json`.

`python tools/card_conditional_discard_audit.py` exécute cinq profils de destination
croisés avec six situations de ressources, doublons, blocage ou Kanon par carte,
puis dix scénarios de refus, source partie et indisponibilité. Les deux ordres
BOB/exil sont testés. Les remplacements sont préparés explicitement.

Les six parcours réseau utilisent de vraies déclarations de Pray. Pour Press,
elles produisent son offre, l'acceptation et l'ordre simultané de la Pile. Pray
reste en dessous lorsque le résultat de Press est inspecté. Une reconnexion au
choix d'ordre conserve la séquence ; les réponses invalides et rejouées sont
refusées. Les clients incrémental et ancien reçoivent les bons états. Le pilote
automatique des phases est isolé, et la phase reste stable.

La priorité du banc de Pray a été remise à son état avant déclaration, au lieu
de conserver la priorité adverse produite par une déclaration préparatoire.
Les refus correspondants du serveur étaient corrects et ne constituent pas
une régression du jeu.

La suite complète est `run_card_audit.units()` avec `audit.OUT` pointant vers
ce dossier. Les tests réseau et Chrome utilisent ici une exécution hors sandbox
Windows. `ui-tests.json` conserve commandes, durées et journaux des trois suites.

`coverage-before.json` conserve les octets du précédent registre global ; son
empreinte correspond à la preuve historique du lot shuffle-draw-followup.
`evidence.json` relie empreintes des sources d'exécution, contrats, arbitrages,
résultats et registre actualisé. Les preuves historiques restent inchangées.

Les autres capacités de Press, réactions d'autres cartes à une défausse remplacée,
parties complètes et toutes les interactions ne sont pas certifiées. La reconnexion
ne certifie pas une restauration après redémarrage du processus. Aucun changement
client, VFX, version, commit ou push, ni nouveau test Safari, appareil ou illustration.
