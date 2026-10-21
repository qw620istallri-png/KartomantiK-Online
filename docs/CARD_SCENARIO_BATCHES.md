# Scénarios réels des cartes, par lots de 10

Cette validation complète le certificat statique et le smoke test des capacités.
Elle vérifie chaque carte sur trois couches :

1. **Serveur** — compilation, résultat, effet continu, passif ou permission, plus
   les scripts génériques exécutés par le gestionnaire de messages réel.
2. **Joueurs** — chaque capacité volontaire est déclarée par un joueur dans une
   phase légale, avec ses cibles, coûts et Essences. La Pile est résolue et les
   vues des deux sièges sont sérialisées avant et après, sans révéler les mains.
3. **Client** — Google Chrome charge le vrai bac à sable local, carte après
   carte, et confirme son rendu dans la main, sur le plateau ou dans une zone
   publique tout en capturant les erreurs JavaScript.

Les 450 cartes sont réparties dans 45 rapports de dix cartes :
`reports/card-scenario-batches/lot-01.md` à `lot-45.md`.

## Rejouer la certification

Depuis la racine du projet :

```powershell
py -B tools\card_scenario_batches.py --write
node tools\card_browser_batches.mjs
py -B tools\card_scenario_batches.py --write
py -B -m unittest tests.test_card_scenario_batches -v
```

La première passe prépare le manifeste et les couches serveur/joueurs. Le test
Chrome écrit `reports/card-browser-results.json`. La seconde passe consolide les
trois couches dans `reports/card-scenario-batches.json` et dans les 45 rapports
Markdown.

`--check` échoue si le rapport JSON versionné ne correspond plus au catalogue,
au moteur, aux scénarios ou aux résultats Chrome enregistrés.

## Errata de Karma Bro et Kaos Bro

L’errata d’octobre 2026 remplace le lancer physique par le choix d’une carte
contrôlée par chaque joueur et un jet de D6 pour chacune. Ces deux cartes sont
désormais automatisées et incluses dans les vérifications serveur, joueurs et
client. Elles ne sont plus signalées comme manuelles dans les rapports.
