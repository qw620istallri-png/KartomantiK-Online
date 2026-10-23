# Audit des cibles et copies de la Stack après 139.43

Passe du 23 octobre 2026. Corrections intégrées à la version 139.44 à la demande
du joueur.

## Règle confirmée par le joueur

Un effet à plusieurs cibles indépendantes se résout autant que possible. Si un
Support ciblé par Multicastigate disparaît ou devient Protégé, l'autre Support
encore valide est détruit. L'effet entier échoue seulement si aucune cible n'est
encore valide. Les coûts payés ne sont pas remboursés.

## Défauts corrigés

- La résolution rejetait tout l'effet dès qu'une seule cible devenait invalide,
  alors que la détection de résolution automatique conservait correctement la
  fenêtre de réponse tant qu'une cible restait valide. Les deux parcours utilisent
  désormais la même vérification individuelle. L'exécution ignore les cibles
  invalides, mais l'historique conserve les cibles déclarées et leurs indices
  invalidés. Les contrôles du nombre de cibles à la déclaration restent stricts.
- Les contrats `self` et `opponent` relisaient le contrôleur stocké plutôt que les
  liens de contrôle actifs. Ils utilisent maintenant le contrôleur effectif,
  notamment pour Thought Saboteur et sa neutralisation temporaire.
- Les contrats de type utilisaient le type imprimé sur les cartes du champ. Une
  Volonté animée est maintenant ciblable comme Manifestation côté serveur et dans
  l'interface. Après annulation de l'animation, une cible Manifestation n'est plus
  valide. Les cartes des zones publiques gardent leur type imprimé.
- Copier une Volonté avec des groupes de cibles sautait le choix serveur, et le
  parcours client ne pouvait envoyer qu'une cible. Le choix s'ouvre désormais pour
  ces contrats, rassemble tous les groupes, et propose une confirmation pour les
  contrats sans groupes à plusieurs cibles. La copie reste un objet de Stack sans
  deuxième carte physique ni nouveau paiement.

## Cas de dépendance vérifiés

- Un transfert de compteur ou un échange de contrôle exige encore ses deux cibles
  valides : une résolution partielle ne transforme pas un donneur en receveur et
  ne prend pas la moitié d'une paire.
- Shattering the Self défausse les trois cartes du joueur encore ciblable même si
  la Manifestation est devenue Protégée ; aucun malus ne lui est alors appliqué.
- Une capacité déjà sur la Stack garde son contrôleur si sa source change de
  contrôle ou quitte le champ. Un modificateur indépendant de la source continue
  de se résoudre.
- Les cibles disparues, protégées, sorties du Soutien, devenues un autre type ou
  déplacées en Stalemate sont ignorées à la résolution de Multicastigate.

## Vérification

- `tests/test_stack_target_audit.py` : 13 tests avec permutations de cible et de
  motif d'invalidation, contrats groupés et effets dépendants.
- `tests/test_stack_target_integration.py` : vrais messages WebSocket pour jouer
  Multicastigate sur deux Supports, répondre par Wall off et résoudre les deux
  effets ; le Support protégé reste et l'autre est détruit sans remboursement.
- `tests/test_frontend.cjs` : sélection selon le type animé, retour au type imprimé,
  zones selon le type effectif, type conservé des copies de Volontés, copies à
  cible unique, multiples et groupées.
- Suite Python complète : **909 tests réussis**, incluant les 14 nouvelles
  régressions serveur et les vérifications du catalogue et des scénarios.
- Régressions générales de l'interface dans Chrome : **réussies**.

Cette passe couvre ces parcours et les cas reproduits ; elle ne prouve pas toutes
les combinaisons possibles du catalogue.
