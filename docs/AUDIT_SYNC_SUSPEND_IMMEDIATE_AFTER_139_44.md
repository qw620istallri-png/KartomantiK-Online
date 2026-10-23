# Audit synchronisation, Suspend et effets immédiats après 139.44

## Périmètre

- Deux joueurs : choix et paiements bloquants, anciennes validations,
  visibilité privée/publique, connexions simultanées et reconnexion.
- Suspend : propriétaires, permission de Gobres, auto-pass, retour des cartes,
  BOB actif/inactif, jeu depuis la suspension et présentation dans la Main/Stack.
- Effets immédiats : ordre au-dessus des effets ordinaires, absence de réponse
  ou de passe nécessaire, paiements internes et reprise après reconnexion.
- Client : actions différées, animations et aperçus lors d'une déconnexion,
  d'un départ de partie ou du remplacement d'une connexion.

## Problèmes reproduits et corrigés

### Connexions et actions périmées

Les callbacks WebSocket utilisaient la variable globale `ws`. Après son
remplacement, une ancienne ouverture envoyait un nouveau Join sur le socket
récent ; un ancien message remplaçait son état ; une ancienne fermeture lançait
une reconnexion injustifiée. Chaque callback vérifie maintenant qu'il appartient
toujours au socket courant. Le socket remplacé est fermé.

Un test Chrome a aussi reproduit deux envois vers la partie suivante : la
validation de carte différée de 180 ms et le délai tactile de placement de
2,5 secondes survivaient au départ de la précédente partie. Les gestes,
brouillons, placements différés, paniers du navigateur de piles et fenêtres
d'action sont maintenant annulés à la déconnexion, au départ et avant une
nouvelle connexion. Les choix du serveur sont reconstruits depuis son état
après reconnexion ; les anciens brouillons ne sont pas rejoués.

Côté serveur, fermer l'ancien socket d'un joueur le marquait déconnecté malgré
un autre socket actif pour le même siège. La présence reste maintenant active
tant qu'une connexion joueur de ce siège subsiste dans la même session.

### Suspend

- Une Volonté jouable via Gobres ne retenait pas la priorité : l'auto-pass ne
  cherchait pas les actions disponibles parmi les cartes suspendues. Elles
  sont désormais prises en compte, avec leurs fenêtres de jeu et leur coût
  modifié autorisant les Tributs de tout Tempérament.
- Un `suspensionId` fourni mais périmé était ignoré. Il doit maintenant
  correspondre à la permission sélectionnée. L'identifiant traverse également
  les deux chemins de déclaration du client. Le repli sans identifiant reste
  compatible avec les anciens clients.
- Le filtre de confidentialité des suspensions masquait aussi la source d'une
  Volonté déjà jouée sur la Stack. Cette source est maintenant publique ; les
  cartes encore suspendues depuis une zone privée restent filtrées.
- Les cartes suspendues affichées dans la Main n'ont plus systématiquement
  l'aura « jouable » : elles suivent les vérifications de priorité, de timing,
  de paiement et de cibles.
- BOB appliquait son seuil d'exil à 11 même après la perte de ses effets.
  Cette action nécessite maintenant que ses effets soient actifs. Le test
  vérifie aussi que leur réactivation rétablit le seuil et exile les cartes
  suspendues correspondantes.

### Effets immédiats

Les chemins spécifiques résolvaient déjà les pilotes imprimés, mais la boucle
générique d'auto-avance pouvait attendre une réponse volontaire si un effet
immédiat s'y retrouvait au sommet avec des réponses disponibles. Elle traite
maintenant ces effets avant de chercher qui peut agir.

Le serveur refuse une déclaration volontaire ou une passe au-dessus d'un effet
immédiat. Le client n'offre plus de slot de réponse, de carte jouable ni de
bouton de passe dans cet état ; il affiche sa résolution en cours. Un paiement
interne demandé par l'effet reste un choix bloquant et reprend les effets
immédiats suivants après validation, y compris après reconnexion.

### Animations et aperçus

Les cartes retenues avant une animation de départ restaient jusqu'à leur délai
de secours, et les callbacks attendant une destination de Confrontation
pouvaient repartir après le départ de la partie. Le nettoyage supprime les
cartes retenues, leurs temporisations, les créations visuelles différées, les
particules et les verrous d'animation de Main. Les aperçus et les éléments
temporaires de la nouvelle interface sont également nettoyés.

## Vérifications conservées

- Un choix périmé ou validé deux fois ne se résout pas à nouveau et ne repaie
  pas son coût. L'adversaire ne peut pas répondre au choix de l'autre joueur.
- Les choix de cartes privés restent privés dans les états et le journal.
  Les rôles privilégiés existants conservent leur accès prévu.
- Les paiements immédiats ne créent pas de fenêtre de réponse au milieu de
  l'effet ; les Tributs et les conversions de compteurs restent possibles.
- Le jeu d'une Volonté de Gobres paie avec les ressources de son joueur,
  conserve son propriétaire et l'envoie dans les Limbes de ce propriétaire.
- Les durées distinctes de BOB et Gobres, les remplacements concurrents,
  l'ordre des effets simultanés et les effets immédiats imprimés restent
  couverts par les suites existantes.

## Validation

- `tests/test_suspend_immediate_audit.py` : sept tests de moteur.
- `tests/test_sync_suspend_integration.py` : quatre parcours WebSocket réels,
  avec les deux vues et des reconnexions.
- `tests/test_connection_lifecycle.cjs` : callbacks anciens, placements
  différés, animations, aura Suspend, identifiant de suspension envoyé et
  contrôles de réponse pendant un effet immédiat.
- Régressions générales de l'interface, des paiements d'Essence blanche,
  des déplacements et des animations immédiates sur PC/mobile.
- Suite Python finale : **965 tests réussis**, dont les onze nouveaux tests
  de moteur et WebSocket. Un ancien scénario de Timid Brain a été corrigé
  pour vérifier sa résolution immédiate sans imposer deux passes.
- Régressions Chrome : **réussies**. `git diff --check` sans erreur.

Corrections intégrées à la version 139.45. Cette passe vérifie
les familles ci-dessus ; elle ne prétend pas couvrir toutes les combinaisons
possibles de cartes.
