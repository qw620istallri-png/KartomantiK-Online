# Pile : preuve navigateur, signalement Safari Mac ouvert

`browser.json` : 24 cas exécutés, tous réussis, dans Chrome installé et WebKit
27.2 sur Windows. Deux tailles de bureau, piles assistées classique/bêta et
pile manuelle bêta, images locales et quatre illustrations distantes avec
chargement retardé, réaffichage en cours de chargement et agrandissement bêta.

Les assertions portent sur le décodage, les styles de visibilité, les dimensions,
le ratio et l'inclusion dans la ligne. Les captures confirment visuellement les
deux profils de la pile assistée bêta à 1 440 × 1 000. La peinture de chaque
configuration n'est pas certifiée par les seules dimensions calculées.

Les captures sans suffixe correspondent à la première passe, conservée dans
`initial-local.json`. Celles avec `local` ou `remote-delayed-expanded` font partie
de la dernière exécution. Les versions, URLs, dates et empreintes des fichiers
client sélectionnés figurent dans `browser.json`.

Commande : `node tests/test_stack_browser_compat.cjs`. WebKit doit être installé
avec la version de Playwright du dépôt ; ici `PLAYWRIGHT_BROWSERS_PATH` pointe
vers `C:/Users/istal/Documents/tmp/kko-playwright-browsers`.

**Pas de reproduction ni de certification de Safari Mac.** Aucun correctif de
production n'a été ajouté pour ce signalement. Aucun commit ni push.
