# Audits des groupes, paiements spéciaux et états terminaux après 139.44

Passe du 23 octobre 2026, à la suite de l'audit des choix sans issue. Corrections
intégrées à la version 139.45.

## Cibles groupées

### Défauts reproduits

- Les groupes de Kaos Bro et Karma Bro étaient perdus dans l'action déclenchée :
  le choix n'imposait plus une cible de chaque contrôleur ni les exclusions de
  source. Les informations perdues affectaient également la revalidation sur la
  Stack.
- La disponibilité des cibles ignorait les groupes et les contrats joueur/Stack.
  Un groupe manquant pouvait donc ouvrir un choix obligatoire sans réponse légale.
- La normalisation d'une cible joueur réutilisait la variable identifiant l'acteur.
  Un groupe suivant pouvait alors refuser sa Main ou accepter celle du joueur ciblé.

### Corrections et contrôles

Les groupes sont conservés de la validation d'entrée à la résolution. Leur
disponibilité recherche une affectation complète de cibles distinctes, avec les
droits de zone, contrôleurs, protections et types habituels. Beacon est contrôlé
avec sa paire Stack/champ, ainsi que les groupes aux candidats communs et les
cibles joueur devenues Immunes. Le serveur refuse les rôles inversés sans mutation.

Le choix publie le contexte de source et d'événement pour filtrer les candidats de
chaque groupe côté client. Le parcours navigateur de chacun des deux Bro demande
d'abord l'autre carte du contrôleur puis la carte adverse, et envoie les deux une
seule fois. Une cible devenue Protégée avant la résolution reste ignorée, tandis
que l'autre instruction indépendante se résout.

## Paiements spéciaux

### Défauts reproduits

Le calcul de possibilité restait limité à la Main et aux Essences, alors que le
règlement acceptait déjà des sources supplémentaires. Bullyboo pouvait donc
appliquer la branche d'incapacité malgré un paiement légal depuis les Limbes,
le Réceptacle, le champ, des Gemmes convertibles ou le sacrifice de Kanopo.
Inversement, sommer une Main entière pouvait annoncer un paiement nécessitant
plus de cartes que la limite actuelle du validateur.

### Corrections et contrôles

- La validation des sources physiques est partagée entre le règlement et la
  recherche de possibilité. Le coût, les allocations blanches et les cartes
  superflues restent contrôlés par le validateur de paiement existant.
- Les permissions imprimées d'Interzone et de Limbes, les compteurs Formula de
  l'Alchemical Press, le Réceptacle de Brabataba et la permission globale d'Orator
  sont pris en compte selon leur état actuel.
- Les budgets partagés sont respectés : un compteur Formula ne sert pas plusieurs
  fois, et une Manifestation sacrifiée pour Kanopo ne peut pas aussi payer le tribut.
- Les Gemmes sont converties sur une session isolée pour cette recherche. La Main,
  les zones, les compteurs, les Essences et le flux aléatoire réels restent intacts.
  Le test exécute ensuite réellement le paiement obligatoire de Bullyboo après les
  deux conversions, pour vérifier que le parcours proposé est réalisable.
- Le règlement d'un tribut du champ ou du Réceptacle conserve le propriétaire réel
  de la carte. Une permission neutralisée ou passée à l'autre contrôleur n'est plus
  comptée.
- La limite de sept cartes déjà présente dans le règlement est conservée. Une
  borne de capacité évite d'explorer tous les sous-ensembles d'une grande Main
  lorsqu'elle ne peut pas payer dans cette limite.

## Fin de partie

### Défauts reproduits

La porte d'entrée réseau refusait déjà les actions après la fin. Des résolveurs
internes pouvaient cependant encore exécuter une ancienne entrée de Stack ou
rouvrir un choix différé. Le chemin de Recovery terminé depuis un choix appelait
ensuite ces continuations et pouvait afficher une demande après le résultat.

### Corrections et contrôles

Une finalisation commune traite abandon, échecs de Mulligan, Recovery incomplète,
arrêt de session et arrêt de tournoi. Elle retire choix, priorités et continuations,
en gardant le champ et la Stack pour inspection. Les résolveurs internes refusent
alors de nouveaux effets, lots ou paiements. Une reconnexion et des réponses tardives
ne changent plus le résultat ni les ressources.

Les changements de points seuls ne terminent pas actuellement une partie : cet
audit ne crée aucun nouveau seuil de victoire. Le calcul des résultats existant
est conservé. Un ancien test de Slumberer passait des phases supplémentaires jusqu'à
une Recovery vide, puis continuait à appliquer des capacités après la fin ; il
résout maintenant uniquement les effets d'entrée avant de tester son réveil.

## Validation

- `tests/test_grouped_target_audit.py` : six tests avec permutations Kaos/Karma,
  contrôle d'entrée, affectation distincte, Beacon, Immunité joueur et Main privée.
- `tests/test_special_affordability_audit.py` : douze tests, dont l'ensemble des
  permissions imprimées d'Interzone, les budgets et le double emploi des ressources.
- `tests/test_terminal_state_audit.py` : six tests, Stack immédiate et normale,
  choix périmé, continuations, fin depuis une Recovery et absence de nouveau seuil.
- `tests/test_three_systems_integration.py` : trois parcours WebSocket réels,
  groupes après reconnexion, paiement du Réceptacle via Bullyboo et fin de partie
  avec réponses tardives puis reconnexion.
- `tests/test_frontend.cjs` : parcours Kaos/Karma Bro, source exclue et choix des
  deux contrôleurs avant l'envoi ; régressions générales de l'interface.
- Suite Python complète : **954 tests réussis**, dont les 27 nouveaux tests de ces
  trois audits. Régressions générales Chrome : **réussies**. `git diff --check`
  sans erreur.

Cette passe couvre ces familles et les cas reproduits ; elle ne certifie pas
toutes les combinaisons de cartes possibles.
