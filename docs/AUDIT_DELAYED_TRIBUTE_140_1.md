# Effets différés après un tribut

Le créateur a confirmé que payer Loop comme tribut ne doit pas placer son
effet sur la pile. Le texte imprimé situe le retour de la Volonté en fin de
tour, sous réserve d'avoir perdu une confrontation ce tour.

## Corrections

- L'utilisation en tribut enregistre directement la mémoire. Le déclenchement
  de fin de tour reste un effet normal sur la pile, avec les choix prévus.
- Loop ne propose rien après une victoire, une égalité ou sans défaite. Une
  défaite conservée dans l'historique du tour suffit même si le résultat courant
  a été effacé. Le joueur peut aussi payer Loop après cette défaite.
- Coral Skull, Refrain Repeater et Qu Lom utilisent également cet enregistrement
  sans effet intermédiaire sur la pile. Le retour, le paiement adverse ou le dé
  restent à leur échéance de fin de tour.
- Loop et Coral Skull ne mémorisent pas une Volonté Persistante dont on paie
  seulement un effet activé : cette Volonté n'a pas été jouée par ce paiement.
- L'événement de tribut conserve le propriétaire réel de la carte et le joueur
  qui l'a payée comme contrôleur de l'effet. Refrain et Qu Lom retrouvent ainsi
  le bon Limbo et la bonne main pour leur retour.

Les vrais déclenchements immédiats au tribut, comme celui de Filth-eater,
conservent leur sélection de cible et leur effet normal sur la pile.

## Couverture ajoutée

`tests/test_delayed_tribute_memory.py` ajoute 14 méthodes indépendantes couvrant :

- absence d'action ou de confirmation au paiement des quatre cartes ;
- retour de la Volonté après défaite, refus et absence d'offre répétée ;
- victoire, égalité, absence de défaite et défaite d'un ancien tour ;
- utilisation après la défaite et conservation de son historique ;
- Volonté neutralisée, revenue en main, mise au Deck ou exilée ;
- Phase Finale sautée pour le joueur concerné ;
- les deux parités du dé de Qu Lom, lancé uniquement en fin de tour ;
- paiement ou refus de l'adversaire face à Refrain ;
- absence d'exigence de défaite pour Coral Skull ;
- attribution au propriétaire réel et retour effectif dans sa main ;
- paiement d'une capacité activée de Nullifying Hat ;
- maintien du véritable déclenchement de Filth-eater.

La régression historique de Coral Skull vérifie maintenant qu'une seule action
reste sur la pile au paiement et que sa mémoire est déjà enregistrée.
Le registre de navigation sémantique inclut les nouvelles familles de tests et
le suivi d'intégration auparavant absent de cet index. Une mention de carte
dans un test reste un lien de navigation, pas une certification de sa clause.

Cette passe ne certifie pas toutes les interactions des 450 cartes.

Validation finale : 1 234 tests Python, sans échec ni test ignoré, et les
13 suites UI passent sur la même empreinte de source. Le registre de revue
reste valide pour les 450 cartes et leurs 760 paragraphes. Ses 175 méthodes
indexées mentionnent 106 cartes ; ce nombre de mentions n'est pas un taux de
couverture sémantique. Les rapports JSON conservent les preuves d'exécution.
