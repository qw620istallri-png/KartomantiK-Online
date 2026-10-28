# Choix du Vaisseau et arrivée en Interzone après 141

Ce lot local part du commit publié `355efdd` (bêta 141). Il sélectionne le
premier paragraphe de Gummo, le paragraphe de Wish Upon the Stars et celui de
Pescojolero, the Ringing King. Les attentes sont écrites à partir de leurs textes
imprimés ; les capacités du jeu sont exécutées, sans servir d'oracle aux résultats.
La seconde capacité de Gummo n'est pas certifiée par ce lot.

## Corrections

- Les choix conservent une identité privée par exemplaire dans le Vaisseau.
  Une carte partie puis revenue ne répond plus à un ancien choix ; la copie
  identique survivante reste disponible et choisir le second exemplaire ne
  retire plus le premier. Gummo affiche également les exemplaires séparément.
- Les réponses booléennes ou décimales sont refusées sans mutation. Les mauvais
  joueurs et les confirmations répétées restent refusés.
- Wish conserve aussi l'identité de la carte initiale. Si celle-ci est partie,
  aucune des deux cartes n'est déplacée. Les retours utilisent désormais le
  déplacement d'effet commun : la suspension de BOB est respectée et les deux
  départs du Vaisseau sont observables par les effets concernés.
- Pescojolero récupère une carte lui appartenant depuis le Vaisseau adverse
  dans son Interzone, sans la jouer ni l'enchaîner. Son départ
  ne supprime pas l'effet déjà résolu jusqu'au choix.
- Le chemin commun d'arrivée en Interzone vérifie maintenant la présence de la
  carte et émet ses déclenchements d'entrée sur le champ et en Interzone, ainsi
  que les événements d'entrée observés. Il est utilisé par Pescojolero et par
  la recherche avec destination `interzone_from_search`. Aucun changement des
  styles, des VFX ou de la version des ressources n'est inclus.

Le réordonnancement, le mélange et le déplacement à l'intérieur d'un même
Vaisseau préservent les identités. Le retour après un véritable changement de
zone crée une nouvelle entrée. Cette extension ne change pas le suivi existant
des exemplaires en Main. Les identités internes ne sont pas envoyées aux
joueurs ni aux spectateurs ordinaires.

## Branches et résultats exacts

Gummo conserve ses propres capacités et ses bonus de puissance en copiant la
puissance de base et les effets. La copie reste après le départ de la carte
copiée ; un nouvel exemplaire de Gummo ne reçoit pas une copie destinée à
l'ancien. Son déclenchement de fin de tour est testé par la file réelle dans
l'Interzone, avec des contrôles négatifs depuis la CZ et l'Impasse. Un changement
de contrôle ne réattribue pas au nouveau contrôleur le choix déjà en cours.

Wish fait choisir le propriétaire de la carte initiale. Les valeurs égales et
supérieures sont admises ; les valeurs inférieures, les Volontés et les cartes
appartenant à un autre propriétaire sont exclues. Sans réponse admissible,
aucune carte ne bouge. Les retours normaux sont au-dessus des Decks des
propriétaires ; sous BOB, les deux cartes sont suspendues. Les deux sorties par
effet sont enregistrées.

Pescojolero donne les cartes avant de proposer la prise. Le budget est la somme
des points des cartes effectivement transférées, sans compter une cible déjà
disparue. Une Interzone pleine conserve la carte dans le Vaisseau et ne reprend
pas les cadeaux déjà transférés. Une arrivée de Keen-eyed Seeker crée son effet
sur la pile sous le contrôle du joueur qui la reçoit ; la carte piochée n'arrive
dans sa Main qu'après résolution de cet effet.

## Preuves

Commande ciblée : `python tools/card_vessel_choices_audit.py`.
Les [clauses et exécutions](../reports/systematic-audit/vessel-choice-followup/clauses.json)
conservent les textes, leurs empreintes et les identifiants réellement exécutés.
Les [observations complémentaires initiales](../reports/systematic-audit/vessel-choice-followup/entry-before.json)
conservent les premiers essais du chemin d'arrivée en Interzone. Leur
reproduction de référence utilise les fixtures corrigées ci-dessous.

La [reproduction de référence](../reports/systematic-audit/vessel-choice-followup/baseline-corrected.json)
rejoue 18 méthodes avec les fixtures corrigées sur les méthodes des six mixins
de jeu publiées en 141 : neuf réussissent et neuf échouent, sur 21 sous-cas en
échec. Le script `baseline-published.py` charge ces méthodes en mémoire depuis
le commit `355efdd`, sans modifier les fichiers. Le rapport distingue
l'empreinte des fixtures courantes des empreintes du code de référence chargé.
Il s'agit de tests synchrones de résolution, sans gestionnaire réseau.

Le premier [relevé historique](../reports/systematic-audit/vessel-choice-followup/before.json)
reste conservé, mais n'est pas utilisé comme preuve de référence. Il contenait
une exigence incorrectement placée à la résolution de Gummo : sa condition
d'Interzone est maintenant vérifiée lors du déclenchement réel, sans modifier
ce comportement du jeu. Un sous-cas Pescojolero sélectionnait le cadeau plutôt
que la carte revenue. Les fixtures positives de Pescojolero attribuaient aussi
les cartes au propriétaire du Vaisseau qui les contenait, ce qui est interdit ;
elles utilisent maintenant les cartes du joueur conservées dans le Vaisseau
adverse. Une assertion empêche de reproduire cette erreur de préparation.
Ces erreurs du banc ne sont pas présentées comme des corrections du jeu.

Trois parcours WebSocket vérifient les réponses et les reconnexions avec un
client incrémental et un client ancien. Le pilote automatique des phases est
isolé. Le test de mélange vérifie d'abord qu'il est refusé pendant un choix,
puis utilise une préparation explicite sans choix avant de restaurer le
sélecteur : il ne crée pas de fenêtre de réponse pendant l'effet.

`node tests/test_vessel_picker.cjs` vérifie les trois sélecteurs dans six
configurations Chrome (français, anglais, italien ; PC et paysage mobile simulé),
soit 18 scénarios. Il utilise les payloads sérialisés par le serveur, des cibles
de fixture et des dos de cartes locaux. Les clics sur les copies identiques,
les indices envoyés, le blocage après confirmation et le réaffichage après
snapshot sont vérifiés. Six captures françaises sont conservées localement ;
le contrôle visuel porte sur la sélection, pas sur les illustrations distantes.

Les résultats finaux et empreintes sont reliés dans
[EXECUTIONS.md](../reports/systematic-audit/vessel-choice-followup/EXECUTIONS.md).

## Limites

Ce lot ne certifie ni toutes les branches de ces cartes, ni les 450 cartes.
Les mutations pendant un sélecteur servent à vérifier les réponses périmées ;
elles ne représentent pas des actions légales au milieu d'un effet. L'annulation
automatique d'un sélecteur dont toutes les options disparaissent reste à couvrir.
Les choix avec plusieurs remplacements concurrents, les changements de points
pendant un choix, les autres sélecteurs et la persistance après redémarrage du
serveur ne sont pas certifiés ici. Les interactions avec la protection du
Vaisseau restent aussi à vérifier séparément. Le ciblage initial de Wish reste soumis au
contrat existant de ciblage par identifiant/version de zone ; ce lot ne généralise
pas des identités publiques à tous les ciblages du moteur.

Le parcours complet de recherche vers l'Interzone reste distinct du test de son
chemin commun d'arrivée. Les appareils physiques, Safari Mac et les illustrations
distantes restent hors de ce lot. Les VFX publiés en 141 sont conservés.
