# Audit des choix refusés, périmés et repris — après 139.2.2

Passe locale du 22 octobre 2026. Cinq défauts reproduits puis corrigés. Sans changement de version ni push à ce stade ; corrections intégrées ensuite à la version 139.3.

## 1. Répartition de decks partiellement appliquée malgré un refus

Le choix de Dissect peut porter sur les deux decks. Avant correction, une première répartition valide modifiait le deck de P1 avant la vérification de la répartition de P2. Une carte invalide, manquante ou un groupe dupliqué dans cette seconde partie provoquait une erreur, en conservant pourtant la première modification. Un transfert impossible d'une carte mise de côté pouvait aussi survenir après l'extraction des cartes à réordonner.

Le résolveur valide maintenant tous les groupes, leur unicité, les cartes et les conditions des transferts avant de commencer les déplacements. Le choix reste ouvert après un refus et peut être corrigé. Le mécanisme existant de suspension de BOB est pris en compte lors de la validation des transferts.

Fichier : server/game/choices/cards.py, _rules_choice_deck_reorder.

## 2. Destinations de confrontation partiellement appliquées

Même défaut sur confrontation_relocation : une première Manifestation pouvait entrer dans l'Interzone avant le refus d'un groupe suivant. Une carte disparue ou sortie de la CZ pouvait aussi être détectée trop tard. Une valeur JSON non textuelle dans la liste pouvait provoquer une exception après une première modification.

Tous les groupes et toutes leurs sources sont maintenant contrôlés avant le déplacement. Une réponse incorrecte ne déplace pas de carte, ne donne pas les 50 points de fin d'effet et ne change pas la phase. Une réponse valide termine le parcours une seule fois.

Fichier : server/game/choices/confrontation.py, _rules_choice_confrontation_relocation.

## 3. Distribution de pertes de puissance partiellement appliquée

Avec deux cibles annoncées et une seconde cible disparue, le premier modificateur de puissance était déjà ajouté avant l'erreur. Les cibles sont désormais toutes vérifiées avant création des modificateurs. Attribuer plusieurs pertes à une même cible reste autorisé.

Fichier : server/game/choices/decisions.py, _rules_choice_power_loss_distribution.

## 4. Annulation d'un choix obsolète non communiquée aux clients

Certains résolveurs annulent volontairement un choix dont la ressource a disparu, puis renvoient une erreur. Le serveur envoyait seulement l'erreur au demandeur : les écrans continuaient donc à afficher un choix qui n'existait plus sur le serveur.

Après une erreur, si le résolveur a annulé ou remplacé le choix courant, le serveur diffuse maintenant le nouvel état aux connexions concernées, via la sérialisation habituelle par rôle. Une réponse à un ancien identifiant ou provenant du mauvais joueur ne change pas le choix courant.

Fichier : server/main.py, traitement de resolve_rules_choice.

## 5. Interface verrouillée après un refus

Le parcours de répartition des destinations de confrontation conservait son verrou d'envoi après une erreur. Certains boutons de choix restaient également désactivés. Une nouvelle tentative était alors impossible sans réouverture de l'écran.

Une reprise commune rétablit les contrôles après erreur. Les répartitions de decks et les destinations de confrontation disposent d'une reprise dédiée qui conserve la disposition des cartes. Les autres écrans sont réaffichés à partir du choix courant.

Fichiers : public/js/choices.js et public/js/connection.js.

## Preuves et contrôles positifs

- Tests moteur : tests/test_choice_atomicity.py, neuf tests avec sous-cas. Comparaison avant/après des joueurs, zones, champs, ressources, moteur et phase pour les refus ; reprise valide ; doublon ; mauvais acteur ; identifiant obsolète ; restitution du choix dans un instantané.
- Tests réseau : tests/test_choice_reconnect.py, quatre tests avec le serveur WebSocket réel. Déconnexion après un refus puis reconnexion et reprise ; double envoi immédiat ne produisant qu'une résolution dans le journal ; refus de l'adversaire et d'un ancien identifiant ; annulation périmée diffusée aux deux joueurs.
- Régressions navigateur PC/mobile : tests/test_release_139_2.cjs. Nouvelle tentative sur un bouton désactivé et sur les déplacements de confrontation, avec disposition conservée après erreur.
- Régression Ponderer : tests/test_ponderer_drag.cjs, parcours de répartition valide sur trois configurations d'écran/thème.
- Suite complète : **763 tests Python réussis**. Contrôles navigateur généraux et régressions PC/mobile réussis.

La plupart des refus problématiques ont été provoqués par des requêtes invalides ou un état de choix devenu périmé. Ces reproductions démontrent un défaut du serveur, sans affirmer qu'une interface normale produit spontanément tous ces messages. Les vérifications portent sur les familles décrites et sur la protection commune des identifiants de choix ; elles ne certifient pas toutes les combinaisons possibles des autres résolveurs.
