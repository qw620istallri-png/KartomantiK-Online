# Bloatuba et Expansive Ponderer — choix après Enchaînement

Ce lot local poursuit la couverture après 141 et après le
[lot Vaisseau/Interzone](AUDIT_VESSEL_CHOICES_AFTER_141.md). Il sélectionne les
deux paragraphes imprimés de Bloatuba et d'Expansive Ponderer. Les attentes
chiffrées et les distributions sont écrites indépendamment des capacités
encodées. Les définitions et les files d'événements réellement livrées sont
utilisées pour l'entrée et l'Enchaînement.

## Défauts reproduits et corrections

Le [relevé avant correction](../reports/systematic-audit/deck-sequence-followup/before.json)
conserve 23 méthodes : dix réussites et treize méthodes en échec, sur dix-neuf
échecs/sous-cas. Les premières préparations du banc ont été corrigées avant ce
relevé et ne sont pas présentées comme des défauts du jeu.

- Bloatuba supprimait tous les identifiants identiques de la liste restante.
  Une seule position révélée est maintenant retirée. Choisir le second exemplaire
  retire bien celui-ci du Deck, même si BOB remplace son déplacement.
- Le répartiteur du Deck refusait les identifiants répétés dans une même zone
  ou entre plusieurs destinations. Il vérifie désormais les quantités exactes :
  chaque exemplaire offert est utilisé une fois, sans accepter une copie de plus.
- Le choix de Bloatuba et les répartitions de cartes inspectées pouvaient agir
  sur des cartes ailleurs dans le Deck, ou parties puis revenues. Ils conservent
  le préfixe inspecté et ses versions d'entrée. Une ancienne réponse est refusée
  sans mutation. Les indices booléens et décimaux de Bloatuba sont aussi refusés.
- Le déplacement vers l'Impasse de Bloatuba contournait la suspension des sorties
  du Deck par BOB. Il utilise maintenant le remplacement commun avant toute
  extraction. L'ordre des cartes restantes reste demandé après ce remplacement.
- Le simple réordonnancement dans un Deck appelait l'extraction de zone, ce qui
  changeait les versions et effaçait les tours d'entrée. Il réorganise maintenant
  les listes sans produire de sortie/entrée de zone. Les cartes réellement mises
  en Main ou à l'Exil utilisent toujours les déplacements d'effet habituels.

Les données privées de validation du préfixe restent côté serveur, y compris
dans les groupes du choix. Les styles, le client et les VFX de la 141 sont
conservés. Aucune version des ressources n'est modifiée et aucun push n'est fait.

## Branches vérifiées

Bloatuba révèle les trois cartes correspondant à la puissance de base trois de
la Manifestation de fixture enchaînée ; les bonus de puissance de Bloatuba ne
changent pas ce nombre. Le joueur adverse choisit une Manifestation, puis le
contrôleur de Bloatuba établit l'ordre des cartes restantes sous le Deck adverse.
Les identifiants révélés sont publics dans le résultat de l'Enchaînement.

Le cas `[A, Volonté, A]` permet de sélectionner le second A et conserve
`[A, Volonté]`. Trois A identiques laissent deux exemplaires à ordonner. Sans
Manifestation révélée, toutes les Volontés sont ordonnées, y compris les doublons.
Un Deck vide ou réduit à une seule carte termine la séquence sans exiger de carte
manquante. Le placement normal est dans l'Impasse, sans déclenchement d'entrée
sur le champ ; Keen-eyed Seeker sert de contrôle négatif. Sous BOB, la carte
choisie est suspendue, pas placée dans l'Impasse.

Expansive Ponderer permet exactement une carte en Main, puis une répartition
libre des autres exemplaires entre dessus et dessous. Trois A identiques peuvent
donner un A à chaque destination. Une quantité incorrecte ou une carte non
inspectée est refusée. La carte est mise en Main, pas piochée : un verrou de
pioche et Kanon ne remplacent pas ce déplacement, et aucun événement de pioche
n'est produit. BOB suspend seulement la carte qui quitte réellement le Deck,
sans suspendre les cartes simplement réordonnées dedans.

Pour les deux cartes, les refus d'Enchaînement passent par leur véritable effet
facultatif ; une Main sans Manifestation enchaînable ne crée pas de sélecteur de
Deck. Le départ de la source après le début de la séquence ne l'annule pas.
Les mauvais acteurs, réponses périmées et confirmations répétées sont refusés.

Un test supplémentaire utilise Dissect pour vérifier le répartiteur commun avec
deux Decks comportant des doublons. Une seconde distribution invalide ne modifie
pas la première ; la réponse correcte ordonne ensuite les deux Decks. Ce test
d'interaction ne certifie pas tout le texte de Dissect et ne compte pas comme
une troisième clause entièrement couverte.

## Réseau, interface et preuves

`python tools/card_deck_sequence_audit.py` conserve les
[clauses et identifiants exécutés](../reports/systematic-audit/deck-sequence-followup/clauses.json).
Le lot comprend 23 méthodes de clauses/interactions et trois parcours réseau.
Les parcours utilisent l'entrée réellement mise sur la pile, les deux passes de
priorité et la réponse d'Enchaînement, puis les sélecteurs. Un client incrémental
et un client ancien vérifient le changement d'acteur de Bloatuba, les copies
restantes après reconnexion, le remplacement de BOB, les refus et les rejeux.
Le pilote automatique des phases est isolé pour ces parcours.

`node tests/test_deck_sequence_ui.cjs` utilise les choix sérialisés du serveur et
des illustrations locales de fixture. Six configurations Chrome combinent le
français, l'anglais et l'italien avec PC et paysage mobile simulé. Dix-huit
scénarios vérifient le clic sur le second exemplaire de Bloatuba, la confirmation
des doublons restants et les glissements de trois cartes identiques vers les
trois destinations de Ponderer. Les quantités envoyées, le verrouillage après
réponse et la nouvelle tentative après erreur sont vérifiés. Quatre captures
françaises servent au contrôle visuel des répartitions.

La validation complète et les empreintes sont réunies dans
[EXECUTIONS.md](../reports/systematic-audit/deck-sequence-followup/EXECUTIONS.md).
Les preuves du lot Vaisseau précédent conservent leurs empreintes historiques.

## Limites

Ce lot ne certifie pas toutes les branches des deux cartes ni les 450 cartes.
Les Decks utilisent le contrat existant de versions par identifiant de carte,
pas une identité unique de chaque exemplaire dans toutes les opérations du Deck.
Une mutation d'un autre exemplaire du même identifiant peut donc invalider
prudemment le choix, même si les noms du préfixe sont inchangés. La sélection de
Bloatuba distingue les positions révélées tant que ce préfixe reste valide.

Les mutations pendant un choix sont des vérifications de réponses périmées,
pas des fenêtres légales de réponse au milieu de l'effet. L'annulation automatique
si toutes les options deviennent invalides, les changements de puissance de base
de la carte enchaînée lors de son entrée, tous les remplacements concurrents et
les autres continuations `afterDraw` / `afterDiscard` restent à couvrir.
Les tests n'établissent pas le déroulement complet d'une partie avec auto-skip,
la persistance après redémarrage, Safari Mac, les appareils physiques ou les
illustrations distantes.
