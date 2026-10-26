# Enchaînements et conséquences différées après 140.1

Cette passe est locale : version inchangée, aucun commit ni push. Elle ajoute
31 tests, dont deux scénarios avec de vraies connexions WebSocket, pour des
branches sélectionnées de 15 paragraphes de huit cartes.

## Référence et portée

Les attentes proviennent des textes anglais et de l'arbitrage `cleanse-memory`
dans `audit/rule-decisions.json` : Cleanse n'efface pas une mémoire d'effet ;
cette mémoire disparaît au Deck ou à l'Exil. Les valeurs attendues et les
destinations sont écrites à la main dans les tests, sans les calculer à partir
des paramètres encodés des capacités.

`python tools/card_chain_outcome_audit.py` exécute le lot et produit
`reports/systematic-audit/chain-outcomes-followup/clauses.json`. Chaque paragraphe
y conserve son texte, son empreinte, les branches attendues et les identifiants
exacts des tests exécutés. Tous les tests ont une association explicite ; une
simple occurrence de nom de carte n'est pas utilisée comme preuve.

## Défauts reproduits et corrections

| Mécanisme | Défaut reproduit | Correction |
| --- | --- | --- |
| Urocione : destination après victoire | Une carte appartenant à l'adversaire allait au Vaisseau du perdant, au lieu de celui d'un adversaire de son propriétaire | Le propriétaire immuable détermine la destination ; le résultat de comparaison reste la référence après un changement de contrôle |
| Urocione : mémoire de victoire | Cleanse, puis une sortie et une nouvelle entrée, pouvaient effacer la conséquence de victoire | Mémoire distincte des modificateurs, conservée à travers main, Limbo et Vaisseau ; oubli au Deck/Exil |
| Lady of the Humps : mélange final | Recherche sans carte admissible et Chain remplacé par Suspend omettaient le mélange | Le mélange final reste exécuté ; les réponses refusées et répétées ne le déclenchent pas |
| Interdictions de Soutien | Chain pouvait contourner Pin Down et Wretched Arena | La restriction commune de Chain contrôle l'interdiction avant le choix et avant toute extraction, pour le joueur et le tour concernés |
| Dol : mémoire du Vaisseau d'origine | Après retour au Vaisseau puis passage par la main, une nouvelle entrée perdait la destination de remplacement | Le Vaisseau d'origine est mémorisé et restauré pour la même carte ; oubli au Deck/Exil |

Les reproductions exécutées avant correction sont conservées dans `before.json`
et `related-before.json`, avec leur empreinte de source. Le premier rapport
enregistre sept méthodes en échec et leurs sous-cas détaillés ; le second
reproduit séparément la perte de mémoire de Dol après les premiers correctifs.

## Branches et résultats exacts

- Urocione : choix privé facultatif, refus sans mutation, pas de choix vide,
  propriétaire différent du contrôleur, changement de contrôle après comparaison,
  Cleanse et départ de la source, égalité, retours par main/Limbo/Vaisseau,
  oubli au Deck/Exil, nouvelle entrée comme Première Manifestation au tour suivant.
- Lady : sélection obligatoire d'une Manifestation admissible, mélange exactement
  une fois, recherche sans résultat, The Slumberer non enchaînable, remplacement
  par BOB, victoire/défaite/égalité et exil chez le propriétaire immuable.
- Mind Parasite : conséquence d'exil après victoire conservée malgré le départ
  de la source. Ce cas couvre la sélection valide, pas toutes les branches de
  paiement et de timing.
- Help! : perte exacte de dix points, avec ou sans Manifestation enchaînable,
  puis exil de la Manifestation gagnante. Le cas gagnant passe par la déclaration,
  le tribut et la pile : la Volonté arrive une seule fois au Limbo, tandis que
  seule la Manifestation est exilée. Les branches sans carte admissible isolent
  la résolution de la déclaration et du paiement.
- Looj : Wind Sprout revient à la main de son propriétaire et le gagnant reçoit
  ses cinq points imprimés, dans les deux ordres possibles des deux effets sur
  la pile, même après le départ de Looj.
- Dol : sélection limitée aux cartes possédées par le joueur, depuis l'un ou
  l'autre Vaisseau ; retour au Vaisseau d'origine sur sortie causée par effet,
  tandis que l'exil normal après victoire reste applicable. Cleanse conserve
  cette mémoire ; Deck et Exil l'effacent.
- Copies : les mémoires d'Urocione et de Dol ne passent pas à une autre copie
  tant que la carte qui les porte est encore présente sur le champ.

## Deux scénarios réseau

Les deux sièges utilisent le serveur et le protocole réels. Le pilote de passage
automatique est maintenu à l'arrêt pour isoler les choix et leur transport ; les
tests de latence précédents couvrent séparément ce pilote.

1. Urocione : confidentialité du choix face à l'autre joueur, refus de sa réponse,
   reconnexion conservant le choix, entrée d'une carte de propriétaire différent,
   puis destination de victoire vérifiée dans l'état envoyé au joueur.
2. Lady : une Volonté proposée à la place d'une Manifestation est refusée sans
   mutation ni mélange ; une sélection valide mélange une seule fois ; son rejeu
   est refusé sans nouvelle entrée ni nouveau mélange.

## Régression Baranchio

La première suite complète a relevé une ancienne attente contradictoire dans
`test_baranchio_lets_the_opponent_take_support_or_lets_you_chain` : le scénario
interdisait le Soutien aux deux joueurs, tout en attendant que le contrôleur
de Baranchio puisse enchaîner. Sa preuve est conservée dans
`regression-before.json` et n'est pas déclarée réussie.

Le test distingue maintenant une interdiction limitée à l'adversaire (offre
impossible, mais Chain autorisé pour le contrôleur) et une interdiction globale
(ni l'offre ni Chain ne peuvent déplacer de carte). Le scénario ciblé et les
29 méthodes de clauses ont été rejoués avant la nouvelle suite complète.

## Limites

Les résultats de confrontation sont préparés explicitement dans plusieurs cas :
ils ne certifient pas à eux seuls le calcul des puissances qui désigne le gagnant.
Certaines résolutions et certains événements sont isolés de leur déclaration,
de leur coût ou du parcours UI complet.

Le jeu à deux joueurs n'offre qu'un adversaire au propriétaire d'une carte :
la destination d'Urocione est donc automatique. Aucun sélecteur multijoueur n'est
ajouté ni certifié. Les conflits entre plusieurs mémoires concurrentes, les
copies transitant simultanément par des zones cachées et les interactions non
listées restent hors de cette passe.

La matrice, les parcours larges des 450 cartes, les 13 suites UI complètes et les
illustrations de la passe Soutien restent des preuves historiques sous leur
ancienne empreinte. Ils ne sont pas déclarés rejoués par ce lot. Aucun téléphone
physique ni Safari iOS n'est certifié.

## Validation finale

La nouvelle suite complète passe : 1 301 tests Python réussis, aucun échec et
aucun test ignoré. Les 31 tests de ce lot en font partie. Les quatre contrôles UI
rejoués passent également : parité, continuité des choix, connexion et interface
sémantique. Les 450 fiches / 760 paragraphes de revue restent structurellement
valides, sans certification sémantique globale.

Les preuves de clauses, Python et UI portent la même empreinte des sources :
`aad3d2b69320c67e84136e284b6d9a180f17b1f15c4997a3553844f3023d56c7`.
Le [rapport de cette passe](../reports/systematic-audit/chain-outcomes-followup/EXECUTIONS.md)
et son `evidence.json` conservent les résumés, les empreintes de fichiers, les
reproductions initiales et les limites. Aucun rapport historique n'est remplacé.
