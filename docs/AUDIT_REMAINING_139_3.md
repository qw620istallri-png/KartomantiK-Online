# Audits complémentaires — 139.3

Périmètre : compléter les audits déjà publiés en 139.2.2 et celui des choix atomiques, sans modifier les règles de capture selon le propriétaire. Référence : livret courant, §3.2 pages 19–20 (propriété, contrôle, indépendance des effets, modificateurs et mémoire), et texte imprimé des cartes.

## Déplacements simultanés et ordre

Parcours relus : retours des Supports de Timidette et Gusted Nebula ; répartition dessus/dessous de deck ; relocalisation de confrontation ; ordre des actions simultanées.

Défauts corrigés :

1. Timidette suivait l’ordre du plateau malgré « in any order ». Son contrôleur ordonne désormais les cartes sous chaque deck, via le choix existant de retour des Supports.
2. Les retours des Supports contournaient les remplacements de déplacement. Ils passent désormais par le déplacement provoqué par un effet ; BOB suspend bien les cartes concernées.
3. Le sélecteur n’est plus proposé si aucun deck ne reçoit au moins deux cartes réelles. Les copies disparaissent sans demander un ordre qui ne changerait aucun deck.

Les cartes protégées et Timidette restent en place. La branche de dessous conserve son ordre de gauche à droite ; la branche de dessus conserve son insertion inversée. Le bonus de Gusted Nebula reste distinct de Timidette.

## Copies, effets temporaires et mémoire

Parcours relus : création des copies/jetons et leurs effets d’entrée, copie de caractéristiques, sortie du champ, suspension, mémoire de victoire/résolution, échéances de fin de tour et du tour suivant. Les scénarios existants couvrent aussi Mirrorbeast, Cleanse, changements de contrôle et destinations de confrontation.

Défauts corrigés :

- Mimer conservait un instantané calculé par une lecture précédente ; en l’absence de lecture ou après une modification récente de la cible, sa copie pouvait être périmée à son départ. L’instantané est désormais pris avant l’extraction, y compris en cas de suspension.
- Le retour anticipé des copies dans la routine de sortie omettait la libération des cartes suspendues. Une copie de BOB libère désormais ses suspensions à sa disparition.
- Les mémoires liées à un objet du champ conservaient l’ancien identifiant après un passage par les Limbes/la main. Le retour de la carte réelle rétablit ce lien ; une copie ne le récupère pas et ses propres mémoires disparaissent avec elle.

Contrôles sans anomalie supplémentaire reproduite : compteurs indépendants des copies, effets désactivés et absence de déclencheur d’entrée dans ce cas, disparition sans carte ajoutée au deck, mémoire conservée en Limbes/main et effacée en deck/exil, expiration aux deux bornes de tour prévues.

## Confidentialité réseau

Parcours relus : sérialisation des zones et des cartes couvertes, choix en attente, actions en pile et dernière résolution, journal récent/complet, suspension et retour, reconnexion et rôles de lecture.

Défauts corrigés : les choix privés étaient déjà filtrés pendant leur affichage, mais leurs résultats pouvaient révéler les cartes après validation via le journal ou une résolution imbriquée. Le filtrage par destinataire s’applique désormais aussi à ces chemins : inspection, dessus/dessous, recherche privée/couverte, remise d’une carte de main sous le deck, nouvelles cartes piochées et retour privé de suspension. Les champs internes préfixés `_` ne partent pas dans ces charges utiles publiques.

Les tests utilisent des identifiants sentinelles dans l’état entier et les journaux. Ils vérifient les deux modes de table, l’adversaire, le spectateur, l’organisateur, les accès privilégiés existants, et l’absence de mutation de l’état serveur par le filtrage. Un test WebSocket résout un ordre privé, demande le journal adverse puis reconnecte l’adversaire : aucune carte du deck privé n’apparaît dans ces réponses. Les révélations volontaires et recherches publiques vers l’Interzone restent visibles.

## Preuves et limite

`test_remaining_rules_audit.py` contient 13 tests avec variantes ; les cinq tests réseau de `test_choice_reconnect.py` complètent les neuf tests d’atomicité. Le test navigateur de version vérifie également le sélecteur sous le deck sur PC et mobile.

Tous les défauts reproduits dans ce périmètre sont corrigés. La validation de catalogue est un contrôle d’exécution des capacités encodées, pas une exploration exhaustive de toutes les combinaisons de cartes, de réponses et de connexions.
