# Destinations : lot local de six cartes

- `before.json` : 51 méthodes, 49 passent et deux échouent (Revive / Claim ignorent BOB).
- `defer-will-before.json` : après ajout d'oracles fidèles au mot Will du texte, les deux cas de Volonté Éphémère échouent. Le contrat de Defer a été élargi ensuite.
- `clauses.json` : **65 cas passent**, dont **57 méthodes unitaires et huit parcours à deux sockets** ; six clauses, six cartes.
- Un cas ajouté en cours de lot expose aussi Nullify Reason sur l'entrée en Interzone. Le remplacement est maintenant centralisé et les deux ordres concurrents avec BOB passent.
- `full.log` / `unit-tests.json` : régression complète finale. Deux tentatives précédentes ont été interrompues pour corriger le libellé Scry puis compléter le ciblage de Defer ; aucune n'est revendiquée comme validation finale.
- `parity.log` : 608 scénarios client/serveur passent après le changement de capacité de Defer.

La progression stricte n'est mise à jour qu'après la suite complète sur le même digest. Les captures et journaux restent locaux ; JSON, scripts et rapports sont versionnables. Les fixtures et limites de certification sont décrites dans `docs/AUDIT_ZONE_DESTINATIONS_AFTER_141_3.md`.

## Reproduction

Depuis la racine du dépôt, avec les dépendances Python serveur/test et Playwright/Chrome installés :

```powershell
$env:PYTHONPATH='server;tests;tools'
$env:PYTHONIOENCODING='utf-8'
python tools/card_zone_destination_audit.py
```

Ce poste utilise aussi le répertoire existant `C:/Users/istal/Documents/tmp/kko-test-deps` dans PYTHONPATH pour ses dépendances Python locales.
