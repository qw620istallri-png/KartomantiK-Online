# Exécutions — Gorlok et groupes de pioche

Empreinte commune : `d19a01c109cc7c31afebb684dc5cf4d45b98e73032449300f7848ae76f0545f1`.

Base publiée : 140.31, `62d169c`. Corrections de ce lot et des deux lots précédents locales, sans push supplémentaire.

## Résultats

- `python tools/card_gorlok_draw_audit.py` : 26 méthodes réussies, dont trois scénarios WebSocket.
- Couverture étendue du paragraphe de Gorlok déjà sélectionné dans le lot Kanon ; aucune nouvelle clause unique revendiquée.
- Découverte complète `unittest` : 1 515 méthodes réussies, aucun échec ni test ignoré.
- Cinq suites navigateur : choix Gorlok, continuité des choix, frontend, reconnexion et parité (608 scénarios).
- Choix Gorlok : six configurations Chrome, trois langues et deux tailles d’écran.
- Une suite JavaScript du transport incrémental.

Les identifiants, résultats et sous-cas sont dans les preuves JSON. Les commandes, durées et journaux client sont dans `ui-tests.json`.

## Historique

`before.json` conserve 22 méthodes avant correction : 11 réussites et 11 échecs. Le cas de réorganisation interne de la Main a ensuite été ajouté.
`unit-before-control.json` conserve la première régression complète réussie avant renforcement du contrôle de pioche propre. Le contrôle final utilise un Deck propre non vide et vérifie les deux cartes réellement piochées.
Ces deux empreintes sont historiques. Les preuves finales de clauses, tests généraux et client partagent l’empreinte en tête de ce registre.

## Artefacts

| Preuve | SHA-256 |
| --- | --- |
| `clauses.json` | `44a0a27740226e2bb1948745f9c20b1a08cc57c66f23a502f92e244dce2c7d7a` |
| `unit-tests.json` | `58a39dd63d0f67b0d2e5cd7185e382e7150441b018bf7e0641b605b9f286bfbe` |
| `ui-tests.json` | `fb2ff24ce8ee7afa0945b26805a418eff08bf6be145aefa77dbf31e41429923b` |
| `before.json` | `b31915ee972dd2201162f68307520835df405f90fad961c27186bfeb29b70a93` |
| `unit-before-control.json` | `0922a7a223b44901468302922baa54004d1fac5ec593404f77203d850ec3aad2` |
| `picker.json` | `4aa7a31362e595a93f0e3a9111214644ce5b91d374b7d5d04a45dc6ef798280d` |
| `picker-1440.png` | `d3caadd29e285c6cb18348a1eeb85b30bcc692e7793e58a55df2a8fbf07cbcdf` |
| `picker-844.png` | `4ae63b40048a7ed2140062fa8d15b00af52a85a67188b12a28f07411cfdf4c27` |

## Vérification visuelle

Les deux captures françaises ont été inspectées sur PC et en paysage mobile simulé, avec des dos de cartes locaux après stabilisation du sélecteur. Seul le texte Gorlok et son branchement de traduction ont changé ; les styles et VFX restent inchangés.

## Limites

- Draw stimuli are explicit shared-engine requests, not every possible printed draw source.
- Network tests isolate automatic phase driving; no certification of full scheduling or VFX.
- Unexpected hand changes during an already-open choice are rejection checks, not legal interruption windows inside an effect.
- Physical devices, Safari Mac, remote illustrations and all card combinations remain outside this lot.
- Automatic cancellation when every card becomes invalid during an already-open choice is not certified.
- Reconnect is within the same live server process; process restart persistence is not certified.
- Previous audit and release evidence keeps historical source digests. No publication, styles or VFX changes.

Les captures PNG ont été régénérées par les contrôles de la 140.32. Les empreintes d’images du tableau ci-dessus restent historiques ; les images courantes et leur empreinte de sources sont consignées dans `releaseVisualEvidence` de `evidence.json`. Le manifeste initial est archivé dans `evidence-before-release.json` ; les fichiers PNG initiaux ne sont plus conservés.
