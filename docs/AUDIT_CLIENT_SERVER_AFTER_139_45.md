# Audit de concordance interface / serveur après 139.45

## Périmètre

Disponibilité des capacités, fenêtres de jeu des Volontés, cibles publiques,
coûts spéciaux, conservation de la priorité et validité des choix pendant les
mises à jour du plateau. Les règles et les métadonnées du catalogue servent
d'oracle ; les états transmis au navigateur passent par le sérialiseur réel.

## Écarts reproduits et corrigés

- Jija proposait son activation sans jeton créé par sa source. Zum proposait
  encore les capacités déjà utilisées ce tour ; la limite de cinq utilisations
  de l'autre capacité concernée n'était pas transmise à l'interface. Le serveur
  fournit maintenant les identifiants des capacités disponibles pour le joueur
  qui reçoit l'état, en réutilisant les contrôles de disponibilité de la priorité.
- Chabak restait activable sans les deux autres Manifestations en main.
  Les capacités depuis la main vérifient aussi le paiement avant d'afficher
  leur disponibilité. Le menu de contexte suit les mêmes contrôles.
- Les capacités utilisables sur une carte adverse et celles depuis un Vaisseau
  ouvraient un flux que le contrôle de provenance refermait immédiatement.
  La validation distingue désormais ces droits d'activation de la propriété
  d'une carte sur le champ. L'auto-pass compte aussi les capacités adverses
  explicitement accessibles au joueur, avec son propre paiement.
- Manipulate proposait des Manifestations qui n'étaient pas entrées en
  Interzone ce tour. Deviate et Repress the Self ignoraient les participants
  et le résultat de la Confrontation dans leur liste de cibles.
- Certaines capacités sans contrat de ciblage affichaient les cartes du champ
  comme cibles possibles. Une capacité encodée sans cible n'en propose plus.
- La Protection et l'Immunité des cartes et joueurs, ainsi que la Protection
  d'un Vaisseau, sont prises en compte pour le joueur destinataire. Les cartes
  cachées ne reçoivent pas de métadonnées d'activation ou de ciblage publiques.
- Les filtres de Pile vérifient les cibles du sort/effet et le Tempérament
  choisi par Nullifying Radiance. Une Protection limitée aux adversaires
  n'exclut plus les propres actions du joueur.
- Scrambling Beacon utilise les cibles légales pour le contrôleur de l'effet
  redirigé. Les groupes doivent avoir une affectation complète de cibles
  distinctes ; le premier choix ne peut pas rendre le groupe suivant impossible.
  Les limites de points cumulés et la relation entre les cibles d'Induce
  Desertion sont conservées pendant la sélection.
- Les aperçus de paiement ne s'arrêtent plus aux douze premiers candidats.
  Ils respectent les sept cartes de Tribut, les budgets de Formula, les
  sacrifices de Kanopo et les cartes réservées au coût supplémentaire.
  Un même exemplaire ne paie pas à la fois le Tribut et le coût d'exil/défausse.
  Le serveur conserve également les exemplaires supplémentaires de la source
  lorsqu'il cherche un Tribut payable. Les branches de recherche équivalentes
  sont évitées pour conserver une prévisualisation réactive.
- Un flux volontaire se ferme si le tour, la phase, la priorité, la source ou
  ses capacités ne sont plus valides. Les cibles devenues invalides sont retirées
  avant une validation, y compris différée. Un changement réel de ressources
  remet à jour le paiement ; les choix internes d'Essences blanches ou de
  surcoût ne sont pas confondus avec une mise à jour du serveur.

## Vérification

- `tests/test_rules_parity.cjs` : 529 scénarios de catalogue générés depuis les
  règles et les vues serveur ; comparaison des candidats, des activations et
  des fenêtres de jeu. Cas supplémentaires de paiement, de groupes distincts
  et de choix périmés, avec parcours de flux sur PC et mobile.
- `tests/test_rules_availability.py` : limites d'utilisation, provenance et
  contrôle des jetons, condition de Chabak, priorité pour une capacité adverse,
  treizième candidat au Tribut, exemplaires distincts de la source,
  confidentialité et contrôleur d'une redirection.
- Régressions existantes : moteur et WebSocket, interface générale, cartes
  signalées, paiements en Essences blanches, reconnexion et nettoyage des gestes.
- Résultat final : 973 tests Python réussis et 529 scénarios de concordance
  réussis. Les suites navigateur générale, cartes signalées, Essences blanches,
  reconnexion et nettoyage des gestes passent aussi. Multicastigate conserve
  bien son Tribut de puissance 5 pour payer le surcoût des deux cibles, sur PC
  et mobile.

Ces vérifications couvrent les contrats déclaratifs et les régressions décrites.
Elles ne constituent pas une preuve de toutes les combinaisons possibles entre
les 450 cartes. Les contrôles de déclaration du serveur restent autoritaires.

Corrections locales ; aucune nouvelle version publiée dans cet audit.
