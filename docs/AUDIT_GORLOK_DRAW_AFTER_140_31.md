# Gorlok — groupes de pioche, exemplaires et effets retardés

Cette passe étend la couverture du paragraphe de Gorlok déjà vérifié pour
un événement isolé dans l'[audit Kanon](AUDIT_KANON_EVENTS_AFTER_140_31.md).
Elle ajoute 23 méthodes de clauses et trois parcours réseau. Elle ne compte
pas ce même paragraphe comme une nouvelle clause distincte du catalogue.
Cette passe a été réalisée après la version publiée 140.31, commit `62d169c`,
et prolonge les deux lots précédents. Ses corrections sont intégrées à la
[140.32](RELEASE_140_32.md) ; les preuves initiales gardent leur empreinte historique.

## Écarts reproduits et correction

Gorlok consultait un historique commun à toutes les pioches du tour, puis le
consommait. Un effet pouvait montrer les cartes d'une autre pioche ; le suivant
ne retrouvait plus les siennes. Deux Gorlok pouvaient également se priver de
leur événement commun. Les cartes piochées avant l'arrivée de Gorlok pouvaient
être incluses par erreur.

Le déclenchement conserve désormais son groupe de pioche privé. Les événements
distincts restent séparés, y compris avant une même collecte des déclenchements.
Chaque effet utilise les cartes de son événement encore présentes en Main au
moment de sa résolution, sans consommer le groupe d'un autre effet.

Une simple comparaison par identifiant de carte pouvait reconnaître une carte
partie puis revenue en Main comme l'ancienne carte piochée. Le moteur conserve
désormais une identité privée par exemplaire en Main. Entrer crée une identité,
sortir la retire, et un changement d'ordre ou un mélange conserve les identités.
L'exil de Gorlok retire l'exemplaire sélectionné, même si un autre exemplaire
identique se trouve plus tôt dans la Main. Ces données restent internes au
serveur ; le protocole de réponse du sélecteur conserve son index existant.

L'effet était entièrement ignoré si Gorlok avait quitté le champ. Il peut
désormais encore montrer les cartes valides et en exiler une. La perte de
puissance ne s'applique qu'à l'ancienne source encore présente ; une nouvelle
instance de Gorlok ne reçoit pas le malus de la précédente. Une Main immunisée
empêche la révélation, l'exil et la perte de puissance correspondante. Les
indices booléens ou décimaux sont refusés.

Le relevé historique
[before.json](../reports/systematic-audit/gorlok-draw-followup/before.json)
conserve 22 méthodes avant correction : 11 réussissent et 11 échouent.
Un parcours ne pouvait pas continuer, car le départ de la source supprimait
le choix attendu. Une méthode supplémentaire vérifie ensuite le maintien des
identités lors d'un déplacement à l'intérieur de la Main.

## Branches vérifiées

- Une pioche de trois cartes montre exactement ces cartes, exile celle choisie
  et fait perdre trois puissances à Gorlok. Une carte déjà en Main reste exclue.
- Deux pioches successives donnent deux groupes distincts. Les deux ordres de
  résolution sont testés, dont l'ordre de pile du dernier effet au premier.
  Une pioche survenue pendant l'attente d'un premier effet ne modifie pas son
  groupe. Deux Gorlok conservent chacun leur événement, avec les cartes encore
  disponibles pour le second.
- Le départ d'une partie des cartes filtre le groupe. Le départ de toutes
  termine l'effet sans choix vide ni perte de puissance. Un aller-retour en
  Main ne réactive pas l'ancien lien. Le départ d'un ancien exemplaire identique
  n'invalide pas celui réellement pioché.
- Deux cartes identiques piochées ensemble comptent deux fois pour la puissance,
  mais une seule est exilée. Deux pioches distinctes de cartes identiques restent
  indépendantes : exiler celle du second événement laisse celle du premier
  disponible pour l'autre effet.
- Le départ de la source n'annule pas l'exil. Un retour avec une nouvelle
  instance n'hérite pas du malus. Un changement de contrôleur ne transfère pas
  le contrôle du choix déjà déclenché.
- Main immunisée, mauvaise personne, mauvais index, réponse malformée ou répétée
  ne provoquent pas d'exil ni de malus partiel. Une carte partie puis revenue
  après l'ouverture du choix ne peut pas être substituée à l'exemplaire montré.
- Les exclusions de pioche propre, Recovery, Deck vide, verrou de pioche,
  source hors Interzone, cachée ou privée d'effets sont rejouées. Les références
  privées ne sont pas visibles dans la pile du joueur de Gorlok avant résolution.

L'ancien test général de Gorlok utilise maintenant le déclenchement réellement
produit par la pioche, avec son contexte, au lieu de reconstruire une action
sans lien avec l'événement. Ses assertions de zones et de puissance sont conservées.

## Réseau et interface

Trois parcours passent par de vrais WebSockets locaux, avec un client
incrémental et un ancien client. Ils vérifient les deux groupes après reconnexion,
les réponses invalides et répétées, les copies identiques après réorganisation
et mélange de la Main, ainsi que le départ de la source combiné au retour d'une
carte adverse en Main. Les passes et les confirmations utilisent les gestionnaires
normaux ; les stimuli de pioche et certains déplacements sont préparés explicitement.

Le choix affichait auparavant « défausser » alors qu'il exile. Le libellé indique
désormais l'exil d'une carte piochée et le malus par carte montrée, en français,
anglais et italien. Six configurations Chrome vérifient ce texte, la sélection
d'un exemplaire identique par son index et l'envoi unique. Deux captures françaises
servent à la vérification visuelle sur PC et en paysage mobile simulé. Les VFX,
les styles et la présentation du sélecteur ne sont pas modifiés.

## Preuves et limites

Commandes ciblées : `python tools/card_gorlok_draw_audit.py` et
`node tests/test_gorlok_picker.cjs`.
[clauses.json](../reports/systematic-audit/gorlok-draw-followup/clauses.json)
relie le texte imprimé, les attentes et les identifiants des tests.
[EXECUTIONS.md](../reports/systematic-audit/gorlok-draw-followup/EXECUTIONS.md)
consigne les régressions finales et les empreintes.

Validation finale : **1 515 tests Python réussis**, aucun échec ni test ignoré,
et six suites client réussies : cinq suites navigateur et une suite JavaScript
du transport. Le contrôle de parité rejoue 608 scénarios et le sélecteur Gorlok
six configurations. Les preuves ciblées, générales et client partagent la même
empreinte finale des sources, après renforcement du cas de pioche propre.

Le pilote automatique des phases est isolé dans les scénarios réseau. Les
changements inattendus de Main après ouverture du choix sont des tests de rejet
d'une réponse périmée, pas une autorisation de répondre au milieu de l'effet.
L'annulation automatique de tout choix devenu vide pendant son affichage n'est
pas certifiée par ce lot. Les identités sont conservées lors d'une reconnexion
au même serveur ; le redémarrage du processus n'est pas testé ici.

Toutes les sources de pioche imprimées, les autres effets qui inspectent une
Main, les illustrations distantes, Safari Mac, les appareils physiques et les
VFX ne deviennent pas couverts par analogie. Les preuves des lots précédents
conservent leurs empreintes historiques.
