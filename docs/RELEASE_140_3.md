# Bêta 140.3 — Création de partie et trafic réseau

- Une case « Règles automatisées (bêta) » apparaît à côté de Créer. Elle est
  décochée par défaut et synchronisée avec le réglage existant du menu tournoi.
- Les nouveaux clients négocient un transport incrémental : seuls les champs
  modifiés et les nouvelles entrées du journal sont renvoyés. Les anciens
  clients conservent les états complets. Chaque résolution de pile reste
  distincte, avec la même cadence de présentation.
- Connexion, reconnexion et changement de rôle repartent d'un état complet.
  Une révision manquante déclenche une resynchronisation. Les références sont
  propres à chaque socket, après filtrage des informations privées.
- Les logs `ws_traffic` indiquent le nombre et la taille JSON des messages par
  action. Ces octets avant compression ne sont pas les octets facturés par
  Render. Aucun contenu de carte ni code de partie n'y est enregistré.

Le benchmark local compare 1 078 états reconstruits à l'identique. Le scénario
mixte réduit le JSON d'environ 95 %, celui de la pile d'environ 71 %, tout en
conservant les 33 résolutions. Ces fixtures ne prédisent pas la consommation
mensuelle réelle. Les gains en production dépendent notamment du renouvellement
des clients ouverts. `KKO_STATE_DELTAS=0` permet de désactiver la négociation.

Le [rapport réseau](NETWORK_USAGE.md) décrit le protocole, les mesures, les
compteurs et leurs limites. La validation avant publication conserve ses preuves
historiques dans `reports/network-usage/` ; les vérifications de publication sont
séparées dans `reports/systematic-audit/release-140-3/`.

Version des ressources : `20261027-rules-beta-140-3`, affichée `beta 140.3`.

Validation finale : **1 409 tests Python**, 14 suites navigateur et une suite
JavaScript de transport réussis, aucun échec ni test Python ignoré. Les
[preuves de publication](../reports/systematic-audit/release-140-3/EXECUTIONS.md)
portent une empreinte commune sur les ressources 140.3.
