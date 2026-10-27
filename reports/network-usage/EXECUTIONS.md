# Transport réseau — preuves locales

Empreinte commune : `794c798229fcb34f1d93780d78ebb6fc9c078932cbe8edd20ef4377bb2020500`.

- Suite Python complète : 1 409 réussites, aucun échec ni test ignoré.
- 21 nouveaux tests Python ciblent les diffs, droits, versions, concurrence et reconnexion.
- 14 suites navigateur et une suite JavaScript de transport réussies.
- Deux actions de cartes et deux parcours de choix privé/reconnexion dans deux vrais navigateurs réussis.
- Six fixtures ; 1 078 états reconstruits exactement par le vrai décodeur client.

| Fixture | JSON complet | JSON incrémental | Réduction JSON | Réduction trames compressées locales |
| --- | ---: | ---: | ---: | ---: |
| mixed | 2845436 | 145342 | 94.89 % | 97.85 % |
| manual | 2612038 | 100730 | 96.14 % | 98.06 % |
| journal | 2738950 | 89886 | 96.72 % | 97.71 % |
| deck | 2917688 | 105610 | 96.38 % | 98.24 % |
| unchanged | 2917688 | 28924 | 99.01 % | 98.99 % |
| stack | 1255578 | 360790 | 71.27 % | 85.95 % |

Les 33 effets de pile conservent toutes leurs diffusions : 68 états pour deux sièges, avant comme après.
Les pourcentages sont propres aux fixtures locales. Ils ne prédisent pas la facture Render et excluent TLS/TCP/keepalives.
Le relevé [before.json](before.json) est historique ; les autres preuves ci-dessous portent l’empreinte commune actuelle.

Commandes : `python tools/network_usage_audit.py`, `run_card_audit.units()` avec OUT vers ce dossier, suites Node listées dans [ui-tests.json](ui-tests.json).
Navigateur réel : `node tools/card_audit_browser.mjs --actions-only --focus=2oka6j26ibu19l9_en,omhqwnu5tvwlzzg_en,inner-deserts-100` avec sortie séparée.
Les captures de cette exécution restent locales ; [browser.json](browser.json) garde les résultats, pas une nouvelle campagne des 450 cartes.

Voir [le protocole et la lecture des compteurs Render](../../docs/NETWORK_USAGE.md). Aucun commit ni push ; version inchangée.
