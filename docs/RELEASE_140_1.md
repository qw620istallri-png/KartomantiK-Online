# Bêta 140.1 — Grimoire et résolution progressive de la pile

- Le Grimoire montre les Volontés sélectionnées, grise leurs exemplaires dans
  la main et propose « Confirmer la pose » ou « Ne rien poser ». Un aperçu peut
  être retiré de la sélection. Les instructions ne s'accumulent plus.
- Les Volontés placées sur le Grimoire sont jouables comme depuis la main,
  même si leur propriétaire est l'adversaire. Leur propriétaire est conservé
  pour les déplacements ultérieurs ; coûts et cibles restent obligatoires.
- Chaque résolution automatique de la pile est diffusée séparément aux
  joueurs, avec une pause de 1,7 seconde. Les effets immédiats suivent aussi
  cette présentation, sans ouvrir de fenêtre de réponse pendant leur résolution.
- Une annonce de phase retardée ne peut plus afficher une ancienne phase ou
  un ancien tour. Les annonces visibles devenues périmées sont retirées.
- Loop ne crée plus d'effet sur la pile lors du tribut : sa mémoire est
  enregistrée directement, puis le retour est proposé en fin de tour seulement
  après une défaite. Le même enregistrement différé est corrigé pour Coral Skull,
  Refrain Repeater et Qu Lom. Les capacités activées ne sont pas confondues avec
  le jeu d'une Volonté, et le propriétaire réel du tribut reste conservé.

Les tests ajoutés couvrent les choix vides, copies identiques, refus atomiques,
propriétaires, coûts, cibles, réponses pendant une pause et la comparaison
Sermon/Renforcer/Tong après résolution de la pile.

Le signalement d'un changement prématuré de phase avec une pile non vide n'a
pas été reproduit. Le défaut des annonces retardées est confirmé et corrigé ;
son lien avec la partie signalée n'est pas établi.

Validation finale en version 140.1, après la passe sur Loop et les effets
différés : 1 234 tests Python et 13 suites UI réussis. Les ressources versionnées
du client, du service worker et des 23 URLs de chargement sont synchronisées.
Les preuves d'audit antérieures conservent leurs empreintes ; elles ne sont
pas présentées comme une nouvelle certification complète des 450 cartes.

Version des ressources : `20261025-rules-beta-140-1`, affichée `beta 140.1`.
Le [rapport détaillé](AUDIT_GRIMOIRE_STACK_AFTER_140.md) décrit les cas vérifiés
et les limites de couverture. Le [suivi des effets différés](AUDIT_DELAYED_TRIBUTE_140_1.md)
documente les nouvelles branches de Loop et des trois cartes apparentées.
