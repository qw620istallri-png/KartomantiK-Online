# Débordements mobiles — preuves locales

- `before.json` : 72 contrôles, 30 réussis et 42 échecs avant correction.
- `browser-initial-72.json` : première validation, 72 contrôles réussis.
- `browser.json` : suivi de la capture manuelle italienne, 96 réussis,
  aucun échec ; empreintes des sources concernées.
- `*-before.png` : captures de reproduction.
- Les autres captures montrent la fenêtre ou le menu après correction.
- `before.log`, `after.log` : sorties du banc ciblé.
- `after-initial-72.log` : sortie de la première validation.
- `language-setup.json` et `.log` : passe intermédiaire de correction du banc,
  expliquée dans le rapport ; ses échecs ne sont pas des défauts du produit.
- Suite voisine : `node tests/test_frontend.cjs` →
  `Frontend feature regression: OK`.

Commande : `node tests/test_mobile_overflow.cjs`.

Les gestes de défilement tactile et de validation sont natifs dans Chrome émulé.
Les formats 1280 × 576 à DPR 1 et 640 × 288 à DPR 2 sont deux hypothèses pour
la capture fournie, dont la taille est 1280 × 576 pixels. Le menu est explicitement
celui du mode manuel. Les captures `*-touch-it-menu-scrolled.png` montrent le
bouton inférieur avant l'appui qui vérifie son message de déplacement.
Aucun appareil physique, Safari ou Samsung Internet réel n'est certifié.
L'écran demandant de tourner l'appareil est masqué dans le banc pour vérifier
la géométrie en portrait. La production conserve sa demande de mode paysage.

Voir `docs/AUDIT_MOBILE_OVERFLOW_AFTER_141.md` pour les causes, les limites et
le détail des vérifications. Aucun commit ni push de ce correctif.
