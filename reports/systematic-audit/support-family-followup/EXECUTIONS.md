# Validation locale du lot Support

Base publiée : 141.3 (`2f0854995886af201e36e7013b3c707e51103cfb`). Aucun push, commit ni changement de version dans ce lot.

## Exécutions ciblées

- `python tools/card_support_spell_audit.py` : **83/83**, zéro échec ou test ignoré ; **73 méthodes unitaires + dix parcours à deux sockets**. Huit paragraphes sélectionnés pour six cartes.
- `python -m unittest test_support_clause_audit test_cleanse_state_audit test_copy_chain_followup_audit test_observed_events_audit test_replacement_order_audit test_game_state.TokenCopyEntersFieldTests` : **90/90**.
- `node tests/test_rules_parity.cjs` : **608 scénarios passent**.

Python utilise les dépendances locales et `PYTHONPATH=…/Documents/tmp/kko-test-deps;server;tests;tools`. Les tests réseau sont exécutés hors de la restriction réseau du bac Windows, uniquement sur l'hôte local.

## Rapports avant correction

- `before.json` : 63 méthodes, 55 passent et huit échouent. Deux attentes du banc sont à distinguer des défauts : lecture prématurée du compteur Blossom pour Reforging Fate et hypothèse de contrôle dans le premier scénario Cleanse. Le rapport détaillé explique leurs corrections.
- `token-routes-before.json` : une méthode échoue, avec huit sous-cas de génération.
- `count-choice-before.json` : le sous-cas Stampeding Brood échoue encore après les corrections de génération, faute de transmission des déclenchements par le choix du nombre.
- Les premiers essais comportant des erreurs de méthode du banc sont conservés dans les journaux ignorés par Git.

Le nouveau lanceur s'appelle `card_support_spell_audit.py`. Le lanceur historique `card_support_audit.py`, momentanément utilisé par erreur lors de la préparation, a été restauré sans modification ; ses anciens résultats ne sont pas remplacés.

## Portée

Coûts, résolution différée, invalidation tardive, remplacements, entrée en Support, observateurs d'entrée, durée, mémoire et nettoyage de victoire sont exercés dans les cas explicitement nommés. Les huit générateurs supplémentaires sont des preuves d'interaction et n'ajoutent pas huit cartes au registre. Aucun nouveau navigateur ou appareil physique n'est certifié. L'avance automatique des phases est désactivée dans les dix parcours réseau de ce lot.

## Validation finale

- Régression complète : **3325/3325 tests passent**, zéro échec et zéro test ignoré, en 586,088 secondes.
- Commande : `python -c "from pathlib import Path; import run_card_audit as r; r.audit.OUT=Path('reports/systematic-audit/support-family-followup'); raise SystemExit(r.units())"`.
- Registre : `python tools/card_coverage_status.py --units reports/systematic-audit/support-family-followup/unit-tests.json --write`.
- **148/450 cartes (32,9 %)** disposent d'au moins une clause sélectionnée prouvée ; six nouvelles cartes, 302 hors registre. Aucun document de preuve exclu.
- Digest identique entre `clauses.json`, `unit-tests.json`, les sources courantes et `coverage-status.json`. Le registre ne prétend pas certifier toutes les interactions des 148 cartes.
- `evidence.json` assemble les résumés et empreintes des artefacts. Le lanceur historique Support ne présente aucun diff. HEAD et origin/main restent au commit publié indiqué plus haut.
