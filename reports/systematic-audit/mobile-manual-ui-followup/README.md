# Destinations tactiles et recherche du Deck

Preuves historiques du panneau ensuite retiré. Le script actuel vérifie le dépôt
direct et écrit dans `mobile-direct-ui-followup/`. Voir
`docs/AUDIT_MOBILE_DIRECT_UI_AFTER_141.md` pour le comportement courant.

- `browser.json` : 156 contrôles réussis, empreintes des huit fichiers de
  production concernés et limites des tests.
- `browser-initial.json` / `initial.log` : première passe, 138 contrôles réussis.
- `overflow/browser.json` : 96 contrôles de débordement réussis sur les sources
  finales ; `overflow/browser-initial.json` conserve leur première passe.
- `manual.log`, `overflow.log`, `frontend.log`, `drag-cleanup.log` : sorties.
- Captures `*-drop-targets.png`, `*-search.png`, `*-filtered.png` : téléphone
  paysage et PC, en italien, avec images locales.

Reproduire sans écraser les anciens rapports de débordement :

```powershell
node tests/test_mobile_manual_ui.cjs
$env:MOBILE_OVERFLOW_PROOF_DIR='reports/systematic-audit/mobile-manual-ui-followup/overflow'
node tests/test_mobile_overflow.cjs
node tests/test_frontend.cjs
node tests/test_drag_cleanup.cjs
```

252 identifiants de contrôles d'interface distincts, plus deux suites voisines.
Les deux places de joueur et les trois langues sont couvertes. Les gestes
tactiles restent émulés dans Chrome ; aucun appareil physique ou clavier
logiciel réel n'est certifié.

Voir `docs/AUDIT_MOBILE_MANUAL_UI_AFTER_141.md` pour les comportements et limites.
Aucun commit ni push.
