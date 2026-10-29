# Validation locale : Support et Jigon

Base publiée : 141.3 (`2f0854995886af201e36e7013b3c707e51103cfb`). Aucun push ni changement de version.

## Lot ciblé

- `python tools/card_support_permissions_audit.py` : **463/463**, soit 443 tests Support sur 39 cartes, dix tests de Jigon et des frontières de permission, deux contrôles de sensibilité des oracles et huit parcours à deux sockets.
- **69 clauses sélectionnées pour 40 cartes**. Les autres paragraphes des 39 cartes Support ne sont pas certifiés par ce lot.
- `python -m unittest test_loop_jigon test_choice_liveness_audit test_copy_chain_followup_audit test_special_payments test_support_clause_audit test_game_state.LotTwentySevenTests` : **91/91**.
- `node tests/test_rules_parity.cjs` : **608 scénarios passent**.

Les variables Python sont `PYTHONPATH=…/Documents/tmp/kko-test-deps;server;tests;tools` et `PYTHONIOENCODING=utf-8`. Les parcours à deux sockets s'exécutent hors de la restriction réseau du bac Windows, uniquement sur l'hôte local.

## Reproduction et erreurs du banc

`jigon-before.json` conserve la reproduction du défaut : trois des six premiers tests échouent sur le message de perte d'effets de la source. L'ancien test Hourglass évitait ce contrôle, faute de capacité jouée encodée.

Les journaux initiaux conservent aussi les erreurs du banc, distinctes des défauts du produit : cibles d'entrée/capacité de contrôleur manquantes pour sept cartes Support, mauvais coût attendu pour Strengthen et rotation/coordonnées manquantes dans les fixtures réseau de Jigon. Les tests corrigés utilisent le coût imprimé {H} et les entrées réellement attendues par les déclarations.

## Portée et méthode

Le regroupement réutilise les mêmes scénarios avec des permissions attendues écrites indépendamment dans le contrat de chaque carte. Les tests de sensibilité vérifient qu'une permission encodée incorrectement provoque bien un échec.

Le lanceur peut assembler ses preuves avec `--units <unit-tests.json>` à partir de l'exécution générale courante. Il contrôle le digest et la liste complète des cas attendus, sans répéter les parcours réseau uniquement pour écrire le rapport. Une seule suite générale est lancée après stabilisation de ce lot.

Les états initiaux et résultats de confrontation des tests Jigon sont contrôlés ; recherche, choix, pile, événements et résolution utilisent les méthodes du jeu. L'avance automatique des phases est désactivée dans les huit parcours réseau. Aucun nouveau rendu navigateur, illustration distante ou appareil physique n'est certifié.

## Validation finale

- **3788/3788 tests Python passent**, zéro échec et zéro test ignoré, en 636,285 secondes.
- Une seule régression générale pour ce lot : `python -c "from pathlib import Path; import run_card_audit as r; r.audit.OUT=Path('reports/systematic-audit/support-permissions-followup'); raise SystemExit(r.units())"`.
- Assemblage sans réexécution des tests : `python tools/card_support_permissions_audit.py --units reports/systematic-audit/support-permissions-followup/unit-tests.json` ; **463 cas, 69 clauses, 40 cartes**.
- Actualisation : `python tools/card_coverage_status.py --units reports/systematic-audit/support-permissions-followup/unit-tests.json --write`.
- Registre : **188/450 cartes (41,8 %)**, 40 nouvelles, 262 hors registre, aucun document de preuve exclu. Clauses sélectionnées seulement.
- Digest identique entre sources courantes, `clauses.json`, `unit-tests.json` et `coverage-status.json`.
- HEAD et origin/main restent au commit publié indiqué plus haut. Aucun push, commit ni changement de version.
