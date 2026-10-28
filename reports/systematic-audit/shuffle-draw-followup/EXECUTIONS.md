# Exécutions — mélanges de Main et pioches

Empreinte finale commune : `db91ce74e53f756177fd3bfb6b55387c5915f90e673e15f07c7b14c618ce1f39`. Lot local après 141, non publié.

- Deux clauses sélectionnées : Deny Fate et Pontificate Heresy.
- 37 scénarios de famille et cinq parcours WebSocket : 42 méthodes réussies.
- Avant correction : 21 réussites et dix échecs sur 31 méthodes, toutes
  retrouvées et réussies dans la suite complète finale.
- Suite complète finale : 2 657 méthodes Python distinctes réussies,
  aucun échec ni test ignoré.
- Trois suites client réussies : parité des règles (608 scénarios), frontend
  et transport incrémental. Aucun nouveau parcours UI propre à ces cartes.
- Registre strict : 118 → 120 cartes sur 450 (26,7 %), soit deux nouvelles.
  Au moins une clause vérifiée par carte ; toutes les branches ne sont pas certifiées.

Les demandes de pioche communes respectent les blocages et Kanon. Pontificate
termine les mélanges avant toute pioche et conserve les cartes protégées de la
Main adverse. Les demandes restantes attendent la fin des choix de remplacement,
y compris la distribution de malus de Kanon. Deny Fate protège ses résultats
privés. Les champs de continuation sont privés et conservés après reconnexion.

`python tools/card_shuffle_draw_audit.py` exécute les contrats manuels de
`audit/shuffle-draw.json`. Les tests utilisent la déclaration, le paiement et
la résolution livrés. Le mélange est neutralisé pour rendre vérifiables l'ordre,
la conservation et les quantités. Les remplacements sont des états contrôlés.

Les parcours réseau utilisent de vraies confirmations, une reconnexion du joueur
et un client incrémental face à un ancien client. Ils refusent les sélections
invalides et rejouées. La phase reste stable ; son pilote automatique est isolé.
Les essais normaux réutilisent l'état final déjà reçu, sans attendre une
nouvelle émission. Cet ajustement du banc n'est pas un défaut supplémentaire.

La suite complète est `run_card_audit.units()` avec `audit.OUT` pointant vers
ce dossier. Les suites client figurent dans `ui-tests.json`. Les tests réseau et
Chrome utilisent ici une exécution hors sandbox Windows.

`coverage-before.json` conserve exactement les octets du précédent registre ;
son empreinte correspond à la preuve historique du lot draw-family-followup.
`evidence.json` relie les empreintes actuelles des sources, contrats, résultats,
journaux et registre. Les campagnes précédentes gardent leurs empreintes historiques.

Les suites conditionnelles « si vous le faites » sous remplacement restent
en attente d'une précision de règle. Aucun changement client, VFX, version,
commit ou push. Aucun nouveau test Safari, appareil physique ou illustration.
