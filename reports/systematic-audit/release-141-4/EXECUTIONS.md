# Validation de publication 141.4

L'ensemble des corrections et audits locaux depuis la 141.3 est publié dans cette version. Les anciens rapports conservent leur état historique « non publié » au moment de leurs exécutions.

- Avant préparation de la version : **3788/3788 tests Python passent**, sans échec ni test ignoré ; preuve dans `../support-permissions-followup/unit-tests.json`.
- Le seul changement de sources après ce résultat est le remplacement de `20261029-rules-beta-141-3` par `20261029-rules-beta-141-4` dans `public/app.js`, `public/index.html` et `public/sw.js`. `source-equivalence.json` vérifie le digest après normalisation de ces trois fichiers.
- Contrôles PWA sur la version finale : **25/25 passent**, preuve dans `pwa/ui.json`.
- Régression fonctionnelle du frontend sur la version finale : **passe**.
- Les 24 URL JS/CSS de l'index, le client et le service worker utilisent le même tag de version.
- Les empreintes des fichiers couverts par les preuves de déplacements manuels (**78/78**) et de Scry (**54/54**) sont identiques ; l'index est comparé après normalisation du seul tag de version. Détail dans `asset-validation.json`.
- Le lot élargi conservé comprend **463 cas**, 40 cartes et 69 clauses sélectionnées ; les 91 tests voisins et les 608 scénarios de parité passaient avant le changement de version seul.

La suite générale exécutée sur les sources finales 141.4 passe : **3788/3788**, aucun échec ni test ignoré, en 617,985 secondes. Le registre strict utilise cette preuve courante et atteint **188/450 cartes (41,8 %)** avec des clauses sélectionnées ; 262 cartes restent hors de ce registre. Toutes les interactions des 188 cartes ne sont pas certifiées.

Commandes de validation finale :

```text
python -c "from pathlib import Path; import run_card_audit as r; r.audit.OUT=Path('reports/systematic-audit/release-141-4'); raise SystemExit(r.units())"
python tools/card_coverage_status.py --units reports/systematic-audit/release-141-4/unit-tests.json --write
PWA_PROOF_DIR=reports/systematic-audit/release-141-4/pwa node tests/test_pwa_install.cjs
node tests/test_frontend.cjs
```

Les journaux et captures restent locaux selon le `.gitignore`. Aucun appareil physique, Safari ou Samsung Internet réel n'est certifié par ces contrôles.
