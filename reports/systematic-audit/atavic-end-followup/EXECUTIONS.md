# Atavic — preuves locales après 140.3

Empreinte commune actuelle : `6ad64abb9a7a4bc0e601102adfbcb289636540a469a994df2b0eef7731784a74`.

- 22 nouvelles méthodes ciblées : 20 méthodes de clauses et deux parcours réseau, toutes réussies.
- Cinq paragraphes sélectionnés de deux cartes ; les autres branches ne sont pas certifiées par analogie.
- Suite Python complète : 1 431 réussites, aucun échec ni test ignoré.
- Quatre suites navigateur et une suite JavaScript du transport réussies.

Reproduction historique avant correction : 20 méthodes, 18 réussites et deux échecs dans [before.json](before.json).
Preuves actuelles : [clauses.json](clauses.json), [unit-tests.json](unit-tests.json), [ui-tests.json](ui-tests.json), [evidence.json](evidence.json).

Commandes : `python tools/card_atavic_end_audit.py`, `run_card_audit.units()` avec OUT vers ce dossier, et suites Node listées dans ui-tests.json.
La portée d’Introspection sur le Limbo adverse attend un arbitrage. Les tests du propre Limbo et les corrections indépendantes sont terminés.
Aucun commit ni push supplémentaire après la publication 140.3.
