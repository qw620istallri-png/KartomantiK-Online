# Auto-skip et phases : preuves locales

Empreinte : `77930a3a630db37fb265e4423d2f90fd7c35d29dba6f078940c830018e9166d6`

| Couche | Résultat |
| --- | --- |
| Nouvelle couverture | 19 méthodes : 16 invariants et trois scénarios réseau |
| Campagne ciblée avec régressions voisines | 59 tests réussis, aucun échec ni test ignoré |
| Suite Python complète | 1 364 réussis, aucun échec ni test ignoré |
| Interface | Quatre suites réussies : parité, continuité des choix, connexion, frontend |

[Scénarios et sous-cas](sequences.json) · [Python complet](unit-tests.json) ·
[commandes UI](ui-tests.json) · [preuves agrégées](evidence.json) ·
[méthode et limites](../../../docs/AUDIT_AUTO_PHASES_AFTER_140_1.md)

## Reproductions conservées

`before.json` : 13 méthodes avant correction, cinq méthodes en échec,
avec sept échecs de sous-cas. `boundary-before.json` conserve le second cas :
la pile vide exactement à la limite, avant reprise des phases passables.
Les deux fichiers portent leurs empreintes historiques.

Les longues piles continuent désormais par lots coopératifs sous le même verrou.
Les règles et choix sont réévalués après chaque lot. Les états manuels/inactifs
ne passent plus dans ce pilote, y compris pour une pile immédiate résiduelle
injectée dans un test défensif.

## Étendue et limites

Les quinze sous-phases sont exercées avec une pile synthétique : les valeurs
100, 110 et 111 et les tailles 2, 1 et 0 doivent apparaître dans cet ordre, sans
changer de phase/tour pendant le vidage. Les tests réseau utilisent le pilote
réel avec deux lecteurs actifs. La pause configurée de 1,7 seconde est observée
mais raccourcie dans le banc : pas de mesure de latence Internet ou de fluidité.

La comparaison de disponibilité prépare 182 déclarations du catalogue ; les
180 acceptées ne sont jamais marquées sans action. Ses fixtures sont généreuses
et peuvent avoir plusieurs actions : ce contrôle ne certifie pas toutes les
conditions de chaque carte. Les origines Grimoire/Limbo/Suspension sont aussi
contrôlées avec de vraies déclarations de Strengthen.

Les dix scénarios réseau de latence précédents sont rejoués et inclus dans les
59 tests ciblés. Les nouvelles preuves ne certifient pas une campagne générale
des 450 cartes, un appareil physique, un client non lecteur ou Safari Mac réel.

Version 140.1 inchangée ; aucun commit ni push. Les modifications locales des
passes précédentes et leurs preuves historiques sont conservées.
