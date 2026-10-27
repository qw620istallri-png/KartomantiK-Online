# Exécutions — Traumatize et Extortionist Womb

Empreinte finale commune : `3fa678948f677fe9f06b2610e7d7ae4e05033cf93fe31ecfcbb4891349320b57`.

- `python tools/card_private_hand_audit.py` : 23 méthodes réussies, dont trois parcours WebSocket.
- `node tests/test_private_hand_picker.cjs` : douze scénarios dans six configurations Chrome.
- Validation commune de publication : 1 538 tests Python, huit suites navigateur et une suite JavaScript du transport réussis.

Les preuves générales sont partagées avec [la publication 140.32](../release-140-32/EXECUTIONS.md), avec la même empreinte. Les identifiants des clauses sont dans `clauses.json`.

`before.json` conserve 20 méthodes avant correction, neuf réussites et onze échecs sur dix-sept sous-cas. Cette empreinte est historique.

Les deux captures françaises ont été inspectées sur PC et en paysage mobile simulé. La main entière est présente ; les cartes non admissibles restent désactivées. Les styles et VFX ne sont pas modifiés.

Les tests isolent le pilote des phases ; les changements de main pendant un choix et la fin de tournoi sont des fixtures explicites. Les autres sélecteurs, combinaisons, appareils physiques, Safari et illustrations distantes ne sont pas certifiés.
