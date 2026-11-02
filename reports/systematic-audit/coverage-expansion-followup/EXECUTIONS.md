# Extension du registre strict et matrice de transitions

## Résultats

- Suite complète enregistrée : **4 337/4 337 tests Python réussis**, zéro
  échec, zéro test ignoré, en 674,856 secondes.
- Identifiants d'exécution : **4 337 uniques**, aucun doublon.
- Parité client/serveur : **609 scénarios catalogue réussis**.
- Matrice multi-étapes : **3 scénarios réussis**, couvrant six cartes.
- Registre strict : **229/450 cartes (50,9 %)**, soit deux nouvelles cartes :
  Rematch! et Gnarlipuff, the Slimy.
- Aucun rapport de clause exclu et empreinte identique entre les sources,
  `unit-tests.json`, `coverage-status.json` et l'inventaire des lacunes.

## Commandes

```powershell
$env:PYTHONPATH='server;tests;tools'
py tools/card_transition_matrix_audit.py
py tools/card_distribution_token_audit.py
py -c "from pathlib import Path; import run_card_audit as r; r.audit.OUT=Path('reports/systematic-audit/zone-tribute-final-followup'); raise SystemExit(r.units())"
py tools/card_coverage_status.py --units reports/systematic-audit/zone-tribute-final-followup/unit-tests.json --write
node tests/test_rules_parity.cjs
```

## Nouvelles garanties

- `card_coverage_status.py` refuse explicitement une preuve contenant des
  identifiants de tests dupliqués.
- Le complément du registre est exact : 229 cartes couvertes et 221 cartes
  hors registre forment les 450 cartes, sans intersection.
- `coverage-gaps.json` inventorie 320 paragraphes et 1 041 oracles de branches
  restant à relier, puis répartit les 221 cartes en 69 lots mécaniques gloutons
  sans duplication.
- La matrice vérifie annulation, nouvelle tentative, résolution, destination,
  tour suivant, disponibilité, auto-pass et reset sur une même séquence.

## Limites

- Une preuve sélectionnée ne certifie pas toutes les branches d'une carte.
- Les groupes mécaniques proviennent du registre d'automatisation et servent à
  ordonner le travail ; ils ne constituent pas une preuve sémantique.
- La campagne ne prétend toujours pas certifier toutes les interactions entre
  les 450 cartes.
