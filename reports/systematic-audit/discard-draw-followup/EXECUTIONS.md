# Exécutions — défausse et pioche

Empreinte commune des sources : `278489dd42e234893f36e49fbe55696833ff8730c59bc3914c1c66bc52092a6d`.

Base publiée : 140.31, `62d169c`. Corrections de ce lot locales, sans push ni modification des VFX.

## Résultats

- `python tools/card_discard_draw_audit.py` : 24 méthodes réussies, dont deux scénarios WebSocket.
- Découverte complète `unittest` : 1 464 méthodes réussies, aucun échec ni test ignoré.
- Quatre suites navigateur : choix, frontend, reconnexion et parité (608 scénarios).
- Une suite JavaScript du transport incrémental.

Les commandes exactes et durées des suites client sont dans `ui-tests.json` ; les identifiants des tests et leurs résultats sont dans les preuves JSON.

## Historique

`before.json` : 22 méthodes avant correction, 15 réussies et sept en échec (onze sous-cas).
`fixture-baseline.json` inclut une erreur préalable du banc sur le choix d’ordre simultané ; elle ne constitue pas une régression du jeu.

Les empreintes historiques sont conservées et ne sont pas celles des sources corrigées.

## Artefacts

| Preuve | SHA-256 |
| --- | --- |
| `clauses.json` | `1a1da684c8c644019e14ae38424f721ef79860466ca887945df81ff65296e4c1` |
| `unit-tests.json` | `5ee53002ecb68dc111f02bc256cfe0561923563fa3f6f1c31d117ae4b9983799` |
| `ui-tests.json` | `c0e8818b4b40c8125c33d0a637d6fe66abd5c7a9b4975fbc62de5e07ba6b3e00` |
| `before.json` | `209bb259c7c05e64d958662050617e7be5c1dc5e5ca638b4c1e499362908709f` |
| `fixture-baseline.json` | `231d9c96202eaeb4d8ca445c8d3ab55a46a59884d352524cca7b1e0862b317ef` |

## Limites

- Press unit cases isolate its triggered action; the combined Pray case explicitly queues paid/play events as the server does.
- Network tests isolate automatic phase driving; they do not certify scheduling or VFX.
- Recovery timing is an explicit fixture, not legal play or phase traversal of these cards.
- Other Press paragraphs, all card combinations, identical copies, physical devices and Safari are not certified.
- Kanon replacement-internal draw/discard event observers remain outside this batch.
- No new full-catalog browser rendering, remote-art, Safari Mac or physical-device certification.
- The published 140.31 release is the base; these corrections remain local and do not edit VFX.
