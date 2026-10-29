# Lot local — destructions ciblées

Huit cartes, douze paragraphes sélectionnés et 135 méthodes réussies dans
`clauses.json` : 126 méthodes unitaires et neuf parcours WebSocket. Les textes,
oracles et liens par clause sont conservés. Les appareils physiques et les
navigateurs ne sont pas certifiés par ce lot.

Reproduire le lot :

```powershell
$env:PYTHONPATH='server;tests;tools'
python tools/card_targeted_destruction_audit.py
```

Les dépendances Python du projet doivent être installées. Un répertoire local
de dépendances de test a été utilisé pour cette exécution sur le PC de travail.

Les reproductions `before.json`, `sibling-before.json` et `repress-before.json`
conservent chacune le défaut confirmé avant son correctif. Les fichiers `.log`
homonymes et `family.log` conservent les sorties d'exécution. Les différences de
préparation initiales du banc sont expliquées dans
`docs/AUDIT_TARGETED_DESTRUCTION_AFTER_141.md`.

`unit-tests.json` et `full.log` conservent la régression complète : **3 083 tests
Python distincts réussis**, aucun échec ni test ignoré, sur la même empreinte
que le lot. Le compteur strict publié dans
`reports/systematic-audit/coverage-status.json` atteint **129/450 (28,7 %)**,
soit sept nouvelles cartes ayant au moins une clause sélectionnée vérifiée.
Multicastigate était déjà comptée. Ce compteur ne certifie pas toutes les
branches d'une carte.

Arbitrage du créateur : Repress gagne les points imprimés malgré Suspension ou
Exil ; Convert et Lilitha exigent une destruction effective pour leur suite
conditionnelle. Les conditions de ciblage du catalogue restent applicables.

Aucun changement de version, commit ou push demandé pour ce lot.
