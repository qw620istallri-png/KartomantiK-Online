# Traumatize et Extortionist Womb — choix privés en Main

Ce lot ajoute 20 méthodes de clauses et trois parcours réseau pour les deux
paragraphes imprimés de Traumatize et Extortionist Womb. Il prolonge
l'[audit Gorlok](AUDIT_GORLOK_DRAW_AFTER_140_31.md), en réutilisant les identités
privées des exemplaires en Main. Il est intégré à la [version 140.32](RELEASE_140_32.md).

## Écarts reproduits et corrections

Le relevé historique
[before.json](../reports/systematic-audit/private-hand-followup/before.json)
conserve 20 méthodes exécutées avant correction : neuf réussissent et onze
échouent, sur dix-sept sous-cas. Les premières préparations du banc ont été
corrigées avant ce relevé ; elles ne sont pas présentées comme des défauts du jeu.

- Traumatize utilisait un déplacement direct qui contournait l'immunité de Main
  acquise après la révélation et la suspension des entrées au Limbo par BOB.
  Le déplacement d'effet commun est désormais utilisé. Le remplacement de
  Tenebro, qui fonctionnait déjà, est conservé et rejoué.
- Les deux choix pouvaient agir sur le premier exemplaire identique trouvé ou
  reconnaître une carte partie puis revenue en Main. Ils conservent maintenant
  l'identité de chaque carte sélectionnable et refusent une ancienne réponse
  sans déplacer un nouvel exemplaire. Les indices booléens et décimaux sont refusés.
- Womb se déclenchait pendant la Révélation. L'événement est désormais la
  Réaction, conformément à la précision fournie pour « après la Révélation ».
  L'effet normal passe sur la pile avant de demander la décision de l'adversaire.
- Womb ne vérifiait que l'immunité globale des Mains. Elle respecte aussi la
  protection contre les effets adverses de Purifying Ritual, sans révéler une
  Main immunisée. Si l'enchaînement devient impossible, son résultat avec jetons
  est exécuté au lieu de perdre le choix sur une erreur ou de forcer une carte.
- Les listes de cartes des choix privés et la preuve de Womb dans le journal
  étaient exposées aux spectateurs. Ces données sont réservées aux deux joueurs
  concernés et aux rôles privilégiés déjà prévus par le jeu.

## Branches vérifiées

Traumatize paie deux essences lors de sa déclaration, avant les réponses ; la
perte de cinq points se produit à la résolution. Une Main vide ou immunisée ne
supprime pas cette perte. Le contrôleur peut se cibler et sa propre protection
contre les effets adverses ne l'empêche pas de défausser. La carte choisie est
défaussée une seule fois, ou son déplacement est remplacé ; aucun paiement ni
perte de points supplémentaire n'est appliqué lors d'une confirmation répétée.

Womb ne crée pas son choix pendant la Révélation. L'événement de Réaction crée
une action normale sur la pile, qui doit se résoudre avant le choix. Refuser,
avoir une Main vide, uniquement des Volontés, ou uniquement des Manifestations
non enchaînables produit le résultat avec deux jetons de puissance deux {H} en
Soutien. Le cas d'acceptation enchaîne la Manifestation choisie sous le contrôle
de l'adversaire, sans la transformer en carte jouée ni lui faire payer un tribut.
Un verrou de Soutien ou une immunité apparue après la présentation du choix
exécute le résultat alternatif. Le départ de Womb avant la résolution de son
effet ne supprime aucune des deux branches.

Les copies identiques sont testées avec un événement Gorlok en attente : choisir
le second exemplaire retire bien celui pioché, et ne laisse pas son ancien lien
agir sur le premier. Les allers-retours de zone, réponses invalides, mauvais
joueurs et confirmations répétées sont vérifiés sans mutation partielle.

## Réseau, visibilité et interface

Trois scénarios utilisent des WebSockets locaux réels, un client incrémental,
un ancien client et, pour Womb, un spectateur. Traumatize est déclarée par le
protocole normal, perd cinq points à la résolution, retrouve son choix après
reconnexion et conserve le remplacement facultatif de Tenebro sans repayer.

Pour Womb, les deux joueurs reçoivent la Main entière, y compris les Volontés,
tandis que le spectateur ne reçoit ni ses cartes privées ni la preuve du
journal. Le journal complet lui est refusé pendant la partie ; son accès filtré
est ensuite vérifié avec un état de fin de partie préparé explicitement.
Il ne s'agit pas d'un test de la détection de victoire.

Lorsque des Manifestations sont enchaînables, la Main entière reste visible
dans le sélecteur, avec les cartes non admissibles désactivées. L'index envoyé
désigne toujours la liste des choix admissibles. Cet affichage est conservé
après reconnexion. Si aucune carte ne peut être enchaînée mais que l'adversaire
a accepté de montrer sa Main, une révélation privée est envoyée aux seuls
destinataires autorisés avant la publication du résultat avec jetons. La Main
n'est pas marquée comme révélée publiquement pour le reste du tour.

Six configurations Chrome rejouent douze scénarios de sélecteur : français,
anglais et italien, sur PC et en paysage mobile simulé. Elles vérifient aussi
la fermeture de la révélation privée sans superposition d'un choix et la
sélection indépendante des copies identiques. Deux captures françaises servent
au contrôle visuel. Aucun style ni VFX n'est modifié.

## Preuves et limites

Commandes ciblées : `python tools/card_private_hand_audit.py` et
`node tests/test_private_hand_picker.cjs`.
[clauses.json](../reports/systematic-audit/private-hand-followup/clauses.json)
relie les textes imprimés, les attentes et les identifiants réellement exécutés.
[EXECUTIONS.md](../reports/systematic-audit/private-hand-followup/EXECUTIONS.md)
relie les preuves finales à celles de la publication 140.32.

Validation finale commune : **1 538 tests Python réussis**, aucun échec ni test
ignoré, et neuf suites client réussies. La preuve ciblée de 23 méthodes et les
contrôles de publication utilisent la même empreinte finale des sources.

Le pilote automatique des phases est isolé dans les parcours réseau. Womb
utilise sa véritable file d'événements de Réaction, mais le parcours intégral
des phases n'est pas certifié ici. Les codes et l'état de tournoi du spectateur
sont des fixtures explicites. Les mutations de Main pendant un choix déjà ouvert
servent à tester les réponses périmées ; elles ne créent pas une fenêtre légale
de réponse au milieu d'un effet.

Les autres sélecteurs de Main ou de Vaisseau, toutes les combinaisons de
remplacements, le redémarrage du serveur, Safari Mac, les appareils physiques
et les illustrations distantes restent hors de ce lot. Les limites de placement
des jetons imposées par d'autres cartes ne sont pas toutes combinées avec Womb.
Les preuves antérieures conservent leurs empreintes historiques.
