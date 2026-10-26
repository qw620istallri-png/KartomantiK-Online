# Retours en main et interdictions de rejouer — preuves locales

Empreinte commune des sources exécutées : `f6ecd1f810192d3ceced5e2194610f97d4f72a6f3eb0b5d1c868ecc44ee6d412`.

Version 140.1 conservée. Aucun commit ni push.

| Couche | Exécutés | Réussis | Échecs | Ignorés |
| --- | ---: | ---: | ---: | ---: |
| Clauses ciblées, dont deux scénarios réseau | 24 | 24 | 0 | 0 |
| Suite Python complète | 1 388 | 1 388 | 0 | 0 |
| Suites UI | 4 | 4 | 0 | 0 |

Six paragraphes sélectionnés de quatre cartes. Les associations explicites sont dans [clauses.json](clauses.json).
Le [rapport détaillé](../../../docs/AUDIT_BOUNCE_REPLAY_AFTER_140_1.md) distingue les branches, fixtures et limites.

Reproduction historique avant corrections : 22 méthodes, 17 réussites et cinq méthodes en échec (12 sous-cas). [before.json](before.json) porte une empreinte antérieure.
Les preuves actuelles utilisent les mêmes sources : [evidence.json](evidence.json), [unit-tests.json](unit-tests.json), [ui-tests.json](ui-tests.json).

Commandes : `python tools/card_bounce_replay_audit.py` ; `run_card_audit.units()` avec OUT vers ce dossier ; quatre commandes Node ci-dessous.

- `node tests/test_rules_parity.cjs` : PASS — [journal](test_rules_parity.log).
- `node tests/test_choice_continuity.cjs` : PASS — [journal](test_choice_continuity.log).
- `node tests/test_frontend.cjs` : PASS — [journal](test_frontend.log).
- `node tests/test_semantic_ui.cjs` : PASS — [journal](test_semantic_ui.log).

Les anciennes campagnes générales restent historiques. Ni toutes les branches des cartes sélectionnées, ni les zones cachées, ni Safari Mac réel ne sont certifiés par ce lot.
