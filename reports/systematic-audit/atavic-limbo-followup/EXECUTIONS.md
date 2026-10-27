# Atavic Introspection — arbitrage des Limbos

Empreinte commune actuelle : `17a8386d34a48af6cad6c891c51f7020c5ea7832bfa79bbb0af7c7c0da5a55f1`.

- Neuf nouvelles méthodes réussies, dont un parcours réseau avec reconnexion.
- Suite Python complète : 1 440 réussites, aucun échec ni test ignoré.
- Six suites navigateur et une suite JavaScript de transport réussies.
- Choix UI : six configurations, trois langues et deux formats ; douze cas de propriétaire avec confirmation et verrouillage.

Le ciblage autorise un seul des deux Limbos ; le Deck du propriétaire reste la destination. Les instructions indiquent le joueur concerné.
La reproduction historique initiale contient six méthodes et trois échecs. Les trois méthodes de destination/protocole sont ajoutées ensuite.
before.json, targets.json et browser-before.json sont historiques ; leurs empreintes et leurs portées initiales sont conservées.
ruling.json, unit-tests.json et ui-tests.json portent l’empreinte actuelle. browser.json est associé à la suite UI exécutée sous cette empreinte, sans empreinte individuelle enregistrée.

Commandes : `python tools/card_atavic_limbo_audit.py` ; `run_card_audit.units()` avec OUT vers ce dossier ; les sept commandes Node sont listées dans ui-tests.json.
Voir [le rapport détaillé](../../../docs/AUDIT_ATAVIC_LIMBO_AFTER_140_3.md). Aucun nouveau commit ni push.
