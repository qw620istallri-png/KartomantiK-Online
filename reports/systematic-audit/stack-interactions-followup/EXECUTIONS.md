# Interactions de Pile — preuves locales après 141.4

[Rapport et limites](../../../docs/AUDIT_STACK_INTERACTIONS_AFTER_141_4.md) · [Contrat indépendant](../../../audit/stack-interactions.json) · [Arbitrages confirmés](../../../audit/rule-decisions.json)

Treize cartes et dix-huit clauses sélectionnées. Les **174 cas liés au lot passent**, collectés depuis [la régression générale](unit-tests.json) de **4189/4189 tests réussis**, sans échec ni test ignoré, en **665,682 secondes**. Aucun test n’a été réexécuté pour assembler [les liens par clause](clauses.json). Ces liens ne certifient pas tous les paragraphes ni toutes les interactions des cartes.

Le [registre courant](../coverage-status.json) atteint **216/450 cartes (48 %)** avec au moins une clause explicitement prouvée ; 234 restent hors registre. Treize cartes s’ajoutent au lot précédent de 203, sans exclusion de lien. Empreinte commune des sources : `6bf2cb5c72398414778b75017fc86e4bdf5a523b682a0d9e525339df52dc7741`.

| Couche | Cas | État ciblé |
|---|---:|---|
| Famille de réponses | 129 | coûts, cibles, copies, valeurs et destinations |
| Déclenchements / tribut | 12 | déclarations payées et producteur public |
| Deux clients WebSocket | 17 | réponses, copies et synchronisation |
| Sensibilité des oracles | 2 | mauvais coût / mauvaise destination détectés |
| Duel existant, réutilisé | 14 | paiement intrinsèque et neutralisation |
| Chrome PC + mobile paysage | 100 | candidats d’interface, dont copies |
| Parité interface / serveur | 608 | catalogue des règles de cibles |

## Journaux conservés

- `before.json` et `before.log` : perte de la couleur choisie de Radiance lorsque la source est absente.
- `clemency-before.json` et `clemency-before.log` : choix inutile de Clemency si la Volonté est absente ou non neutralisable.
- `rulings-before.log` : propriétaire incorrect des copies, copie Persistante absente du champ et effet Eorthoda séparé avant les corrections.
- `rulings-after.log` : validation ciblée avant les deux derniers cas Thoughtcutter et les deux nouveaux parcours de copies.
- `copy-branches.log` : 129 méthodes de famille finales et deux nouveaux parcours réseau réussis.
- `browser.json`, `browser.log`, `parity.log` et `choice-ui.log` : résultats des contrôles d’interface et de continuité des choix.
- `browser-fixture-initial.json` et `triggers-initial.log` : essais initiaux incluant des erreurs de banc décrites dans le rapport ; ils ne sont pas présentés comme des défauts supplémentaires du jeu.
- `preflight.json` : empreinte gelée des sources et vérification des périmètres des deux lots de preuves Chrome.
- `full.log` et `unit-tests.json` : régression générale finale et identifiants réellement exécutés.
- `clauses.json` et `evidence.json` : collecte finale et empreintes des preuves.

Les illustrations distantes, Safari réel et les appareils physiques sont hors de ce lot. L’avance automatique des phases est désactivée dans les parcours réseau pour isoler les réponses de Pile. Aucun push.
