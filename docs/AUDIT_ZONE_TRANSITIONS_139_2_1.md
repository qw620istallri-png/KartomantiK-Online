# Corrections de l'audit des transferts — après 139.2.1

Les trois problèmes du précédent audit sont corrigés localement. Version inchangée, aucun push.

- **Cible ayant quitté sa zone** : la validation des cibles hors champ vérifie leur présence actuelle à la résolution. Le résolveur de réanimation vérifie aussi l'extraction effective avant de construire le Support. Reforging Fate ne duplique plus une carte exilée en réponse par Extinguish Nostalgia.
- **Suspension de BOB** : la réanimation applique le même mécanisme de remplacement que les déplacements ordinaires. Les choix de répartition dessus/dessous appliquent aussi les remplacements aux cartes transférées depuis le Limbo ou mises de côté depuis le deck. Un simple réordonnancement de cartes restant dans le deck reste possible. Les résultats distinguent les cartes réellement placées et les remplacements par suspension.
- **Entrée après réanimation** : les effets d'entrée et les observateurs concernés rejoignent la procédure de pile après résolution de la réanimation. Keen-eyed Seeker pioche une fois pour son contrôleur. Urolong conserve son exception : la carte réanimée perd ses effets et ne déclenche pas son propre effet d'entrée.

Validation : **739 tests Python réussis** ; contrôles navigateur PC/mobile réussis. Sept tests de régression avec sous-cas sont ajoutés dans tests/test_zone_transition_audit.py : réponse exilant la cible, protection du résolveur direct, seuils de BOB, libération vers le deck du propriétaire, choix différé de Caress, effet d'entrée sous un nouveau contrôleur et exception d'Urolong.

Un test historique d'Everspring place désormais ses cibles dans le Réceptacle avant de vérifier leur validité. Les messages concernant une mauvaise zone conservent leur priorité sur l'erreur de présence.

L'audit suivant vérifie les destinations après confrontation lorsque propriétaire et contrôleur diffèrent, ainsi que la libération des cartes suspendues lorsque BOB change de zone sans quitter le champ. Les nouvelles observations de cet audit restent à corriger.
