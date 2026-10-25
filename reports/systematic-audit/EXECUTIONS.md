# Rapport des exécutions

Empreinte : `d7206b761c14f98bfb92805803e73341e06ebecf175e711c5e60197b4d50bf07`

```json
{
  "cards": 450,
  "voluntaryUiActions": 182,
  "unit": {
    "executed": 1206,
    "passed": 1206,
    "failed": 0,
    "skipped": 0
  },
  "matrix": {
    "cards": 450,
    "abilities": 496,
    "matrix": {
      "carrier-only": 314,
      "dedicated-path": 36,
      "needs-family-scenario": 2826,
      "not-applicable": 222,
      "pass": 1562
    },
    "failures": 0,
    "printedAssertions": 119,
    "printedFailures": 0
  },
  "browser": {
    "cards": 450,
    "actions": 182,
    "journeys": 2,
    "failed": 0,
    "unresolvedChoiceScenarios": 0
  },
  "traces": {
    "traces": 40,
    "steps": 12175,
    "failed": 0
  },
  "ui": {
    "executed": 13,
    "failed": 0
  },
  "independentReview": {
    "catalogCards": 450,
    "reviewRecords": 450,
    "uniqueReviewedCards": 450,
    "catalogParagraphs": 760,
    "matchedParagraphEntries": 760,
    "recordedCardStatuses": {
      "reviewed-defect": 51,
      "reviewed-match": 396,
      "ruling-required": 3
    },
    "indexedTestMethods": 139,
    "cardsMentionedByTests": 96,
    "indexedMethodsWithCurrentExecution": 139
  },
  "remoteArt": {
    "cards": 450,
    "passed": 450,
    "failed": 0,
    "supplementalFailed": 0,
    "identicalBodyGroups": 0,
    "pageErrors": 0
  },
  "failed": 0,
  "fullTextSemanticCertification": false
}
```

## Mécaniques : tests effectivement exécutés

| Famille | Exécutés | Réussis | Modules absents |
|---|---:|---:|---|
| payment | 26 | 26 | aucun |
| stack-target-priority | 25 | 25 | aucun |
| copy-control | 35 | 35 | aucun |
| chain | 23 | 23 | aucun |
| departure-memory | 27 | 27 | aucun |
| first-reference | 11 | 11 | aucun |
| suspend-immediate | 11 | 11 | aucun |
| replacement-events | 43 | 43 | aucun |
| cleanse-duration | 39 | 39 | aucun |
| choices-reconnect | 16 | 16 | aucun |
| endgame | 6 | 6 | aucun |

## Couverture restante

- Relier chaque clause revue à un oracle exécutable ; les mentions AST ne certifient pas les clauses.
- Compléter les branches alternatives et interactions pertinentes qui ne sont pas encore exécutées.
- Les porteurs déclenchés/passifs isolés ne prouvent pas toutes les séquences de partie.
- Les parcours navigateur vérifient la fin du choix/Pile ; leurs résultats chiffrés demandent un oracle dédié.

[450 fiches et matrice](README.md) · [revue indépendante](SEMANTIC_REVIEW.md) · [preuves détaillées](evidence.json) · [navigateurs](browser.json) · [séquences](traces.json)
