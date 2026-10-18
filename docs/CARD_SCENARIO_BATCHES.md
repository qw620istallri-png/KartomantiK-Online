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

## Limite physique conservée

Karma Bro et Kaos Bro restent signalées comme manuelles pour le lancer physique,
la rotation et la détection de la carte touchée. Leur chargement serveur, leurs
deux vues joueur et leur rendu client restent vérifiés automatiquement.
