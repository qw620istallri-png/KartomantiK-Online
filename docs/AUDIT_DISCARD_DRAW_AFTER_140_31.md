# Pioche après défausse ou coût additionnel — suite de 140.31

Cette passe vérifie trois paragraphes sélectionnés : le texte de Pray the Ether,
le déclenchement « Whenever you play a Will » d'Alchemical Press et le texte de
Martyrize. Elle ajoute 22 méthodes de test de clauses et deux parcours réseau.
Cette passe a été réalisée après la publication de **140.31**, commit
`62d169c`. Ses corrections sont intégrées à la [140.32](RELEASE_140_32.md) ;
les preuves initiales ci-dessous gardent leur empreinte historique. Les VFX
ne sont pas modifiés.

## Écarts reproduits et corrections

- La continuation commune « défausser puis piocher » déplaçait directement les
  cartes du Deck à la Main. Pray et Press ignoraient donc le verrou de pioche
  et le remplacement de Kanon. Elle termine désormais la défausse avant de
  demander une pioche au moteur commun, sans écraser le choix de remplacement.
- Martyrize respectait déjà le verrou mais contournait Kanon après le paiement
  additionnel. Elle utilise maintenant la même demande, en conservant le
  format historique de sa liste de cartes piochées. La Manifestation révélée
  et exilée reste payée ; la Volonté est exilée même si la pioche attend un choix.
- Une demande de pioche verrouillée pouvait encore proposer Kanon. Le verrou
  est maintenant vérifié avant de créer le remplacement, avec conservation
  de l'exception de Recovery.
- Press pouvait proposer son déclenchement avec une Main immunisée, puis
  imposer une sélection impossible. L'offre et la résolution vérifient cette
  disponibilité. L'ancien chemin d'acceptation la vérifie aussi lorsque la
  Main est devenue vide ou immunisée entre les deux choix.

Le relevé [before.json](../reports/systematic-audit/discard-draw-followup/before.json)
conserve 22 méthodes avant correction : 15 passent, sept échouent, avec onze
sous-cas en échec. `fixture-baseline.json` conserve séparément une préparation
antérieure qui omettait le choix d'ordre simultané dans le banc de test. Cet
échec de préparation n'est pas présenté comme un défaut du jeu.

## Branches et échanges vérifiés

Les tests comparent les quantités exactes, les cartes restantes dans chaque
zone et l'ordre défausse/pioche. Ils couvrent la Main vide, les sélections
invalides et le mauvais joueur, les verrous propres et adverses, Kanon adverse
ou allié, ainsi que l'exception de Recovery préparée explicitement. Une pioche
de plusieurs cartes produit un seul événement pour Denblew dans le chemin
normal. Le parcours Press puis Pray vérifie deux défausses et deux pioches
distinctes avec l'ordre de pile choisi par le joueur.

Pour Press, le refus ne défausse ni ne pioche, une Main indisponible ne bloque
pas la résolution, le départ de la source n'annule pas son effet déjà placé
sur la pile et une confirmation répétée ne repioche pas. Martyrize refuse
atomiquement une carte additionnelle qui n'est pas une Manifestation ; son
paiement, sa révélation et son exil précèdent la fenêtre de réponse.

Les deux parcours réseau passent par les gestionnaires normaux sur un serveur
local, avec un client incrémental et un ancien client. Pray retrouve son choix
de défausse après reconnexion, conserve ensuite le choix de Kanon et refuse
le rejeu d'une ancienne confirmation. Les cartes inspectées sont réservées au
joueur concerné. Martyrize retrouve le choix de Kanon après reconnexion sans
rembourser le coût ni remettre la Volonté en main. Les mauvaises quantités sont
refusées sans mutation d'état.

## Preuves et limites

Commande ciblée : `python tools/card_discard_draw_audit.py`.
Les résultats détaillés et les paragraphes imprimés sont reliés dans
[clauses.json](../reports/systematic-audit/discard-draw-followup/clauses.json).
Le registre [EXECUTIONS.md](../reports/systematic-audit/discard-draw-followup/EXECUTIONS.md)
consigne les régressions finales et leurs empreintes.

Validation finale : **1 464 tests Python réussis**, aucun échec ni test ignoré,
ainsi que quatre suites navigateur et une suite JavaScript du transport. Le
contrôle de parité rejoue 608 scénarios. Les preuves ciblées et générales
portent la même empreinte des sources.

La plupart des tests de Press isolent son action déclenchée ; le parcours
combiné déclare Pray puis émet les événements de paiement/jeu comme le serveur.
Les tests réseau isolent le pilote automatique des phases. Le cas Recovery
est une fixture de timing, pas une certification du droit de jouer ces cartes
à cette phase ni du parcours des phases.

Les autres paragraphes de Press, toutes les combinaisons du catalogue, les
copies identiques, les appareils physiques et Safari Mac ne sont pas certifiés
par ce lot. Les événements de pioche/défausse produits à l'intérieur du
remplacement de Kanon restent à auditer séparément. Les preuves historiques
et les illustrations distantes ne sont pas réactualisées par analogie.

La [passe suivante consacrée à Kanon](AUDIT_KANON_EVENTS_AFTER_140_31.md)
apporte désormais des preuves dédiées sur ces événements et remplacements ;
les preuves de cette première passe conservent leur empreinte historique.
