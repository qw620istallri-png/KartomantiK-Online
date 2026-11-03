# Publication bêta 150.1.2

Empreinte source : voir `unit-tests.json`.

## Résultats

- **4 363/4 363 tests Python** réussis.
- Zéro échec, test ignoré, identifiant dupliqué ou preuve exclue.
- Frontend général, continuité des choix desktop/mobile et **609 scénarios** de
  parité client/serveur réussis.
- **78/78 gestes réels** réussis sur PC, mobile et vues mixtes.
- Régressions 139.2, Solo desktop/mobile, interactions de Main et **25 contrôles
  PWA** réussis.
- Registre strict : **309/450 cartes (68,7 %)**.

## Ressources

Le client, le service worker et les 24 URL JavaScript/CSS utilisent
`20261103-rules-beta-150-1-2`, affichée `beta 150.1.2`.

## Portée

La table Solo reste orientée sur P1 pendant les actions P2. Les clés de zones
conservent les IDs `solo:p1` et `solo:p2`, les piles ne sont plus dupliquées,
la Main P2 reprend le gabarit adverse normal et les totaux de Confrontation sont
placés vers les bords extérieurs de leurs zones.
