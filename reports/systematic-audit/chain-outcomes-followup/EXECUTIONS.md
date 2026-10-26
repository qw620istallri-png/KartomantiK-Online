# Clauses d’Enchaînement : preuves locales

Empreinte : `aad3d2b69320c67e84136e284b6d9a180f17b1f15c4997a3553844f3023d56c7`

| Couche | Résultat |
| --- | --- |
| Clauses sélectionnées | 31 tests, 15 paragraphes de 8 cartes ; tous réussis |
| Deux sièges WebSocket réels | 2 scénarios de choix, confidentialité, reconnexion et rejeu, inclus dans les 31 tests |
| Python complet | 1 301 réussis, aucun échec ni test ignoré |
| UI ciblée | 4 suites réussies : parité, continuité des choix, connexion, interface sémantique |

La suite complète inclut les 31 nouveaux tests et le scénario Baranchio corrigé pour distinguer verrou individuel et global. La première exécution avec son ancienne attente contradictoire est conservée dans regression-before.json.

La validation documentaire des 450 fiches / 760 paragraphes reste structurellement valide ; elle ne certifie pas toutes leurs clauses à l’exécution.

## Limites et couverture restante

- Other unlisted card clauses and alternative branches need independent executed expectations.
- Simultaneous conflicting memories and duplicate cards moving through hidden zones remain outside this batch.
- No new broad 450-card browser, matrix, remote-art or physical-device execution in this batch.

Certaines actions sont isolées à la résolution et les vainqueurs sont explicitement préparés dans plusieurs cas. Les scénarios réseau maintiennent le pilote automatique à l’arrêt pour isoler le transport des choix.

[Clauses et sous-cas exécutés](clauses.json) · [preuves agrégées](evidence.json) · [correctifs et méthode](../../../docs/AUDIT_CHAIN_OUTCOMES_AFTER_140_1.md)

Travail local : version inchangée ; aucun commit ni push. Les preuves antérieures sont conservées sous leur empreinte historique.
