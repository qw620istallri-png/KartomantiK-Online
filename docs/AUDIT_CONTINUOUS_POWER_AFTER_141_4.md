# Puissance continue : audit après la 141.4

Ce lot reste local après la version 141.4 (`ebeb398`). Aucun push ni changement de version.

## Corrections reproduites

Les cartes qui entrent en Impasse depuis le Support conservent leur indicateur historique `isSupport`. Cet indicateur ne suffit donc pas à déterminer qu’elles sont encore un Support dans la confrontation courante.

Herbaceous Whisperer et Gargullo pouvaient appliquer leur bonus à un Nubilung arrivé en Impasse par le nettoyage réel de confrontation. Hyperuranic Tower pouvait également lui donner +1 de puissance via Float et un marqueur Abstraction : Nubilung conserve des capacités propres à l’Impasse, mais cela ne le remet pas sur le champ. Le calcul commun des bonus continus du champ exclut maintenant un destinataire en Impasse. Les modificateurs déjà appliqués sont distincts et ne sont pas supprimés par cette correction.

Skapus comptait les anciens Supports en Impasse comme des Supports actuels sous son contrôle. Son +2 pouvait alors disparaître malgré l’absence d’un autre Support dans sa Zone de Confrontation. Son comptage utilise maintenant la collection canonique des Manifestations en Confrontation, filtrée par contrôleur et rôle de Support.

`before.json` conserve **228 méthodes dont quatre en échec** avant ces corrections : trois tests d’aura hors du champ et un test de comptage de Skapus. Ils correspondent à deux problèmes de portée communs, pas à quatre systèmes différents.

## Clauses sélectionnées de 19 cartes

| Carte | Portée des preuves ajoutées |
| --- | --- |
| Sprawling Tentacle | Seuil de quatre Manifestations dans les deux Zones de Confrontation. |
| Prospero of the Bushes | Bonus à la Première Manifestation selon ses Manifestations en Interzone ; promotion d’une nouvelle Première Manifestation. |
| Herbaceous Whisperer | Bonus de +1 aux Supports actuellement contrôlés, jetons compris. |
| Gargullo, King of the Woods | Bonus aux Supports non-jetons selon les autres Manifestations non-jetons de sa Confrontation. |
| Heartening Monument | Bonus de +1 à ses Manifestations en Confrontation. |
| Artificial Thinker | Seuil de cinq Volontés dans son Limbo ; Support et +2 uniquement en Confrontation. |
| Tipson, the Mediator | Bonus selon toutes les cartes de la main du contrôleur. |
| Repelling Urn | Bonus selon les Manifestations du Limbo du contrôleur ; Volontés exclues. |
| Cimba, the Boisterous | Présence d’au moins une Manifestation en Impasse, quel que soit son contrôleur. |
| Planar Beak | Nombre de Manifestations des deux côtés en Impasse ; condition de Confrontation de la source. |
| Skapus, the Vile | Bonus de +2 pour le seul Support actuellement contrôlé en Confrontation. |
| Lucerco the Reckless | Nombre de Manifestations en Confrontation de l’adversaire qui en contrôle le plus. |
| Vengeful Vilupera | Manifestations possédées par le contrôleur dans les deux Vaisseaux ; distinction propriétaire/conteneur. |
| Bell, Ardent Fanatic | Bonus de +2 à son unique Manifestation en Confrontation ; les jetons comptent pour cette condition. |
| Berta, the Peaceful | Plancher à la puissance de base pour les autres Manifestations du champ ; sa propre puissance peut baisser. |
| Hyperuranic Tower | Float avec marqueur Abstraction et bonus de +1 aux Manifestations avec Float sur le champ. |
| Sangen, the Relic | Malus de −1 aux autres Manifestations de l’Interzone de son contrôleur. |
| Kelona, the Anchorite | Malus par carte du Limbo, plafonné à −6 ; les autres bonus restent applicables. |
| Kazadur, the Fiery | Bonus par Manifestation adverse en Confrontation, plafonné à +3 ; les autres bonus restent applicables. |

Le contrat `audit/continuous-power-family.json` épingle le texte complet du catalogue et les valeurs attendues écrites indépendamment : puissance imprimée, puissance avec source active/inactive, changement de contrôle, cumul et zones de fonctionnement. Les attentes ne sont pas calculées à partir des règles encodées.

Les clauses Support déjà prouvées de Sprawling Tentacle, Cimba et Skapus ne sont pas recomptées comme nouvelles cartes. Hyperuranic Tower était également déjà au registre pour une autre preuve. Ce lot ajoute **15 nouvelles cartes et des clauses supplémentaires sur quatre cartes déjà présentes**, après validation de la suite générale.

Les autres paragraphes, notamment la victoire de Sangen, son interdiction de remplacement, le Chain de Kazadur ou le déplacement de marqueurs de la Tower, ne sont pas certifiés par cette preuve. Pour Sangen, seule la proposition du malus d’Interzone est sélectionnée.

## Validation ciblée

- **228 méthodes unitaires** : valeurs exactes, zones, source face cachée/sans effets/partie du champ, contrôle, lecture sans mutation ni objet sur la pile, phases et tours, cumul, Cleanse, Discombobulator, destinataires et variations de compteurs.
- Les seuils et plafonds sont vérifiés de part et d’autre : quatre Manifestations, cinq Volontés, −6 de Kelona et +3 de Kazadur. Les bonus additionnels dépassant le plafond du seul effet restent pris en compte.
- **Onze parcours à deux connexions WebSocket** jouent réellement Defer en payant deux essences vitreuses. La valeur ne change pas avant résolution ; les deux clients reçoivent ensuite la puissance exacte. La carte déplacée est vérifiée au-dessus du Deck de son propriétaire.
- **Deux tests de sensibilité** injectent volontairement un mauvais bonus de Whisperer et un mauvais plafond de Kazadur : les oracles indépendants doivent détecter ces erreurs.
- **228 contrôles de navigateur** : les 19 cartes, source active/privée d’effets/rétablie, les deux points de vue et deux formats Chrome (PC et mobile paysage). Les badges de modificateur sont comparés aux valeurs littérales, sans doublon ni erreur de script. Les états viennent de la sérialisation publique du serveur ; les illustrations sont remplacées par une image locale.
- **381 tests voisins passent**, concernant les changements de puissance, leur ordre, Cleanse, événements observés, Support et copies.

Le lanceur `tools/card_continuous_power_audit.py --units <preuve générale courante>` assemble les clauses à partir des identifiants réellement exécutés dans la suite générale, sans relancer les mêmes parcours réseau pour produire le rapport.

## Fixtures corrigées et limites

Le premier banc avait omis un alias de recherche de carte pour les tests Cleanse et ne rafraîchissait pas les Premières Manifestations après un changement de contrôle. Ces erreurs du banc ne sont pas des défauts du moteur. Deux essais ultérieurs tentaient de créer directement un jeton en Impasse avec une API qui crée des Supports ; les conditions d’Impasse utilisent maintenant des Manifestations réelles. Les jetons/copies de la mécanique normale ne restent pas en Impasse.

Les comptes, cibles synthétiques de puissance 5, contrôles et résultats de comparaison sont des états initiaux contrôlés. La recherche des règles, le calcul, Cleanse, le nettoyage de confrontation et les parcours Defer utilisent le code de production. L’avance automatique des phases est désactivée dans les onze parcours réseau pour isoler les interactions. Les tests Chrome prouvent le rendu DOM des modificateurs ; ils ne certifient ni une partie complète, ni toutes les interactions, ni les illustrations distantes, ni un téléphone physique ou Safari réel.

Validation finale : **4029/4029 tests Python passent**, aucun échec ni test ignoré, en 640,485 secondes. Les **241 cas du lot** (228 unitaires, onze parcours réseau, deux tests de sensibilité) sont assemblés depuis cette exécution générale sans les relancer. Les 228 contrôles Chrome restent liés aux empreintes courantes de leurs sources testées.

Le registre strict atteint **203/450 cartes (45,1 %)**, soit 15 nouvelles et 247 hors registre. Les 20 clauses de 19 cartes ne certifient pas tous leurs paragraphes ou toutes leurs interactions. Les preuves du lot, de la suite générale et du registre ont le même digest courant. **Aucun push.**
