# Protection et capacités accordées — preuves locales après 141.4

[Rapport](../../../docs/AUDIT_PROTECTION_KEYWORDS_AFTER_141_4.md) · [Contrat indépendant](../../../audit/protection-keywords.json)

Treize cartes et dix-neuf clauses sélectionnées, dont onze cartes nouvelles pour le registre strict. Les **138 cas liés au lot passent**, collectés depuis [la régression générale finale](unit-tests.json) : **4326/4326 tests réussis**, aucun échec ni test ignoré, en **739,336 secondes**. [La collecte par clause](clauses.json) ne réexécute aucun parcours.

Le [registre courant](../coverage-status.json) atteint **227/450 cartes (50,4 %)** avec au moins une clause explicitement prouvée ; 223 restent hors registre. Aucun lien de preuve n’est exclu. Empreinte commune des sources : `937dee457aced052ffde2d17c763e7aada2144987705d623b07e1e8fa57e33ba`. Cela ne certifie pas tous les effets de ces cartes.

| Couche | Cas |
|---|---:|
| Famille : valeurs, coûts, destinataires et durées | 122 |
| Deux connexions WebSocket et actions réelles | 13 |
| Sensibilité des oracles | 2 |
| Contrôle existant Nectar actualisé et réutilisé | 1 |
| Chrome PC/mobile, deux points de vue | 144 |
| Parité interface/serveur | 609 |

`before.log` contient les 17 échecs initiaux correspondant aux trois défauts décrits dans le rapport. `after.log` contient le premier passage des 96 cas initiaux. `adjacent.log` conserve la régression transitoire de Mimer ; `after-adjacent.log` prouve sa correction avec les 148 scénarios de cette étape. `branches.log` contient les 115 méthodes finales. `network.log` contient douze parcours réussis et le premier essai de sensibilité avec une durée non reconnue ; la suite générale finale exécute le mutant corrigé.

`browser-fixture-initial.json` et `browser-fixture-dormant.json` conservent des erreurs du banc, distinctes des défauts du produit. `browser.json`, `browser.log` et `parity.log` contiennent les validations finales de ces couches.

`potato-before.log` reproduit l’absence de déclenchement d’entrée de Hot Potato. `potato-after.log` valide les 122 méthodes finales, deux tests de sensibilité et le parcours Hot Potato, soit 125 tests. La première régression générale a été interrompue pour ajouter ce cas voisin ; `full-aborted-for-hot-potato.log` conserve ce journal incomplet et n’est pas une preuve de réussite.

`full-before-refresh.log` et `unit-tests-before-refresh.json` contiennent une exécution complète de 4326 tests avec quatre attentes historiques devenues obsolètes après migration des deux capacités. `refresh-tests.log` valide les nouveaux contrôles de comptage et d’entrée de Nectar sans cible. `generated-checks.log` contient dix contrôles réussis après régénération de `public/automation-coverage.json` et des rapports génériques des lots. Les rapports génériques ne sont pas des preuves de validation intégrale des cartes. La dernière suite générale réexécute toutes ces vérifications.

`preflight.json` conserve l’empreinte gelée des sources. `entry-source-review.json` contient le contrôle structurel des douze Persistantes au texte d’entrée correspondant. `full.log` et `unit-tests.json` contiennent la réussite générale finale ; `clauses.json` et `evidence.json` assemblent les identifiants et empreintes de leurs preuves.

Ces preuves portent sur les clauses et branches décrites ; elles ne certifient pas chaque interaction possible. Aucun push.
