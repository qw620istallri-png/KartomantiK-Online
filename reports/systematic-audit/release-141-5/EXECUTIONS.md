# Préparation de publication 141.5

Cette publication rassemble les trois lots locaux après 141.4 : puissance continue, interactions avec la Pile, Protection/capacités accordées et effets d’entrée. Les anciens rapports conservent leur état historique « non publié » au moment de leurs exécutions.

- La dernière régression fonctionnelle complète passe : **4326/4326 tests Python**, aucun échec ni test ignoré. Elle précède le changement de version seul ; elle n’est pas présentée comme une nouvelle exécution sur le tag 141.5.
- `source-equivalence.json` vérifie que remplacer le nouveau tag par l’ancien dans `public/app.js`, `public/index.html` et `public/sw.js` retrouve exactement le digest testé. Aucun autre changement de source fonctionnelle n’a suivi cette régression.
- Les **24 URL JS/CSS**, le client et le service worker utilisent `20261030-rules-beta-141-5`. README est synchronisé.
- Sur les assets finaux : **25/25 contrôles PWA passent**, ainsi que `node tests/test_frontend.cjs`.
- Les **144 contrôles Chrome** du dernier lot correspondent aux sources finales après normalisation du tag. Les anciens périmètres visuels dont des fichiers fonctionnels ont changé restent historiques ; ils ne sont pas annoncés comme réexécutés.
- Le registre strict contient **227/450 cartes (50,4 %)** avec au moins une clause explicitement reliée à des tests réussis. Cela ne certifie pas toutes leurs interactions.

Le registre distingue `currentUnitEvidence: false` (tag différent du lancement Python) et `versionEquivalentUnitEvidence: true` (équivalence exacte vérifiée). Sa copie avant publication est conservée dans `pre-release-coverage.json`, sans réécrire les preuves historiques des audits.

Les journaux et captures restent locaux selon `.gitignore`. Aucun appareil physique ni Safari réel n’est certifié par ces contrôles. Aucun changement VFX supplémentaire n’est introduit dans cette préparation.
