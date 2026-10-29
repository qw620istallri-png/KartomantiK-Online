# Dépôts directs et cartes à droite

- `browser.json` / `manual.log` : 168 contrôles réussis, empreintes des sources.
- `overflow/browser.json` / `overflow.log` : 96 contrôles réussis sur les sources
  finales ; les sorties initiales restent dans les fichiers `initial`.
- `frontend.log`, `drag-cleanup.log` : suites voisines réussies.
- `initial.json`, `initial.log` : préparation intermédiaire du banc d'inspection,
  expliquée dans le rapport, avec son état d'inspection non fermé en cascade.
- Captures `*-search.png`, `*-filtered.png`, `*-hold-stack.png` et `overflow/` :
  disposition sur ordinateur et téléphone paysage, images locales.

```powershell
node tests/test_mobile_manual_ui.cjs
$env:MOBILE_OVERFLOW_PROOF_DIR='reports/systematic-audit/mobile-direct-ui-followup/overflow'
node tests/test_mobile_overflow.cjs
node tests/test_frontend.cjs
node tests/test_drag_cleanup.cjs
```

264 identifiants de contrôles d'interface distincts, plus deux suites voisines.
Le panneau de destinations de l'itération précédente est retiré. Les gestes
tactiles sont émulés dans Chrome ; aucune certification d'appareil physique ou
de clavier logiciel réel. Voir `docs/AUDIT_MOBILE_DIRECT_UI_AFTER_141.md`.

Aucun commit ni push.
