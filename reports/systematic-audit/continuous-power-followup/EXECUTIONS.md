# Validation locale : puissance continue

Base publiée : 141.4 (`ebeb398fc3cd4b3a54142074104f92e309e552c9`). Aucun push ni changement de version.

## Exécutions ciblées

- `python -m unittest test_continuous_power_family` : **228/228** après correction.
- `python -m unittest test_continuous_power_integration` : **11/11** parcours à deux connexions, utilisant le jeu payé de Defer et vérifiant les puissances publiques des deux joueurs.
- `python -m unittest test_continuous_power_oracle` : **2/2**, détection de mauvais bonus/plafond injectés dans les fixtures.
- `node tests/test_continuous_power_ui.cjs` : **228/228** contrôles du rendu DOM des badges, 19 cartes × trois états de la source × deux joueurs × deux formats Chrome.
- `python -m unittest test_power_family test_modifier_order_audit test_cleanse_state_audit test_observed_events_audit test_support_clause_audit test_game_state.TokenCopyEntersFieldTests` : **381/381**.

Python utilise `PYTHONPATH=…/Documents/tmp/kko-test-deps;server;tests;tools` et `PYTHONIOENCODING=utf-8`. Les sockets et Chrome s'exécutent hors de la restriction réseau du bac Windows, uniquement en local.

## Avant correction

`before.json` contient **228 cas dont quatre échecs** : bonus continus de Herbaceous Whisperer, Gargullo et Hyperuranic Tower reçus en Impasse par Nubilung ; comptage d'un ancien Support en Impasse par Skapus. Le test Nubilung utilise le nettoyage de confrontation du moteur pour produire sa présence en Impasse avec le marqueur historique Support.

Les journaux initiaux conservent aussi les erreurs du banc : alias `cid` manquant pour Cleanse, rafraîchissement des Premières Manifestations manquant après changement de contrôle, et deux créations de jetons avec une destination non prise en charge. Ces erreurs ne sont pas comptées comme défauts du produit.

## Portée

**20 clauses sélectionnées de 19 cartes**, dont 15 cartes encore hors du registre et quatre déjà présentes pour d'autres clauses. Les attentes de puissance et de portée sont littérales dans le contrat ; les règles encodées fournissent l'implémentation, jamais les résultats attendus.

Les états initiaux, répartitions de zones, contrôleurs et résultats de comparaison sont contrôlés. L'avance automatique des phases est désactivée dans les onze parcours réseau. Les contrôles Chrome utilisent la sérialisation publique du jeu et des illustrations locales ; ils vérifient les badges de modificateur, sans certifier une partie complète, une interaction de glissement, les illustrations distantes, un téléphone physique ou Safari.

Le lanceur `tools/card_continuous_power_audit.py --units <preuve générale courante>` réutilise les résultats réels de la suite complète pour assembler les liens de clauses, sans répéter les parcours réseau. Une seule suite complète est lancée après stabilisation des sources du lot.

## Validation finale

- **4029/4029 tests Python passent**, zéro échec et zéro test ignoré, en 640,485 secondes.
- Une seule régression générale pour ce lot : `python -c "from pathlib import Path; import run_card_audit as r; r.audit.OUT=Path('reports/systematic-audit/continuous-power-followup'); raise SystemExit(r.units())"`.
- Assemblage sans réexécution : `python tools/card_continuous_power_audit.py --units reports/systematic-audit/continuous-power-followup/unit-tests.json` ; **241 cas, 20 clauses, 19 cartes**.
- Registre : `python tools/card_coverage_status.py --units reports/systematic-audit/continuous-power-followup/unit-tests.json --write` ; **203/450 cartes (45,1 %)**, quinze nouvelles, 247 hors registre. Aucun document de preuve exclu.
- Digest identique entre sources courantes, `clauses.json`, `unit-tests.json` et `coverage-status.json`. Les empreintes de `browser.json` correspondent aux sources actuellement présentes.
- HEAD et origin/main restent au commit publié indiqué plus haut. Aucun push, commit ni changement de version.
