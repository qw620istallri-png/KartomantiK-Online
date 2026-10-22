# Audit des interactions — après 139.3

Passe locale du 22 octobre 2026. Périmètre demandé : exemplaires identiques, remplacements combinés, disparition/désactivation des sources, paiements interrompus. Corrections intégrées à la version 139.4, publiée à la demande du joueur.

## 1. Identité des cartes

Les decks réglementaires sont uniques par carte (`validate_tournament_deck`). L’hypothèse de deux exemplaires réels du même propriétaire ne correspond donc pas à un deck réglementaire. Les cas légaux vérifiés sont deux propriétaires possédant la même référence et les copies créées par les effets.

Le test confirme que remettre au deck la carte d’un propriétaire n’efface pas la mémoire de celle de l’autre propriétaire. Une copie n’hérite pas de la mémoire de la carte réelle. Aucun nouveau défaut reproduit sur ces cas ; les protections de 139.3 sont conservées.

## 2. Remplacements combinés

La règle de départage a été précisée par le propriétaire du projet pendant cet audit : chaque joueur ordonne ses propres effets simultanés ; entre contrôleurs différents, le joueur prioritaire (le perdant pendant la Confrontation) place son lot en premier dans la pile, donc le lot adverse se résout d’abord.

Le moteur applique désormais ce classement aux remplacements concurrents de déplacement. Pour un même contrôleur, un sélecteur réutilise le glisser-déposer de l’ordre simultané : l’effet à appliquer en premier est à gauche. Les sources de suspension distinctes restent distinguées ; des remplacements identiques vers le même exil ne provoquent pas de confirmation inutile. Le premier remplacement déplace la carte hors de sa source initiale.

Le choix se prépare sur une copie isolée de l’état, avant toute modification réelle. Cela couvre les résolutions de pile, les effets, les réponses aux choix de cartes et les déclarations dont le paiement entraîne un déplacement concurrent. Les coûts ne sont pas payés pendant cette préparation. Un flux aléatoire privé est conservé pendant le choix pour que la reprise ne relance pas les dés et ne modifie pas les tirages d’autres parties.

Autres défauts reproduits et corrigés :

- Quasimillenary : une Manifestation issue de sa pioche des Limbes pouvait revenir en main depuis le champ au lieu d’être exilée. L’exception du Réceptacle est conservée ; sa marque est effacée chez son propriétaire, même lorsqu’elle entre dans le Réceptacle adverse.
- Nullify Reason : le déplacement réel vers l’exil pouvait être enregistré comme une entrée aux Limbes, produisant des événements de destruction/défausse erronés. Les entrées sont maintenant enregistrées selon la destination réelle.
- Le retour des cartes suspendues par un BOB pouvait contourner un second BOB encore actif. Les remplacements s’appliquent aussi à ce retour.
- La suspension d’un porteur faisait disparaître les cartes attachées sans destination. Leur nettoyage habituel s’applique désormais aussi à la suspension.

## 3. Sources disparues ou désactivées

Un effet activé déjà en pile reste indépendant du départ de sa source : vérifié avec Drildrill. Les liaisons qui exigent réellement la présence de la source cessent à son départ.

Deux défauts corrigés :

- Mimer perdait sa copie de puissance/couleur déjà résolue lorsqu’il perdait ses capacités. Ce modificateur reste acquis ; il n’autorise pas de nouvelle activation pendant la désactivation.
- Les liaisons continues étaient supprimées définitivement par une désactivation temporaire. Elles sont maintenant conservées mais inactives, puis reprennent si la source retrouve ses effets. Les contrôles portent sur Flaying Jaw, Annihilating Nectar, Armored Husk, Altruistic Inflorescence et Thought Saboteur. Les liaisons inactives ne sont pas envoyées au client comme des effets applicables.

Une rectification concerne aussi la passe 139.2.2 : le glossaire du livret, page 39, précise que Stalemate conserve le contrôleur et les modificateurs. Cette exception spécifique prime la règle générale des entrées en zone partagée. Le nettoyage ne rétablit donc plus le propriétaire comme contrôleur en cas de Stalemate ; le test utilise deux exemplaires de propriétaires distincts et vérifie aussi la puissance conservée. Les captures ordinaires selon le propriétaire restent inchangées.

## 4. Paiements interrompus

Défauts corrigés :

- Un tribut autorisé depuis les Limbes pouvait consommer les essences puis être suspendu par BOB et lever `Validated Limbo Tribute payment failed`. Un coût utilise désormais le déplacement de coût ; BOB ne le remplace pas comme un déplacement provoqué par un effet.
- Le sacrifice d’une source contournait la sortie commune du champ et oubliait ses cartes attachées ou suspendues. Il conserve les remplacements propres à la carte et effectue ce nettoyage.

Les tests par WebSocket réel couvrent `effect_payment`, `effect_memory_payment`, `immediate_effect_payment` et `stack_counter_payment` : refus sans dépense, mauvaise identité, déconnexion/reconnexion, validation, double envoi sans double dépense. Une essence convertie depuis un Gem avant la déconnexion reste disponible et n’est consommée qu’une fois. La reprise réseau du nouveau choix de remplacement conserve aussi une seule résolution et une seule entrée de journal.

## Complément : The Stomper

Selon la précision du joueur, sa puissance de base doit être strictement supérieure à celle des autres Premières Manifestations. Une égalité ne déclenche plus son effet immédiat, même avec un tempérament dominant. La condition est également vérifiée à la résolution. Cinq tests dédiés couvrent égalité, puissance supérieure/inférieure, bonus de puissance et présence en Support.

## Validation

- `test_interaction_edge_audit.py` : 13 tests, dont des variantes sur cinq liaisons continues.
- `test_replacement_order_audit.py` : 9 tests, incluant les lots de contrôleurs, les reprises, les réponses invalides, l’absence de déplacement partiel et l’absence de dépense avant le choix d’un remplacement pendant un paiement.
- `test_payment_interruption_audit.py` : 6 tests par serveur WebSocket réel.
- **Suite Python complète : 810 tests réussis** sur l’état final, y compris la rectification de Stalemate.
- Navigateur : parcours de version PC/mobile et régressions générales réussis ; le sélecteur affiche suspension/exil et transmet l’ordre attendu.
- Catalogue : 496 capacités, 500 variantes d’état, 379 cartes, aucune carte en échec ; registre d’automatisation à jour.

Les preuves portent sur ces parcours et les régressions existantes. Elles ne constituent pas une exploration exhaustive de toutes les combinaisons de cartes.
