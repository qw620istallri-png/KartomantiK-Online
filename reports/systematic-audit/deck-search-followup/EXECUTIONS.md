# Recherches et déclarations de noms : preuves locales

Empreinte globale : `18eabc370ab143d1eb1e00e08453a1563f6b653832fa035bf7a0c6e17b3498bc`

| Couche | Résultat |
| --- | --- |
| Clauses sélectionnées | 25 tests, quatre paragraphes de quatre cartes, tous réussis |
| Réseau réel | Deux scénarios à deux sièges, inclus dans les 25 tests |
| Python complet | 1 345 tests réussis, aucun échec ni test ignoré |
| UI | Cinq suites réussies : nouveau parcours, interface sémantique, frontend, continuité des choix, parité |
| Nouveau parcours navigateur | Six configurations Chrome : trois langues, PC et mobile paysage |

[Clauses et sous-cas](clauses.json) · [suite Python](unit-tests.json) ·
[commandes UI](ui-tests.json) · [configurations navigateur](browser.json) ·
[preuves agrégées](evidence.json) · [méthode et limites](../../../docs/AUDIT_DECK_SEARCH_AFTER_140_1.md)

## Échecs conservés

`before.json` conserve la reproduction avant correction : 20 méthodes, six
méthodes en échec. Les cinq méthodes ajoutées ensuite vérifient le parcours réel
de Recall, les refus/rejeux de Mejik, les résultats dissimulés et le réseau.

`regression-before.json` conserve la première suite complète : 1 344 méthodes
réussies et un échec de rapport généré périmé. Le rapport de scénarios a ensuite
été régénéré ; seuls les compteurs de messages globaux (530 à 528) et de Mejik
(3 à 1) changent. Les quatre tests de cohérence, puis les 1 345 tests complets,
ont été rejoués avec succès. La couche navigateur large de cet artefact reste
historique ; sa régénération ne la certifie pas à nouveau.

## Limites

Les attentes sont écrites depuis le texte imprimé et associées explicitement aux
tests. Certaines résolutions sont isolées de la déclaration et les résultats de
confrontation de Recall sont préparés. Les deux tests réseau maintiennent le
pilote automatique à l'arrêt pour isoler le transport.

Les autres clauses et interactions du catalogue restent à compléter. Pas de
nouvelle matrice, trace générale, campagne navigateur des 450 cartes, contrôle
des illustrations distantes ou essai sur appareil physique. Le signalement
Safari Mac reste ouvert.

Version 140.1 inchangée, aucun commit ni push. Les corrections locales précédentes
et leurs preuves historiques sont conservées.
