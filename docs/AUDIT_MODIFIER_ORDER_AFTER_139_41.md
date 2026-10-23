# Audit de l'ordre et de la durée des modificateurs

Passe du 23 octobre 2026, après 139.41. Corrections intégrées à la version 139.42 à la demande du joueur.

## Arbitrages confirmés par le joueur

- Les changements de tempérament suivent l'ordre réel de résolution de la Pile : Mask bleu résolu avant une copie rouge donne finalement rouge. Un Mask résolu après cette copie prend le dessus jusqu'à son expiration.
- Mimer mémorise la puissance courante de sa cible comme nouvelle puissance de base. Ses propres bonus restent appliqués : copier une puissance de 4 en ayant +2 donne 6. Les changements ultérieurs de la cible n'actualisent pas la copie.
- Inflate the Ego ajuste la puissance courante à 10 à sa résolution et impose un plafond de 10. Un malus de −2 résolu ensuite donne 8.

## Défauts corrigés

- Les copies et changements de tempérament étaient traités par catégories, ce qui donnait toujours priorité à Mask. Ils sont maintenant lus dans leur ordre de résolution. Humiliate et les résultats de dés qui rendent Hollow participent au même ordre.
- Entrust modifiait un drapeau lu avant les copies, indépendamment de sa résolution. Le doublement devient un modificateur ordonné de la base : copie de 5 puis Entrust donne 10 ; Entrust puis copie de 5 donne 5. Les bonus additifs ne sont pas doublés.
- Le calcul de Berta utilisait parfois la puissance imprimée comme plancher, alors que les autres règles utilisaient la base copiée. Les deux lectures utilisent désormais la même base.
- La puissance fixée par Inflate ignorait les malus suivants. Le moteur mémorise désormais l'ajustement appliqué à la résolution, puis applique les autres modificateurs et le plafond. Les autres créateurs de `power_set_maximum` utilisent le même calcul.
- Le verrouillage global des Points de Haltan était supprimé au nettoyage des effets, faute de carte cible. Une cible globale reste valide jusqu'à l'échéance de l'effet, même si sa source a été sacrifiée.
- L'expiration d'un bonus pouvait laisser une Manifestation à zéro déclencher son début de tour. Les actions d'état sont maintenant vérifiées après expiration, avant la collecte des déclenchements de début de tour. Leurs propres déclenchements sont conservés et la pioche attend les choix et effets requis.
- Les remplacements concurrents pendant cette transition passent par un point de reprise atomique : choix avant toute modification du tour ou de la carte, puis reprise et journalisation uniques, y compris après reconnexion.

## Vérifications

- Suite Python complète : **843 tests réussis** au premier passage final, incluant les 14 premières régressions de cet audit.
- Deux régressions complémentaires passent également : persistance copie/doublement malgré la perte d'effets et le passage en Stalemate, nettoyage à la sortie du champ ; échéances distinctes de Mirrorbeast et de son propre bonus.
- `tests/test_modifier_order_audit.py` : **15 tests**, avec permutations des résolutions, bonus/malus, Cleanse et compteurs, sources continues privées d'effets, expiration et remplacements concurrents.
- `tests/test_modifier_order_integration.py` : reconnexion, rejeu d'une réponse refusé, tour avancé une seule fois et journal d'expiration conservé par le vrai serveur WebSocket.
- Régressions générales de l'interface : réussies.
- Catalogue : **379 cartes, 496 capacités, 500 variantes exécutées, aucun échec**.

Cette passe couvre ces familles de modificateurs et leurs cas voisins reproduits ; elle ne prouve pas toutes les combinaisons possibles du catalogue.
