# Exécutions — Kanon, événements et exemplaires

Empreinte commune : `b56c9308ef4064f74410bb1c19bf37447e174c741573686fd05d8883774c35d8`.

Base publiée : 140.31, `62d169c`. Ce lot et le précédent restent locaux, sans nouveau push ni modification des VFX.

## Résultats

- `python tools/card_kanon_events_audit.py` : 25 méthodes réussies pour neuf paragraphes sélectionnés de huit cartes, dont deux scénarios WebSocket.
- Découverte complète `unittest` : 1 489 méthodes réussies, aucun échec ni test ignoré.
- Cinq suites navigateur : sélecteur Kanon, choix, frontend, reconnexion et parité (608 scénarios).
- Sélecteur Kanon : six configurations Chrome, trois langues et deux tailles d’écran, cartes illustrées localement.
- Une suite JavaScript du transport incrémental.

Les identifiants et résultats des tests figurent dans les preuves JSON. Les commandes, durées et journaux des suites client sont dans `ui-tests.json`.

## Avant correction

`before.json` conserve 23 méthodes : neuf réussies et 14 en échec, dont une réponse malformée produisant une exception. Cette empreinte est historique.

## Artefacts

| Preuve | SHA-256 |
| --- | --- |
| `clauses.json` | `c9cb382063c99e614d42b6d59aa2e08a10bd95fc6e59cbff26df9e8663bbfb46` |
| `unit-tests.json` | `4d83b20be932097c6071b76e96d69742eb10b228c6a3e02509bcd3d5bddde357` |
| `ui-tests.json` | `fb862b1ef1705dd9f97b6035c9c65d40cceea376e968b8918eec2e013ff858ff` |
| `before.json` | `5a67a2701b7c4228208b5a643dcb39edc1ed20e5afd9ed38434ad72195105f90` |
| `picker.json` | `8c90e2e6d7afde5ef57d3c2d94a324a16a22ff5f2bf9b1f3a4d03bf6fafdb0e1` |

## Limites

- Draw requests are explicit fixtures; most observer effects are resolved in isolation. Tombloom uses the actual target-choice/Stack path.
- Network fixtures seed an inspected draw and isolate automatic phase driving; reconnect and choices use actual sockets.
- Gorlok is tested for a single draw event; concurrent/delayed events, stale hand copies and its full text remain outside this batch.
- Tenebro's victory exile and other printed paragraphs are not certified.
- BOB coverage uses one Deck-suspension source, not competing replacements, all thresholds or release.
- No new real-device, Safari, remote-art, full-catalog UI or VFX certification.
- The inspected Deck prefix is checked; a departure/reentry restoring the same visible prefix is outside this batch.
- Previous batch and release evidence retains historical source digests; no publication or VFX changes.
