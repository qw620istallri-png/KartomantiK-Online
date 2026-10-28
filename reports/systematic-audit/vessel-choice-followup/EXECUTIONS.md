# Exécutions — Vaisseau et Interzone après 141

Lot local, non publié. Base : `355efdd` (bêta 141).
Empreinte commune : `ab7041bd9260d707be384a5744b0dfd1406545ee0286410cf5523d2e993de8d4`.

- Clauses sélectionnées : 28 méthodes réussies, dont trois parcours WebSocket.
- Suite Python complète : 1566 tests réussis, aucun échec ni test ignoré.
- Six suites client réussies : sélecteur Vaisseau, continuité des choix, parité
  client/serveur (608 scénarios), régressions générales, reconnexion et transport.
- Sélecteurs : six configurations Chrome, 18 scénarios, français/anglais/italien,
  PC et paysage mobile simulé. Six captures françaises inspectées visuellement.

## Commandes

```powershell
python tools/card_vessel_choices_audit.py
node tests/test_vessel_picker.cjs
```

La suite complète utilise `run_card_audit.units()` avec `audit.OUT` pointant
vers ce dossier. Les suites client utilisent le mode `--ui-only` avec les six
commandes listées dans `ui-tests.json`. Les WebSockets/Chrome nécessitent ici
une exécution hors de la sandbox Windows. Aucun serveur de production n'est utilisé.

`evidence.json` relie les empreintes des clauses, unités, suites client,
payloads sérialisés, journaux et captures. `baseline-corrected.json` est la
reproduction de référence : 18 méthodes sur le code publié en 141, neuf réussites
et neuf échecs. Son script charge les six mixins de jeu en mémoire, sans changer
les fichiers, et conserve leurs empreintes. `before.json` et `entry-before.json`
restent historiques ; les erreurs de préparation du premier banc sont détaillées
dans le rapport, sans les compter comme corrections du jeu.

Les autres preuves de campagnes conservent leurs empreintes historiques.
Les fichiers `*-before-final-review.json` conservent une validation intermédiaire.
Après retrait d'un contrôle de protection hors du lot vérifié et correction des
fixtures de propriété du Vaisseau, les trois couches ont été rejouées sur
l'empreinte finale commune ci-dessus.
Ni les 450 cartes ni toutes les interactions ne sont déclarées certifiées.
Les styles, VFX, versions et publications restent inchangés.
