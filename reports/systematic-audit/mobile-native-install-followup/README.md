# Installation native — suivi de 141.1

- `before.json` : reproduction de la régression sur 141.1, 20 contrôles,
  11 réussis, 9 échoués, sans rendu navigateur.
- `ui.json` : 25 contrôles réussis sur la correction, empreintes des six fichiers
  de production concernés et limites des essais.
- `*-home.png`, `*-guide.png`, `*-native-ready.png` : captures finales en Chrome.
- Suite voisine exécutée : `node tests/test_frontend.cjs` →
  `Frontend feature regression: OK`.

Reproduire : `node tests/test_pwa_install.cjs`.
Le répertoire peut être changé avec `PWA_PROOF_DIR` pour préserver ces preuves.
`--unit-only` exclut les quatre rendus navigateur.

Les événements natifs sont simulés. Les tests vérifient la conservation de la
promotion du navigateur, l'appel de `prompt()` pendant le geste utilisateur,
l'arrivée tardive dans le guide, les traductions Samsung, la consommation unique,
le refus, l'échec et l'installation avant/après initialisation. Aucune installation
physique ni garantie de déclenchement automatique n'est revendiquée.
