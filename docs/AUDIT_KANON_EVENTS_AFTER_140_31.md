# Événements et remplacements de Kanon — suite locale de 140.31

Ce lot ajoute 23 méthodes de clauses et deux parcours réseau pour neuf
paragraphes sélectionnés de huit cartes : Kanon, Denblew, Makaboon,
Pale Entity, Forfog, Tombloom, Tenebro et Gorlok. Il prolonge
l'[audit des défausses/pioches](AUDIT_DISCARD_DRAW_AFTER_140_31.md).
Cette passe a été réalisée après le commit publié `62d169c`. Ses corrections
sont intégrées à la [140.32](RELEASE_140_32.md), sans modification des VFX ;
les preuves initiales gardent leur empreinte historique.

## Écarts reproduits

Le choix de Kanon utilisait une extraction et une insertion directes des
cartes. Cela omettait les événements de pioche/défausse et attribuait aux
entrées au Limbo une provenance générique. Denblew, Makaboon, Pale Entity,
Forfog, Tombloom et Gorlok ne réagissaient donc pas correctement à ces
déplacements. Le même chemin contournait la suspension de BOB et le choix
de mettre Tenebro en Soutien.

La validation rejetait deux exemplaires identiques dans une sélection.
Lorsqu'un seul exemplaire était choisi, la comparaison par identifiant
pouvait aussi envoyer toutes les copies inspectées au Limbo. Une valeur
malformée dans la réponse provoquait une exception. Enfin, les déplacements
suivaient l'ordre du Deck en alternant défausse et pioche, alors que le texte
demande de défausser les cartes choisies, puis de piocher les restantes.

Le relevé historique
[before.json](../reports/systematic-audit/kanon-events-followup/before.json)
conserve 23 méthodes exécutées avant correction : neuf réussissent et
14 échouent. L'exception de réponse malformée est incluse dans ces échecs.

## Correction et branches vérifiées

Le choix compte désormais les exemplaires disponibles et sélectionnés.
Il défausse toutes les cartes choisies, puis pioche les autres, en passant
par les déplacements d'effet communs. Une identité de lot distincte rassemble
les cartes réellement piochées dans un seul événement. La liste des cartes
piochées ne comprend ni les cartes défaussées ni celles dont le déplacement
a été remplacé. Le malus de Kanon compte uniquement les Volontés réellement
défaussées.

- Les quantités sont exactes pour une à quatre cartes, les nombres impairs
  et un Deck plus court que la demande. L'inspection ne déplace aucune carte
  avant confirmation. Quatre copies identiques permettent d'en défausser deux
  et d'en conserver deux ; une sélection mixte respecte aussi les quantités.
- Mauvais joueur, mauvais nombre de cartes, exemplaires absents ou en excès,
  réponse malformée et confirmation répétée sont refusés sans nouvelle
  mutation. Un préfixe de Deck qui a changé annule le choix devenu périmé.
- Denblew gagne exactement +1 pour une pioche de plusieurs cartes conservées,
  et +2 pour deux événements distincts avant la même collecte. Une pioche
  normale et une pioche remplacée restent distinctes. Aucun bonus pour zéro
  carte piochée, une pioche propre, une source cachée ou privée d'effets.
- Deux cartes défaussées du Deck font déclencher Makaboon une fois, avec une
  défausse additionnelle exacte dans la Main du joueur concerné. Cette
  défausse depuis la Main ne redéclenche pas Makaboon. Une Main vide n'impose
  pas de sélection impossible. Pale Entity gagne cinq points et Forfog fait
  perdre cinq points pour leur événement de défausse respectif.
- Tombloom entre au Limbo comme défausse depuis le Deck. Son choix de cible
  et son passage sur la pile sont exécutés ; il s'exile et applique exactement
  −2 à la Manifestation choisie.
- Tenebro propose son remplacement avant tout déplacement partiel. Les deux
  réponses sont vérifiées : Soutien en cas d'acceptation, Limbo en cas de
  refus ; dans les deux cas, la pioche restante et l'événement de défausse
  sont conservés.
- Avec un seul BOB au seuil de suspension des Decks, les quatre déplacements
  sont remplacés par une suspension. Aucune pioche, défausse ou pénalité pour
  Volonté défaussée n'est alors inventée.
- Deux Volontés défaussées permettent de répartir deux malus de −1 sur une
  même cible ou deux cibles opposées, y compris dans l'Interzone. Sans cible
  légale, le choix n'est pas proposé. Le départ de Kanon n'annule pas un
  remplacement déjà créé.
- Pour un événement isolé, Gorlok montre uniquement les cartes conservées,
  exile l'une d'elles et perd autant de puissance que de cartes montrées.

## Réseau et interface

Les deux parcours emploient des WebSockets locaux réels, un client incrémental
et un ancien client. Le premier retrouve quatre copies identiques après
reconnexion, refuse les réponses invalides, en défausse exactement deux et
résout un unique bonus de Denblew. Le second retrouve le remplacement de
Tenebro après reconnexion sans déplacement partiel, refuse une réponse de
l'adversaire et achève le Soutien puis la pioche une seule fois. Les détails
internes de reprise ne sont pas exposés dans le choix sérialisé.

Le test navigateur vérifie le sélecteur de Kanon dans trois langues et deux
tailles d'écran, soit six configurations Chrome. Les quatre copies restent
sélectionnables individuellement, la limite de deux est respectée, retirer
une sélection désactive la confirmation et l'envoi contient bien deux
exemplaires identiques. Aucune modification du code d'interface ou des VFX
n'a été nécessaire.

## Preuves et limites

Commandes ciblées : `python tools/card_kanon_events_audit.py` et
`node tests/test_kanon_picker.cjs`. Les paragraphes, attentes et identifiants
des tests sont reliés dans
[clauses.json](../reports/systematic-audit/kanon-events-followup/clauses.json).
Le registre [EXECUTIONS.md](../reports/systematic-audit/kanon-events-followup/EXECUTIONS.md)
consigne les régressions finales et leurs empreintes.

Validation finale : **1 489 tests Python réussis**, aucun échec ni test ignoré,
et six suites client réussies : cinq suites navigateur, dont les six
configurations du sélecteur, et une suite JavaScript du transport. La parité
client/serveur rejoue 608 scénarios. Les preuves ciblées, générales et client
portent la même empreinte des sources.

Les demandes de pioche sont préparées explicitement. La plupart des effets
observateurs sont résolus en isolation ; les parcours réseau isolent le
pilote des phases. Ces fixtures ne certifient pas toutes les façons de créer
une pioche en partie. Les tests de Gorlok concernent un seul événement : ses
événements multiples ou retardés et les cartes ayant quitté puis rejoint la
Main restent à auditer. Le départ puis retour d'une carte inspectée dans un
Deck resté identique visuellement n'est pas couvert par le seul contrôle du
préfixe.

L'exil de Tenebro après victoire, les autres paragraphes des cartes, les
remplacements concurrents, les autres seuils et la libération de BOB ne sont
pas certifiés par ce lot. Les images utilisées par le test navigateur sont
locales ; les illustrations distantes, Safari Mac et les appareils physiques
ne font pas l'objet d'une nouvelle certification.

La [passe Gorlok suivante](AUDIT_GORLOK_DRAW_AFTER_140_31.md) prolonge maintenant
les groupes retardés, les exemplaires en Main et le départ de sa source.
Les preuves de ce premier lot restent historiques.
