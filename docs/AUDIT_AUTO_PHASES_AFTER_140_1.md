# Passage automatique et phases — suite locale

Cette passe ajoute 19 tests : 16 méthodes d'invariants et trois scénarios réseau.
La campagne ciblée rejoue aussi les contrôles existants d'auto-pass, de cibles
invalides et de commandes retardées : **59 tests réussis**.
Les preuves sont séparées dans `reports/systematic-audit/auto-phase-followup/`.

## Blocage reproduit et corrigé

Le pilote limitait chaque appel à 60 opérations de priorité. Deux passes sont
nécessaires pour résoudre un effet normal : avec 32 effets, il en résolvait 30,
puis s'arrêtait avec deux effets restants. Aucun message n'arrivait ensuite pour
le reprendre puisque les joueurs n'avaient aucune réponse jouable.

La limite sert maintenant de point de reprise coopératif : le même pilote rend
la main à la boucle asynchrone, puis réévalue les actions et choix avant un
nouveau lot. Le verrou de session reste détenu pendant cette reprise, ce qui
empêche un second pilote de résoudre en parallèle.

La reprise couvre aussi une pile qui devient vide exactement à la limite : les
phases encore passables continuent, sans exiger un nouveau clic. Elle s'arrête
sur un choix, une réponse possible, la demande de confirmation de confrontation,
la première Manifestation à choisir, le Mulligan obligatoire ou la fin de partie.

Le pilote vérifie également l'activation du moteur assisté et du suivi de phases
avant de traiter les Immediates. Ce garde-fou empêche une pile résiduelle injectée
dans un état manuel/inactif de produire des résolutions automatiques. Ce second
cas est un test défensif, pas une reproduction d'une partie manuelle réelle.

Les reproductions avant correction sont conservées dans `before.json`
(13 méthodes, cinq méthodes en échec / sept échecs de sous-cas) et
`boundary-before.json` (frontière exacte avant la reprise des phases vides).
Elles portent leurs propres empreintes historiques. `observations.json` conserve
le premier constat : 60 opérations et deux effets restants sur une pile de 32.

## Invariants et branches vérifiés

| Domaine | Attente exécutée |
| --- | --- |
| Quinze sous-phases | Une pile de trois effets produit les valeurs 100, 110, 111 dans cet ordre, sans changer de phase ni de tour tant qu'elle se vide ; auto-skip des phases désactivé |
| Longues piles | 32 et 61 effets normaux, 65 effets aux cibles invalides ; aucun message supplémentaire requis pour vider la pile |
| Frontière exacte | Après 30 effets en Phase Finale, les phases vides reprennent jusqu'au choix de Première Manifestation du tour suivant |
| Choix obligatoires | Neuf familles de choix bloquent les effets normaux et immédiats ; un choix au-delà du premier lot arrête puis reprend la pile une fois |
| Concurrence | Un second pilote appelé pendant la publication du premier effet ne consomme pas la carte suivante |
| Réponses nouvelles | Une réponse devenue disponible après le premier lot conserve sa fenêtre ; relâcher « tout passer » rend la priorité au joueur |
| Recovery / fin de tour | Première Manifestation et Mulligan bloquants ; les deux excédents de main sont traités avant le changement de tour ; saut de Phase Finale individuel |
| Fin de partie | Une concession pendant la publication du premier effet arrête le travail restant |
| Origines de Volontés | Strengthen réellement déclarable depuis Grimoire, Limbo autorisé et Suspension dans les trois fenêtres de réponse ; aucun passage automatique préalable |
| Déclarations du catalogue | 182 préparations comparées à la déclaration générale : les 180 acceptées ne sont jamais marquées « aucune action » |

Le dernier contrôle est une comparaison de chemins, pas un oracle indépendant
pour toutes les cartes. Ses fixtures sont généreuses en ressources et peuvent
contenir plusieurs actions possibles. Les deux préparations refusées par la
déclaration générale ne sont pas certifiées par cette comparaison.

## Trois nouveaux scénarios réseau

Le pilote automatique reste réel ; seules les attentes d'animation sont
raccourcies dans le banc de test. Les deux sièges consomment leurs états.

1. Une seule commande lance 33 résolutions. Les deux joueurs reçoivent chaque
   état intermédiaire avec pile décroissante, score exact et phase inchangée.
2. Deux Immediates puis un effet normal sont publiés séparément ; chaque
   publication demande la pause configurée de **1,7 seconde** avant la suivante.
   Le test observe la valeur demandée, sans attendre réellement 1,7 seconde.
3. Un choix de défausse après le premier lot arrête la pile ; la réponse du
   joueur concerné reprend les trois derniers effets, chacun une seule fois.

Les dix scénarios de latence précédents sont également rejoués : ajout d'une
réponse pendant la pause, reconnexion, commandes périmées et Immediates avant
réouverture des réponses normales.

## Limites et publication

Les quinze étapes sont exercées avec des effets synthétiques pour isoler leur
ordonnancement ; ce n'est pas une certification de chaque déclenchement de
chaque carte à chaque phase. La pause demandée est vérifiée, pas sa durée réelle
sur Internet ni la fluidité des animations sous charge. Les tests ne constituent
pas un benchmark de clients lents ou non lecteurs.

Le comportement conservateur de Réaction reste intentionnel : détenir une
Volonté Éphémère peut retenir la priorité même si l'estimation rapide du coût
ou des cibles ne prouve pas qu'elle est immédiatement jouable. La désactivation
du saut de phases n'empêche pas de résoudre automatiquement une pile à laquelle
le joueur n'a aucune réponse ; elle conserve les limites de phase.

Aucune nouvelle campagne générale des 450 cartes, illustration distante,
vérification Safari Mac ou certification d'appareil physique dans ce lot.
Version 140.1 conservée ; aucun commit ni push.

Commande ciblée : `python tools/auto_phase_audit.py`. Les preuves détaillent les
identifiants et sous-cas ; leur empreinte distingue les campagnes historiques.

## Validation finale

**1 364 tests Python réussis**, aucun échec ni test ignoré. Les 59 tests ciblés
sont inclus dans cette suite complète. Quatre suites UI passent également :
parité client-serveur, continuité des choix, connexion et frontend.
Le [registre d'exécution](../reports/systematic-audit/auto-phase-followup/EXECUTIONS.md)
assemble les preuves sous une même empreinte des sources.
