# Exécutions — première famille d'effets de puissance

Empreinte commune finale : `abc621db2fb2e4418957619ba989c5f6b9a28f31d2a0ad16418b7d2b1cd9bd55`. Lot local, non publié, après 141.

- 21 cartes, 23 clauses disposant d'un oracle indépendant.
- 291 scénarios de famille, onze parcours WebSocket et cinq contrôles du banc :
  307 méthodes réussies, aucun échec ni test ignoré.
- Suite complète : 1 899 tests Python réussis, aucun échec ni test ignoré.
- Trois suites client réussies : parité client/serveur (608 scénarios),
  régressions frontend et transport incrémental. Il ne s'agit pas de nouveaux
  parcours UI dédiés aux 21 cartes.
- Compteur strict : 71 → 87 cartes distinctes sur 450 (19,3 %), soit 16 nouvelles.
  Une clause testée ne certifie pas toutes les branches d'une carte.

## Reproduction et provenance

`python tools/card_power_family_audit.py` exécute les contrats manuels de
`audit/power-family.json`, avec un identifiant par couple effet/scénario.
Les scénarios non applicables ne sont pas générés ; aucun cas vide ne sert de preuve.
Les effets volontaires emploient les déclarations, coûts et résolutions réels.
Les déclenchements emploient la file de production et des stimuli explicites.

La suite complète est `run_card_audit.units()` avec `audit.OUT` pointant vers
ce dossier. Les trois suites client figurent dans `ui-tests.json`. Les tests
WebSocket/Chrome utilisent ici une exécution hors sandbox Windows.

`tools/card_coverage_status.py --units reports/systematic-audit/power-family-followup/unit-tests.json --write`
refuse une preuve périmée ou échouée. Le registre global `coverage-status.json`
ne compte que les cartes possédant des liens clause → tests réussis, en excluant
les références d'interaction seules. `coverage-before.json` conserve le compteur
fondé sur la précédente suite complète, en le distinguant des preuves courantes.

L'inventaire des mécanismes encodés sert seulement à préparer les lots. Jija
reste sans contrat dans ce groupe et n'est pas comptée par analogie.
Les premiers ajustements du banc (appel complet de Cleanse, représentation de
l'épuisement, préparation des événements et réserves d'essences réseau) ne sont
pas présentés comme des défauts du jeu.

`evidence.json` relie les empreintes des contrats, preuves et journaux, ainsi que
celle du compteur global. Les campagnes précédentes conservent leurs empreintes
historiques. Aucun nouveau correctif moteur, VFX, version, commit ou push dans ce lot.
