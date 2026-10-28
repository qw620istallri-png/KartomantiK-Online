# Exécutions — points proportionnels

Empreinte finale commune : `63368879dbcf7d6a657f58b1759d445aaef48a3351f2a5146993fb3a8c0de2fe`. Lot local après 141, non publié.

- Six clauses sélectionnées disposant de contrats indépendants.
- 113 scénarios de famille, six parcours WebSocket et un contrôle du banc :
  120 méthodes réussies, aucun échec ni test ignoré.
- Suite complète : 2 311 méthodes Python réussies, toutes distinctes,
  aucun échec ni test ignoré.
- Trois suites client réussies : parité des règles (608 scénarios),
  régressions frontend et transport incrémental. Aucun nouveau parcours UI
  propre aux six cartes n'est certifié par ces suites.
- Registre strict : 100 cartes sur 450 (22,2 %), inchangé. Les six cartes
  avaient déjà des preuves ; leurs nouvelles branches s'y ajoutent.

## Reproduction et provenance

`python tools/card_scaled_score_audit.py` exécute les contrats manuels de
`audit/scaled-score-family.json`. Chaque scénario possède un identifiant de test.
Les populations attendues sont préparées indépendamment du compteur du moteur.
Le coefficient attendu vient du texte imprimé ; le test de sensibilité doit
échouer si ce coefficient est altéré volontairement.

Plea emploie une vraie déclaration et paie deux essences vertes. Les autres
capacités passent par une file normale de déclenchements. Cinq cas supplémentaires
emploient les constructeurs de résultat de confrontation ou de phase finale.
Les résultats de confrontation et les changements de population sont des
préparations contrôlées, pas des parties complètes produisant tous les événements.

Les six parcours réseau passent les priorités après une modification de la
population comptée. Un client incrémental et un client ancien doivent constater
le montant calculé sur l'état à la résolution, identifié par son action précise.
Le pilote automatique des phases est isolé ici.

La suite complète est `run_card_audit.units()` avec `audit.OUT` pointant vers
ce dossier. Les trois suites client figurent dans `ui-tests.json`. WebSocket
et Chrome emploient ici une exécution hors sandbox Windows.

`tools/card_coverage_status.py --units reports/systematic-audit/scaled-score-followup/unit-tests.json --write`
refuse des sources périmées ou une suite échouée. Chaque preuve de clause est
reliée à des tests qui ont tous réussi dans la suite complète courante.
`coverage-before.json` conserve exactement les octets du précédent compteur ;
`evidence.json` relie les empreintes des contrats, résultats, journaux et du
registre global actualisé. Les preuves précédentes gardent leurs empreintes
historiques.

Les six clauses renforcées sont celles de Floating Dancer, Plea for Generosity,
Agrupol, Donmo, Lombriculpop et Armored Pachywyrm. Les capacités non liées aux
points et les cas explicitement hors lot ne sont pas certifiés par association.
Aucun correctif moteur nouveau, aucun changement VFX, client, version, commit
ou push. Les corrections locales antérieures restent conservées.
