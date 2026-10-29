# Déplacements manuels : PC et tactile

Le banc démarre le serveur et deux véritables clients Chrome. Seules les zones initiales sont injectées via une route de fixture liée à 127.0.0.1 ; les joins, négociations de patches, gestes, commandes, réponses et rendus utilisent le jeu livré.

## Diagnostic

- `initial-fixtures.json` conserve le premier essai de 54 cas. Une fenêtre de préparation de Deck masquait les gestes, une cible Volontés était mal nommée et une assertion lisait mal le compteur public. Ces erreurs du banc ne sont pas revendiquées comme bugs du jeu.
- Les déplacements par commande ont malgré cela reproduit le défaut de destination : une copie déjà au Limbo suffisait à détourner le vol vers cette pile, y compris pour un départ à l'Exil ou à la main.
- `before-compact-drop.json` conserve 66 cas : 60 passent ; les six gestes vers le Vaisseau adverse replié échouent. Les icônes compactes ne portaient pas les destinations de dépôt.
- Les diagnostics de geste depuis la main ont ensuite corrigé l'assertion de cible (elle n'acceptait que les cartes du plateau) et attendu les frames de disposition de la main. Ils ne représentent pas une régression du jeu.
- `browser.json` est le résultat final complet ; les journaux de diagnostics restent locaux selon `.gitignore`.

## Périmètre

PC/PC (1440×1000), tactile/tactile (844×390), PC/petit tactile (640×288), depuis les deux sièges. Les tests vérifient le trajet et le nœud animé, le dépôt réel vers Deck/Vaisseau, les autres départs du plateau, les transferts entre piles, les zones Interzone/Volontés et le nettoyage. La pioche manuelle et l'arrivée depuis la main sont contrôlées séparément. Le mode réduit conserve un retour visuel sans vol.

Les cartes privées restent des dos chez l'adversaire. Les assertions sur les vols capturent les arguments de la vraie fonction, puis celle-ci s'exécute ; les gestes ne sont pas remplacés. Les illustrations sont remplacées par le dos local pour rendre le banc indépendant du réseau d'images. Aucun appareil physique ni Safari réel n'est certifié. Les variantes de toutes les cartes et les déplacements simultanés de copies identiques ne sont pas exhaustivement certifiés.

## Reproduction

Depuis la racine du dépôt, avec les dépendances Python serveur/test et Playwright/Chrome installés :

```powershell
$env:PYTHONPATH='server;tests;tools'
$env:PYTHONIOENCODING='utf-8'
node tests/test_manual_motion.cjs
```

Ce poste utilise aussi le répertoire existant `C:/Users/istal/Documents/tmp/kko-test-deps` dans PYTHONPATH pour ses dépendances Python locales.
