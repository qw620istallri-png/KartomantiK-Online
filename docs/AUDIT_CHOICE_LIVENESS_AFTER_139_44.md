# Audit des choix sans issue après 139.44

Passe du 23 octobre 2026. Corrections intégrées à la version 139.45.

## Blocages et défauts reproduits puis corrigés

### 1. Copie sans nouvelle cible légale

Imitate copiant Mirror the Impulse sans Manifestation du contrôleur de la copie
ouvrait un choix dont toutes les réponses étaient refusées. « Conserver » passait
par la validation d'une nouvelle déclaration, alors que les cibles sont héritées
de l'action copiée. Une cible disparue ou devenue Protégée bloquait aussi cette
option ; une copie à plusieurs cibles ne pouvait pas conserver une cible invalide
pour résoudre ensuite les instructions applicables aux autres.

« Conserver » reprend maintenant uniquement le snapshot privé du serveur. La copie
rejoint la Stack puis suit la validation habituelle à la résolution : résolution
partielle, ou résolution automatique sans effet si toutes ses cibles sont invalides.
Le choix de nouvelles cibles reste entièrement validé. Une requête rejetée reste
sans mutation ; envoyer des cibles avec « Conserver » ne remplace pas le snapshot.

### 2. Ju Lien et interdiction d'entrée en Soutien

Si l'entrée en Soutien avait été verrouillée avant la résolution, Ju Lien ouvrait
encore son choix de Volonté. Chaque sélection échouait et la partie restait bloquée.
Le prérequis est maintenant vérifié avant la proposition et à la résolution. La
Volonté reste en Main si l'entrée est interdite ; le parcours normal reste actif
quand l'entrée est possible.

### 3. Cible différée disparue après un Effet Immédiat

Un déclenchement de Zombieswing collecté avec une cible dans les Limbes restait
proposé après que Macabre Ritual avait exilé les Limbes. Accepter ouvrait ensuite
un sélecteur obligatoire sans cible. Le même défaut touchait les contrats
obligatoires différés devenus impossibles avant leur proposition.

Les contrats différés sont désormais revérifiés avant la proposition. Le moteur
ignore l'action devenue impossible en conservant le reste du lot. Si cette action
devait reprendre les destinations de confrontation, la continuation attend la fin
des autres choix, puis reprend une seule fois sans les écraser.

### 4. Bullyboo et calcul incomplet du paiement possible

Le calcul n'examinait que les sept premières Manifestations de la Main et utilisait
une seule allocation automatique des Essences blanches. Il pouvait donc appliquer
le défaut de paiement alors que la huitième carte, ou une autre allocation blanche,
permettait de payer.

Le calcul prend toute la Main éligible et les allocations blanches disponibles. Il
utilise le calcul de couverture existant : si le pool légal couvre le coût, un
sous-ensemble minimal peut le payer. Il n'énumère plus tous les sous-ensembles de
la Main. Cette correction concerne le calcul Main + Essences de Bullyboo ; elle ne
redéfinit pas les règles des autres sources de tribut.

### 5. Suites de choix de Kanon

Après la défausse de Volontés remplaçant une pioche, la distribution de pertes de
puissance proposait des Manifestations Protégées, des cartes en Stalemate et même
des copies de Volontés marquées comme jetons. Elle pouvait appliquer la perte sur
ces cartes. La génération et la réponse utilisent maintenant un contrat de cible
Manifestation adverse sur le champ. Sans candidat légal, aucun second choix ; avec
un candidat légal, la distribution reste possible. Les réponses incorrectes sont
refusées avant l'application de tout modificateur.

### 6. Allocation des Essences blanches lors du paiement d'un effet

Le sélecteur de couleurs existait pour jouer une carte, mais les paiements demandés
par un effet conservaient une allocation automatique. Pour un coût bleu + rouge,
une Essence blanche et un tribut bleu, affecter automatiquement le blanc au bleu
rendait le paiement impossible. Cela pouvait verrouiller le paiement obligatoire
de Bullyboo malgré un ensemble de ressources suffisant.

Les quatre familles de paiements d'effets utilisent maintenant le même sélecteur :
contre sur la Stack, mémoire, effet immédiat et autre effet. L'allocation choisie est
transmise par `transcendentPayment` jusqu'au validateur de paiement habituel. Elle
peut être changée avant de payer et reste choisie après conversion d'un compteur
en Essence. Le refus reste disponible pendant la sélection si le paiement est
optionnel ; Bullyboo conserve son paiement obligatoire. Une mauvaise allocation
refuse le paiement sans dépenser les cartes ou les Essences.

## Parcours contrôlés sans nouveau défaut

- Recall (`cnqaie6oq458qgq_en`) termine sa recherche dans un Deck vide sans sélecteur.
- Jigon avec un Deck vide ou sans Volonté termine sans sélecteur. Avec une seule
  Volonté éligible parmi des Manifestations, le choix et la pose cachée aboutissent.
- Bullyboo sans ressource de paiement applique bien sa branche de défaut, révèle
  la Main prévue, retire 10 points et défausse la Volonté sans choix de paiement
  obligatoire.
- Les tests de paiement interrompu et de choix atomiques existants couvrent le
  refus d'un paiement incorrect, la reprise et l'absence de paiement en double.

## Validation

- `tests/test_choice_liveness_audit.py` : 16 tests, dont permutations de cibles
  héritées et contrôles positifs des parcours corrigés.
- `tests/test_choice_liveness_integration.py` : deux tests, Imitate / Mirror par les vrais
  messages WebSocket, reconnexion au choix, conservation du snapshot, résolution
  automatique de la copie sans cible valide, original encore sur la Stack et
  réponse dupliquée sans second effet.
- Le second parcours réseau vérifie qu'une allocation blanche incorrecte est
  refusée sans dépense, puis que l'allocation alternative parvient au serveur et
  permet le paiement complet.
- `tests/test_frontend.cjs` : bouton « conserver » disponible sans nouvelle cible,
  envoi de l'option attendue et régressions générales de l'interface.
- Paiement d'effet avec allocation blanche, réouverture du sélecteur, puis envoi
  du paiement pour les versions optionnelle et obligatoire ; régressions des
  Essences blanches sur PC et mobile.
- Suite Python complète : **927 tests réussis**, dont les 18 nouveaux tests de
  cette passe. Régressions générales Chrome et régressions des Essences blanches
  sur PC/mobile : **réussies**. `git diff --check` sans erreur.

Cette passe vérifie ces familles et les cas reproduits ; elle ne certifie pas
toutes les combinaisons possibles des autres cartes ou paiements spéciaux.
