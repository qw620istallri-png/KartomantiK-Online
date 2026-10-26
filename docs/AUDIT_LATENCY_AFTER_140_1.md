# Séquences réseau après la version 140.1

Cette passe locale vérifie les échanges entre deux joueurs pendant les pauses
de résolution, les reconnexions et les commandes reçues après un changement
de fenêtre. Elle n'est pas publiée et ne change pas le numéro de version.

## Problèmes reproduits et corrigés

| Entrée retardée | Comportement reproduit | Correction |
| --- | --- | --- |
| Passe visant un sommet déjà résolu | La passe était appliquée à la pile vide, comme une nouvelle décision de finir la Réaction | Comparer le tour, la phase et le sommet vus par le client à l'état courant avant d'accepter la passe |
| Renforcer envoyé avec un contexte de Réaction | Le serveur acceptait la Volonté pendant les effets de Résolution, après fixation du vainqueur | Refuser la commande périmée avant le paiement, l'extraction de la carte et la mise sur la pile |
| Réponse à un choix déjà terminé | Le serveur renvoyait une erreur mais lançait ensuite le passage automatique ; le test passait de la Phase Finale à la Récupération | Une commande refusée sans mutation ne démarre plus de pilote de passage automatique |

Le client joint `rulesContext` aux déclarations de carte et aux passes en mode
assisté : numéro du tour, identifiant de phase, identifiant du sommet de pile
ou `null` pour une pile vide. Le serveur refuse les contextes incomplets,
malformés ou différents de l'état courant. Le refus renvoie l'état actualisé ;
le client ferme l'action préparée et demande au joueur de choisir à nouveau.
Le message est localisé en français, anglais et italien.

Les options persistantes de passage automatique et le mode manuel conservent
leur fonctionnement. Les anciens clients sans `rulesContext` restent acceptés
pour compatibilité : la protection contre un contexte périmé nécessite donc le
client et le serveur mis à jour. Le refus sans progression des anciens choix
s'applique également à ces anciens clients.

Si le résolveur annule effectivement un choix devenu obsolète, cette mutation
est diffusée et la séquence peut reprendre normalement. Elle est distinguée du
simple refus d'un ancien message n'ayant rien changé à la partie.

## Dix scénarios avec de vraies connexions

`tests/test_latency_stack_sequences.py` ouvre deux sièges via le véritable
serveur WebSocket. Une barrière asynchrone retient une résolution après sa
diffusion, ce qui rend reproductibles les commandes arrivant pendant la pause.
La durée réelle des animations n'est pas mesurée dans ces tests.

1. Les deux joueurs reçoivent les trois résolutions dans l'ordre inverse,
   avec des profondeurs 2, 1, 0 et des scores 100, 110, 111. La Réaction ne
   change pas avant la confirmation sur pile vide.
2. L'autre joueur joue Renforcer pendant la pause. Son +3 est appliqué avant
   l'effet inférieur ; la puissance de sa Manifestation devient exactement 7.
3. Un choix de défausse survit à la reconnexion du joueur. Sa réponse est
   exécutée une seule fois et l'effet inférieur se résout une seule fois.
4. Une passe envoyée pour l'ancien sommet ne valide pas la fin de Réaction.
5. Une Volonté prévue en Réaction n'est pas jouée après la comparaison ; la
   carte et son tribut restent dans la main.
6. Un ancien choix refusé ne fait changer ni de phase ni de tour.
7. Un nouveau sommet ajouté au-dessus de l'ancien invalide l'ancienne passe,
   sans résoudre aucune des deux cartes.
8. Les contextes malformés et d'un ancien tour sont refusés ; une passe valide
   et son annulation continuent à fonctionner.
9. Une mémoire réellement disparue est annulée, puis la pile suspendue reprend.
10. Les effets immédiats restants interdisent les réponses et la dépense de
    ressources ; après leur résolution, l'autre joueur conserve sa fenêtre
    de réponse à l'effet normal inférieur.

## Client et limites

`tests/test_connection_lifecycle.cjs` vérifie dans Chrome l'enregistrement du
contexte avec une pile vide ou occupée, la conservation d'un contexte déjà
fourni, l'absence de mutation du message d'origine, les options persistantes,
le mode manuel, les trois traductions et la fermeture du choix périmé.
Ces tests de client utilisent un WebSocket simulé ; les dix scénarios précédents
utilisent deux véritables connexions réseau locales.

Ces mécanismes peuvent expliquer un décalage entre la manipulation et la fenêtre
où le serveur accepte finalement une action. Ils n'établissent pas à eux seuls
la cause exacte de la partie Sermon/Tong signalée. Le passage automatique avec
une pile encore non vide n'a pas été reproduit dans les scénarios normaux.

Les nouvelles preuves sont conservées dans
`reports/systematic-audit/latency-followup/`. Les rapports de publication 140.1
restent intacts. Cette passe ne certifie ni toutes les interactions des 450
cartes ni un téléphone physique.

## Validation finale

Les 1 244 tests Python passent sans échec ni test ignoré, ainsi que les 13
suites UI. Les dix scénarios réseau ci-dessus font partie de cette exécution.
Les rapports Python et UI portent la même empreinte des sources testées à la
fin de cette passe, avant les correctifs de Soutien suivants :
`029d2ecb7ca5c83fc3fea3803f261584e890b715f8dceb007f3fcc4336507f6a`.
Le fichier `reports/systematic-audit/latency-followup/evidence.json` rassemble
leurs résumés, leurs empreintes de fichier et les dix résultats réseau.
